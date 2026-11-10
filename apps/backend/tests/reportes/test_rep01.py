from datetime import timedelta, timezone

import httpx
import pytest

from app.main import app
from app.modules.auth.public import usuario_actual
from app.modules.usuarios.identidad import por_id
from tests.conftest import cabecera
from tests.panel.conftest import AHORA, datos, sentencias, solo_base_pruebas  # noqa: F401

RUTA = "/reportes/rep-01"
FECHA = AHORA.date().isoformat()


@pytest.fixture
def recepcion(db, client, usuarios):
    identidad = por_id(db, usuarios["RECEPCION"].id_usuario)
    app.dependency_overrides[usuario_actual] = lambda: identidad
    return client


@pytest.mark.parametrize(("rol", "codigo"), [
    (None, 401), ("ADMINISTRADOR", 403), ("TECNICO_IA", 403), ("RECEPCION", 200),
])
def test_roles(client, usuarios, rol, codigo):
    headers = cabecera(client, usuarios[rol]) if rol else {}
    respuesta = client.get(RUTA, params={"fecha": FECHA}, headers=headers)
    assert respuesta.status_code == codigo, respuesta.text


@pytest.mark.parametrize("ruta", ["/reportes/rep-02", "/reportes/rep-03", "/reportes/reasignaciones"])
def test_reportes_existentes_siguen_disponibles_para_administracion(client, usuarios, ruta):
    headers = cabecera(client, usuarios["ADMINISTRADOR"])
    respuesta = client.get(ruta, headers=headers)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["filas"] == []


@pytest.mark.parametrize("params", [
    {}, {"fecha": "20261109"}, {"fecha": "2026-02-30"},
    {"fecha": "9999-12-31"}, {"fecha": FECHA, "nivel_riesgo": "URGENTE"},
    {"fecha": FECHA, "especialidad": "NEUROLOGIA"},
])
def test_filtros_invalidos(recepcion, params):
    assert recepcion.get(RUTA, params=params).status_code == 422


def test_rango_local_grupos_y_orden(recepcion, datos):
    inicio = AHORA.replace(hour=0)
    datos.cita(fecha_hora_cita=inicio - timedelta(seconds=1))
    primera = datos.cita(fecha_hora_cita=inicio.astimezone(timezone.utc), estado_actual="CANCELADA")
    empate = datos.cita(fecha_hora_cita=inicio)
    tarde = datos.cita(fecha_hora_cita=inicio + timedelta(hours=13))
    pediatria = datos.cita(fecha_hora_cita=inicio, especialidad="PEDIATRIA")
    datos.cita(fecha_hora_cita=inicio + timedelta(days=1))

    respuesta = recepcion.get(RUTA, params={"fecha": FECHA})
    assert respuesta.status_code == 200, respuesta.text
    reporte = respuesta.json()
    assert reporte["total"] == 4
    assert [(g["especialidad"], g["franja_horaria"], g["subtotal"]) for g in reporte["grupos"]] == [
        ("CARDIOLOGIA", "MANANA", 2), ("CARDIOLOGIA", "TARDE", 1), ("PEDIATRIA", "MANANA", 1),
    ]
    filas = [fila for grupo in reporte["grupos"] for fila in grupo["filas"]]
    assert [f["id_cita_externa"] for f in filas] == [
        primera.id_cita_externa, empate.id_cita_externa, tarde.id_cita_externa, pediatria.id_cita_externa,
    ]
    assert [f["hora"] for f in filas] == ["00:00:00", "00:00:00", "13:00:00", "00:00:00"]
    assert filas[0]["nivel_riesgo"] is None
    assert filas[0]["probabilidad_no_show"] is None
    assert filas[0]["estado_intervencion"] is None
    assert filas[0]["respuesta_paciente"] is None


def test_ultima_prediccion_e_intervencion_y_lectura_unica(recepcion, db, datos, sentencias, monkeypatch):
    cita = datos.cita()
    datos.cita(especialidad="PEDIATRIA")
    datos.pred(cita, "ALTO", fecha_hora_inferencia=AHORA)
    datos.pred(cita, "MEDIO", fecha_hora_inferencia=AHORA)
    datos.pred(cita, "BAJO", fecha_hora_inferencia=AHORA - timedelta(days=1))
    datos.inter(cita, "RESPONDIDA", fecha_hora_envio=AHORA, respuesta_paciente="CONFIRMA")
    datos.inter(cita, "ENVIADA", fecha_hora_envio=AHORA)
    datos.inter(cita, "FALLIDA", fecha_hora_envio=AHORA - timedelta(days=1))

    def prohibido(*args, **kwargs):
        pytest.fail("REP-01 debe consultar sin escrituras ni llamadas a IA")

    monkeypatch.setattr(db, "commit", prohibido)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", prohibido)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", prohibido)
    sentencias.clear()
    filtros = {"especialidad": "CARDIOLOGIA", "nivel_riesgo": "MEDIO"}
    respuesta = recepcion.get(RUTA, params={"fecha": FECHA, **filtros})
    assert respuesta.status_code == 200, respuesta.text
    assert len(sentencias) == 1
    assert sentencias[0].lstrip().upper().startswith("SELECT")
    reporte = respuesta.json()
    assert reporte["filtros"] == filtros
    assert reporte["total"] == reporte["grupos"][0]["subtotal"] == 1
    fila, = reporte["grupos"][0]["filas"]
    assert fila["nivel_riesgo"] == "MEDIO"
    assert fila["probabilidad_no_show"] == 0.4
    assert fila["estado_intervencion"] == "ENVIADA"
    assert fila["respuesta_paciente"] is None

    for params in ({"fecha": FECHA, "nivel_riesgo": "ALTO"}, {"fecha": "2026-11-12"}):
        vacio = recepcion.get(RUTA, params=params)
        assert vacio.status_code == 200, vacio.text
        assert vacio.json()["total"] == 0
        assert vacio.json()["grupos"] == []
