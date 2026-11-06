"""S-08: recorrido HTTP de ofertas y estados/auditoría en PostgreSQL aislado."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app.modules.auditoria.models import AuditoriaEvento
from app.modules.citas import public as citas_public
from app.modules.lista_espera import public as cupos_public, service
from app.modules.lista_espera.models import CupoLiberado, ListaEspera, Reasignacion
from app.modules.lista_espera.schemas import CandidatoCreateIn
from tests.conftest import cabecera
from tests.intervenciones.conftest import crear_cita


@pytest.fixture
def escenario(db, usuarios, client):
    actor = usuarios["RECEPCION"]
    cita = crear_cita(db, nivel=None)
    citas_public.transicionar_cita_interno(db, cita.id_cita, "LIBERADA", usuario=actor, ip="127.0.0.1")
    cupo = cupos_public.crear_cupo_liberado_interno(db, id_cita_origen=cita.id_cita,
        especialidad=cita.especialidad, medico=cita.medico, fecha_hora_cupo=cita.fecha_hora_cita,
        origen_liberacion="INTERVENCION_VOLUNTARIA", usuario=actor, ip="127.0.0.1")
    db.commit()
    candidato = service.crear_candidato(db, CandidatoCreateIn(paciente_anon_id="PAC-C-OFERTA",
        especialidad_req=cita.especialidad, franja_preferida="MANANA"), usuario=actor, ip="127.0.0.1")
    return SimpleNamespace(cupo=cupo, candidato=candidato, cita=cita, headers=cabecera(client, actor), actor=actor)


def eventos(db, id_cupo):
    return list(db.scalars(select(AuditoriaEvento).where(AuditoriaEvento.modulo == "REASIGNACION",
        AuditoriaEvento.entidad_afectada == "cupos_liberados", AuditoriaEvento.id_entidad == id_cupo,
        AuditoriaEvento.accion.in_(("OFERTAR", "RECHAZAR", "DESISTIR", "CERRAR_OFERTA")))
        .order_by(AuditoriaEvento.id_log)))


def ofertar(client, e):
    return client.post(f"/cupos/{e.cupo.id_cupo_liberado}/ofertas", headers=e.headers,
                       json={"id_candidato": e.candidato.id_candidato})


def test_oferta_y_detalles_coherentes_con_bitacora(client, db, escenario):
    e = escenario
    response = ofertar(client, e)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["estado_cupo"] == "EN_OFERTA"
    assert result["oferta_vigente"]["id_candidato"] == e.candidato.id_candidato
    assert result["oferta_vigente"]["id_operador"] == e.actor.id_usuario
    assert result["historial_ofertas"] == [{"id_candidato": e.candidato.id_candidato,
        "fecha_hora_oferta": result["oferta_vigente"]["fecha_hora_oferta"], "cierre": None}]
    assert db.get(ListaEspera, e.candidato.id_candidato).estado_candidato == "CONTACTADO"
    audit = eventos(db, e.cupo.id_cupo_liberado)
    assert len(audit) == 1 and audit[0].accion == "OFERTAR"
    assert audit[0].datos_before == {"estado_cupo": "DISPONIBLE", "estado_candidato": "ACTIVO"}
    assert audit[0].datos_after["id_candidato"] == e.candidato.id_candidato
    for prefix in ("cupos", "cupos-liberados"):
        assert client.get(f"/{prefix}/{e.cupo.id_cupo_liberado}", headers=e.headers).json() == result
    cita = client.get(f"/citas/{e.cita.id_cita}", headers=e.headers).json()
    assert cita["cupo_liberado"]["oferta_vigente"] == result["oferta_vigente"]


@pytest.mark.parametrize("ruta,cierre,accion", [("rechazo", "RECHAZA", "RECHAZAR"),
                                              ("desistimiento", "SIN_RESPUESTA", "DESISTIR")])
def test_cerrar_reofertar_y_no_duplicar_cierre(client, db, escenario, ruta, cierre, accion):
    e = escenario
    assert ofertar(client, e).status_code == 200
    url = f"/cupos/{e.cupo.id_cupo_liberado}/ofertas/{ruta}"
    response = client.post(url, headers=e.headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["estado_cupo"] == "DISPONIBLE" and data["oferta_vigente"] is None
    assert data["historial_ofertas"][0]["cierre"] == cierre
    assert db.get(ListaEspera, e.candidato.id_candidato).estado_candidato == "ACTIVO"
    audit = eventos(db, e.cupo.id_cupo_liberado)
    assert [a.accion for a in audit] == ["OFERTAR", accion]
    assert audit[1].datos_after["id_oferta"] == audit[0].id_log
    assert client.post(url, headers=e.headers).status_code == 409
    assert len(eventos(db, e.cupo.id_cupo_liberado)) == 2
    again = ofertar(client, e)
    assert again.status_code == 200
    assert [h["cierre"] for h in again.json()["historial_ofertas"]] == [cierre, None]


def test_no_reemplazar_oferta_abierta(client, db, escenario):
    e = escenario
    assert ofertar(client, e).status_code == 200
    assert ofertar(client, e).status_code == 409
    assert len(eventos(db, e.cupo.id_cupo_liberado)) == 1


@pytest.mark.parametrize("estado", ["REASIGNADO", "EXPIRADO"])
def test_no_reabrir_cupos_finales(client, db, escenario, estado):
    e = escenario
    db.get(CupoLiberado, e.cupo.id_cupo_liberado).estado_cupo = estado
    db.commit()
    assert ofertar(client, e).status_code == 409
    assert client.post(f"/cupos/{e.cupo.id_cupo_liberado}/ofertas/rechazo", headers=e.headers).status_code == 409
    assert db.get(CupoLiberado, e.cupo.id_cupo_liberado).estado_cupo == estado
    assert eventos(db, e.cupo.id_cupo_liberado) == []


@pytest.mark.parametrize("campo,valor", [("especialidad_req", "PEDIATRIA"), ("franja_preferida", "TARDE"),
                                       ("estado_candidato", "ASIGNADO"), ("estado_candidato", "DESISTIDO")])
def test_rechaza_candidato_incompatible_o_final_sin_escrituras(client, db, escenario, campo, valor):
    e = escenario
    setattr(db.get(ListaEspera, e.candidato.id_candidato), campo, valor)
    db.commit()
    assert ofertar(client, e).status_code == 409
    assert db.get(CupoLiberado, e.cupo.id_cupo_liberado).estado_cupo == "DISPONIBLE"
    assert eventos(db, e.cupo.id_cupo_liberado) == []


def test_recurso_inexistente_conserva_404(client, escenario):
    e = escenario
    assert client.post("/cupos/999999999/ofertas", headers=e.headers,
                       json={"id_candidato": e.candidato.id_candidato}).status_code == 404
    assert client.post(f"/cupos/{e.cupo.id_cupo_liberado}/ofertas", headers=e.headers,
                       json={"id_candidato": 999999999}).status_code == 404


def test_candidato_no_recibe_dos_ofertas_abiertas(client, db, escenario):
    e = escenario
    assert ofertar(client, e).status_code == 200
    otra = crear_cita(db, nivel=None, id_cita_externa="CIT-C-OTRA", paciente_anon_id="PAC-C-OTRA")
    cupo = cupos_public.crear_cupo_liberado_interno(db, id_cita_origen=otra.id_cita,
        especialidad=otra.especialidad, medico=otra.medico, fecha_hora_cupo=otra.fecha_hora_cita,
        origen_liberacion="CANCELACION_EXTERNA", usuario=e.actor, ip="127.0.0.1")
    db.commit()
    response = client.post(f"/cupos/{cupo.id_cupo_liberado}/ofertas", headers=e.headers,
                           json={"id_candidato": e.candidato.id_candidato})
    assert response.status_code == 409 and response.json()["error"]["codigo"] == "CANDIDATO_EN_OFERTA"
    assert eventos(db, cupo.id_cupo_liberado) == []


def test_legacy_sin_evento_no_inventa_oferta(client, db, escenario):
    e = escenario
    db.get(CupoLiberado, e.cupo.id_cupo_liberado).estado_cupo = "EN_OFERTA"
    db.commit()
    response = client.post(f"/cupos/{e.cupo.id_cupo_liberado}/ofertas/rechazo", headers=e.headers)
    assert response.status_code == 409 and response.json()["error"]["codigo"] == "OFERTA_NO_REGISTRADA"
    assert eventos(db, e.cupo.id_cupo_liberado) == []


def test_cerrar_no_resucita_desistido(client, db, escenario):
    e = escenario
    assert ofertar(client, e).status_code == 200
    r = client.patch(f"/lista-espera/{e.candidato.id_candidato}", headers=e.headers, json={"estado_candidato": "DESISTIDO"})
    assert r.status_code == 200
    r = client.post(f"/cupos/{e.cupo.id_cupo_liberado}/ofertas/desistimiento", headers=e.headers)
    assert r.status_code == 200
    assert db.get(ListaEspera, e.candidato.id_candidato).estado_candidato == "DESISTIDO"


def test_oferta_reasignacion_humana_cierra_historial(client, db, escenario):
    e = escenario
    assert ofertar(client, e).status_code == 200
    url = f"/cupos/{e.cupo.id_cupo_liberado}/reasignar"
    data = {"id_candidato": e.candidato.id_candidato, "confirmacion_humana": False}
    assert client.post(url, headers=e.headers, json=data).status_code == 400
    assert db.get(CupoLiberado, e.cupo.id_cupo_liberado).estado_cupo == "EN_OFERTA"
    result = client.post(url, headers=e.headers, json={**data, "confirmacion_humana": True})
    assert result.status_code == 200, result.text
    detail = client.get(f"/cupos/{e.cupo.id_cupo_liberado}", headers=e.headers).json()
    assert detail["oferta_vigente"] is None and detail["historial_ofertas"][0]["cierre"] == "REASIGNADO"
    assert detail["reasignacion"]["id_reasignacion"] == result.json()["id_reasignacion"]
    assert client.post(f"/cupos/{e.cupo.id_cupo_liberado}/ofertas/rechazo", headers=e.headers).status_code == 409
    assert [a.accion for a in eventos(db, e.cupo.id_cupo_liberado)] == ["OFERTAR", "CERRAR_OFERTA"]


def test_no_reasignar_a_otro_candidato_con_oferta_vigente(client, db, escenario):
    e = escenario
    assert ofertar(client, e).status_code == 200
    otro = service.crear_candidato(db, CandidatoCreateIn(paciente_anon_id="PAC-C-OTRO", especialidad_req="CARDIOLOGIA"),
        usuario=e.actor, ip="127.0.0.1")
    result = client.post(f"/cupos/{e.cupo.id_cupo_liberado}/reasignar", headers=e.headers,
                         json={"id_candidato": otro.id_candidato, "confirmacion_humana": True})
    assert result.status_code == 409
    assert db.scalar(select(Reasignacion).where(Reasignacion.id_cupo_liberado == e.cupo.id_cupo_liberado)) is None


@pytest.mark.parametrize("rol,estado", [(None, 401), ("TECNICO_IA", 403)])
def test_roles_no_autorizados_no_escriben(client, db, usuarios, escenario, rol, estado):
    e = escenario
    headers = cabecera(client, usuarios[rol]) if rol else {}
    base = f"/cupos/{e.cupo.id_cupo_liberado}/ofertas"
    for path, body in [(base, {"id_candidato": e.candidato.id_candidato}), (base + "/rechazo", None), (base + "/desistimiento", None)]:
        assert client.post(path, headers=headers, json=body).status_code == estado
    assert eventos(db, e.cupo.id_cupo_liberado) == []


@pytest.mark.parametrize("operacion", ["OFERTAR", "DESISTIR"])
def test_fallo_tras_flush_revierte_estados_eventos_y_proyeccion(client, db, escenario, monkeypatch, operacion):
    e = escenario
    if operacion == "DESISTIR":
        assert ofertar(client, e).status_code == 200
    original = service.registrar_evento
    commit = Mock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", commit)
    def fallar(db, **kwargs):
        event = original(db, **kwargs)
        if kwargs["accion"] == operacion:
            db.flush()
            raise RuntimeError("Fallo C tras flush")
        return event
    monkeypatch.setattr(service, "registrar_evento", fallar)
    with pytest.raises(RuntimeError, match="Fallo C"):
        if operacion == "OFERTAR":
            ofertar(client, e)
        else:
            client.post(f"/cupos/{e.cupo.id_cupo_liberado}/ofertas/desistimiento", headers=e.headers)
    commit.assert_not_called()
    db.rollback()  # reproduce cierre de get_db, sustituido por la fixture compartida
    db.expire_all()
    result = service.obtener_detalle_cupo(db, e.cupo.id_cupo_liberado)
    assert result.estado_cupo == ("DISPONIBLE" if operacion == "OFERTAR" else "EN_OFERTA")
    assert len(eventos(db, e.cupo.id_cupo_liberado)) == (0 if operacion == "OFERTAR" else 1)
    assert all(h.cierre is None for h in result.historial_ofertas)
