"""B.1: payloads históricos y atomicidad observados en PostgreSQL aislado."""
import pytest
from sqlalchemy import func, select
from unittest.mock import Mock

from app.modules.auditoria.models import AuditoriaEvento
from app.modules.citas import public as citas_public
from app.modules.citas.models import Cita, HistorialEstadoCita
from app.modules.intervenciones import service
from app.modules.intervenciones.models import Intervencion
from app.modules.lista_espera.models import CupoLiberado
from tests.conftest import cabecera
from tests.intervenciones.conftest import crear_cita, crear_intervencion


@pytest.fixture
def headers(client, usuarios):
    return cabecera(client, usuarios["RECEPCION"])


def eventos(db, modulo="INTERVENCION"):
    return list(db.scalars(select(AuditoriaEvento).where(AuditoriaEvento.modulo == modulo,
                      AuditoriaEvento.accion == "LIBERAR").order_by(AuditoriaEvento.id_log)))


@pytest.mark.parametrize("existente", [False, True])
def test_patch_liberacion_payload_historico_y_un_historial(client, headers, db, existente):
    cita = crear_cita(db)
    inter = crear_intervencion(db, cita)
    if existente:
        db.add(CupoLiberado(id_cita_origen=cita.id_cita, especialidad=cita.especialidad, medico=cita.medico,
                           fecha_hora_cupo=cita.fecha_hora_cita, estado_cupo="DISPONIBLE",
                           origen_liberacion="INTERVENCION_VOLUNTARIA"))
        db.flush()
    response = client.patch(f"/intervenciones/{inter.id_intervencion}", headers=headers,
                            json={"respuesta_paciente": "SOLICITA_LIBERACION"})
    assert response.status_code == 200, response.text
    cupos = list(db.scalars(select(CupoLiberado).where(CupoLiberado.id_cita_origen == cita.id_cita)))
    assert len(cupos) == 1
    cupo = cupos[0]
    audit = eventos(db)
    assert len(audit) == 1
    assert audit[0].entidad_afectada == "cupos_liberados" and audit[0].id_entidad == cupo.id_cupo_liberado
    assert audit[0].datos_before == {"estado_cita": "RECIBIDA"}
    assert audit[0].datos_after == {
        "id_cita_origen": cita.id_cita, "id_intervencion": inter.id_intervencion,
        "id_cupo_liberado": cupo.id_cupo_liberado, "estado_cita": "LIBERADA",
        "estado_cupo": "DISPONIBLE", "origen_liberacion": "INTERVENCION_VOLUNTARIA"}
    assert response.json()["id_cupo_liberado_generado"] == cupo.id_cupo_liberado
    assert db.scalar(select(func.count()).select_from(HistorialEstadoCita).where(
        HistorialEstadoCita.id_cita == cita.id_cita, HistorialEstadoCita.estado_nuevo == "LIBERADA")) == 1


def test_liberacion_explicita_payload_historico(client, headers, db):
    cita = crear_cita(db)
    inter = crear_intervencion(db, cita, "RESPONDIDA", "SOLICITA_LIBERACION")
    response = client.post(f"/intervenciones/{inter.id_intervencion}/liberar-cupo", headers=headers,
                           json={"motivo": "Cede el cupo"})
    assert response.status_code == 201, response.text
    audit = eventos(db)
    assert len(audit) == 1 and audit[0].id_entidad == response.json()["id_cupo_liberado"]
    assert audit[0].datos_before == {"estado_cita": "RECIBIDA"}
    assert audit[0].datos_after == {"id_cupo_liberado": response.json()["id_cupo_liberado"],
        "id_cita_origen": cita.id_cita, "estado_cupo": "DISPONIBLE",
        "origen_liberacion": "INTERVENCION_VOLUNTARIA", "motivo": "Cede el cupo"}


