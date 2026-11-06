"""Delegación HTTP de lecturas/exportaciones, sin relajar permisos ni datos."""
from datetime import timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app.modules.auditoria.models import AuditoriaEvento
from app.modules.reportes import service as reportes
from tests.conftest import cabecera
from tests.intervenciones.conftest import HOY, crear_cita, crear_intervencion


@pytest.fixture
def headers(client, usuarios):
    return cabecera(client, usuarios["RECEPCION"])


def datos(db):
    cita = crear_cita(db)
    inter = crear_intervencion(db, cita, "ENTREGADA", fecha_hora_envio=HOY - timedelta(minutes=10))
    return cita, inter


def test_lecturas_intervenciones_conservan_filtros_pagina_y_detalle(client, db, headers):
    cita, inter = datos(db)
    response = client.get("/intervenciones", headers=headers, params={"id_cita": cita.id_cita,
        "estado_intervencion": "ENTREGADA", "desde": "2026-10-23", "hasta": "2026-10-25", "limite": 1})
    assert response.status_code == 200, response.text
    pagina = response.json()
    assert pagina["total"] == 1 and pagina["items"][0]["id_intervencion"] == inter.id_intervencion
    assert pagina["historial_intervenciones"] == pagina["items"]
    assert client.get("/intervenciones", headers=headers, params={"desplazamiento": 1}).json()["items"] == []
    detail = client.get(f"/intervenciones/{inter.id_intervencion}", headers=headers)
    assert detail.status_code == 200 and detail.json()["id_cita_externa"] == cita.id_cita_externa
    por_cita = client.get(f"/citas/{cita.id_cita}/intervenciones", headers=headers)
    assert por_cita.status_code == 200 and por_cita.json()[0]["id_intervencion"] == inter.id_intervencion
    assert client.get("/intervenciones/999999999", headers=headers).status_code == 404


def test_lectura_ia_no_ejecuta_inferencia(client, db, headers):
    cita, _ = datos(db)
    response = client.get(f"/ia/predicciones/{cita.id_cita}", headers=headers)
    assert response.status_code == 200 and len(response.json()) == 1
    assert response.json()[0]["nivel_riesgo"] == "ALTO"
    assert client.get("/ia/predicciones/999999999", headers=headers).json() == []


@pytest.mark.parametrize("formato", ["json", "csv", "xlsx"])
def test_alias_rep02_delega_sin_typeerror_y_conserva_export(client, db, headers, formato):
    datos(db)
    params = {"formato": formato, "canal_contacto": "WHATSAPP", "especialidad": "CARDIOLOGIA"}
    main = client.get("/reportes/rep-02", headers=headers, params=params)
    alias = client.get("/reportes/intervenciones", headers=headers, params=params)
    assert main.status_code == alias.status_code == 200
    assert main.headers["content-type"] == alias.headers["content-type"]
    if formato == "json":
        assert main.json() == alias.json()
    elif formato == "csv":
        assert main.content == alias.content
    else:
        from io import BytesIO
        from openpyxl import load_workbook
        assert main.content.startswith(b"PK") and alias.content.startswith(b"PK")
        assert list(load_workbook(BytesIO(main.content)).active.values) == list(load_workbook(BytesIO(alias.content)).active.values)
    exports = list(db.scalars(select(AuditoriaEvento).where(AuditoriaEvento.modulo == "REPORTES", AuditoriaEvento.accion == "EXPORT")))
    assert len(exports) == (0 if formato == "json" else 2)
    assert all(e.datos_after == {"formato": formato,
        "filtros": {"especialidad": "CARDIOLOGIA", "canal_contacto": "WHATSAPP"}} for e in exports)


@pytest.mark.parametrize("path", ["/reportes/rep-02", "/reportes/intervenciones"])
def test_reportes_conservan_roles(client, usuarios, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers=cabecera(client, usuarios["TECNICO_IA"])).status_code == 403


def test_export_fallido_no_confirma_auditoria(client, db, headers, monkeypatch):
    datos(db)
    commit = Mock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", commit)
    original = reportes.registrar_evento
    def fallar(db, **kwargs):
        event = original(db, **kwargs)
        db.flush()
        raise RuntimeError("Export C fallido")
    monkeypatch.setattr(reportes, "registrar_evento", fallar)
    with pytest.raises(RuntimeError, match="Export C"):
        client.get("/reportes/rep-02", headers=headers, params={"formato": "csv"})
    commit.assert_not_called()
    db.rollback()  # equivale al cierre de get_db; la fixture mantiene sesión compartida
    assert list(db.scalars(select(AuditoriaEvento).where(AuditoriaEvento.modulo == "REPORTES", AuditoriaEvento.accion == "EXPORT"))) == []