def test_cancelacion_conserva_evento_y_orden_historicos(client, headers, db):
    cita = crear_cita(db)
    response = client.post(f"/citas/{cita.id_cita}/estado", headers=headers,
                           json={"estado_nuevo": "CANCELADA", "liberar_cupo": True})
    assert response.status_code == 200, response.text
    cupo = db.scalar(select(CupoLiberado).where(CupoLiberado.id_cita_origen == cita.id_cita))
    audit = eventos(db, "REASIGNACION")
    assert len(audit) == 1 and audit[0].id_entidad == cupo.id_cupo_liberado
    assert audit[0].datos_before is None
    assert audit[0].datos_after == {"id_cita_origen": cita.id_cita, "estado_cupo": "DISPONIBLE",
        "origen_liberacion": "CANCELACION_EXTERNA", "fecha_hora_cupo": cita.fecha_hora_cita.isoformat()}
    cambio = db.scalar(select(AuditoriaEvento).where(AuditoriaEvento.modulo == "CITAS",
                        AuditoriaEvento.accion == "UPDATE", AuditoriaEvento.id_entidad == cita.id_cita))
    assert cambio.id_log < audit[0].id_log


@pytest.mark.parametrize("respuesta,estado", [("CONFIRMA", "CONFIRMADA"), ("SOLICITA_LIBERACION", "LIBERADA")])
def test_post_respuesta_sigue_sin_transicionar_cita(client, headers, db, respuesta, estado):
    cita = crear_cita(db)
    inter = crear_intervencion(db, cita, "ENTREGADA")
    response = client.post(f"/intervenciones/{inter.id_intervencion}/respuesta", headers=headers,
                           json={"respuesta_paciente": respuesta})
    assert response.status_code == 200, response.text
    db.refresh(cita)
    assert cita.estado_actual == "RECIBIDA"
    assert eventos(db) == []
    assert db.scalar(select(CupoLiberado).where(CupoLiberado.id_cita_origen == cita.id_cita)) is None


def test_fallo_auditoria_despues_de_crear_cupo_revierte_todo(client, headers, db, monkeypatch):
    cita = crear_cita(db)
    inter = crear_intervencion(db, cita)
    db.commit()
    id_cita, id_inter = cita.id_cita, inter.id_intervencion
    commit = Mock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", commit)
    original = service.workflow_intervenciones.registrar_evento
    def fallar(db, **kwargs):
        if kwargs["accion"] == "LIBERAR":
            raise RuntimeError("Fallo B.1 tras flush del cupo")
        return original(db, **kwargs)
    monkeypatch.setattr(service.workflow_intervenciones, "registrar_evento", fallar)
    with pytest.raises(RuntimeError, match="Fallo B.1"):
        client.patch(f"/intervenciones/{id_inter}", headers=headers,
                     json={"respuesta_paciente": "SOLICITA_LIBERACION"})
    commit.assert_not_called()
    # La fixture comparte sesión y reemplaza get_db; en producción su cierre
    # revierte la transacción fallida. Reproducir aquí ese límite de petición.
    db.rollback()
    db.expire_all()
    assert db.get(Cita, id_cita).estado_actual == "RECIBIDA"
    assert db.get(Intervencion, id_inter).estado_intervencion == "PENDIENTE"
    assert db.scalar(select(CupoLiberado).where(CupoLiberado.id_cita_origen == id_cita)) is None
    assert eventos(db) == []
    assert db.scalar(select(func.count()).select_from(HistorialEstadoCita).where(
        HistorialEstadoCita.id_cita == id_cita, HistorialEstadoCita.estado_nuevo == "LIBERADA")) == 0


def test_transicion_publica_sin_commit_permanece_reversible(db, usuarios):
    cita = crear_cita(db)
    db.commit()
    id_cita = cita.id_cita
    savepoint = db.begin_nested()
    result = citas_public.transicionar_cita_interno(db, id_cita, "CONFIRMADA",
        usuario=usuarios["RECEPCION"], ip="127.0.0.1")
    db.flush()
    assert result.estado_actual == "CONFIRMADA"
    savepoint.rollback()
    db.expire_all()
    assert db.get(Cita, id_cita).estado_actual == "RECIBIDA"
    assert db.scalar(select(func.count()).select_from(HistorialEstadoCita).where(
        HistorialEstadoCita.id_cita == id_cita, HistorialEstadoCita.estado_nuevo == "CONFIRMADA")) == 0
