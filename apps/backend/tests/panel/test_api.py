import ast
from pathlib import Path

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.modules.auth.public import usuario_actual
from app.modules.panel import consultas
from app.modules.usuarios.identidad import por_id
from tests.conftest import cabecera


@pytest.mark.parametrize("ruta", ["/panel/resumen", "/panel/pendientes?tipo=OFERTAS_EN_CURSO"])
@pytest.mark.parametrize(("rol", "codigo"), [(None, 401), ("TECNICO_IA", 403),
                                             ("RECEPCION", 200), ("ADMINISTRADOR", 200)])
def test_roles_y_sesion(client, usuarios, reloj_panel, ruta, rol, codigo):
    headers = cabecera(client, usuarios[rol]) if rol else {}
    r = client.get(ruta, headers=headers)
    assert r.status_code == codigo, r.text
    if codigo != 200:
        assert set(r.json()["error"]) == {"codigo", "mensaje", "campos"}
    else:
        assert r.json()["fecha"] == "2026-11-09"
        assert r.json()["zona_horaria"] == "America/Lima"


@pytest.mark.parametrize("query", ["fecha=incorrecta", "fecha=2026-02-30", "fecha=9999-12-31",
                                     "especialidad=NEUROLOGIA", "especialidad=TODAS"])
def test_validacion_filtros(client, usuarios, db, query):
    app.dependency_overrides[usuario_actual] = lambda: por_id(db, usuarios["RECEPCION"].id_usuario)
    r = client.get(f"/panel/resumen?{query}")
    assert r.status_code == 422, r.text
    assert set(r.json()["error"]) == {"codigo", "mensaje", "campos"}


@pytest.mark.parametrize("query", ["", "tipo=INVALIDO", "tipo=OFERTAS_EN_CURSO&limite=0",
    "tipo=OFERTAS_EN_CURSO&limite=101", "tipo=OFERTAS_EN_CURSO&desplazamiento=-1",
    "tipo=OFERTAS_EN_CURSO&limite=abc", "tipo=OFERTAS_EN_CURSO&fecha=invalid"])
def test_validacion_pendientes(client, usuarios, db, query):
    app.dependency_overrides[usuario_actual] = lambda: por_id(db, usuarios["RECEPCION"].id_usuario)
    r = client.get(f"/panel/pendientes?{query}")
    assert r.status_code == 422, r.text
    assert "error" in r.json()


def test_contrato_sin_ia_sin_escrituras_y_con_snapshot_por_respuesta(
    client, usuarios, db, datos, reloj_panel, sentencias, monkeypatch,
):
    identidad = por_id(db, usuarios["RECEPCION"].id_usuario)
    app.dependency_overrides[usuario_actual] = lambda: identidad
    def prohibido(*args, **kwargs):
        pytest.fail("El panel no debe contactar al motor IA ni confirmar escrituras")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", prohibido)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", prohibido)
    monkeypatch.setattr(db, "commit", prohibido)
    c = datos.cita()
    datos.pred(c)
    sentencias.clear()
    r = client.get("/panel/resumen")
    assert r.status_code == 200, r.text
    assert r.json()["citas"]["total"] == 1
    assert r.json()["pendientes"]["citas_sin_intervencion"] == 1
    assert len(sentencias) == 1
    sentencias.clear()
    r = client.get("/panel/pendientes?tipo=CITAS_SIN_INTERVENCION")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == len(body["items"]) == 1
    assert isinstance(body["items"][0]["probabilidad_no_show"], float)
    assert body["items"][0]["tipo"] == "CITAS_SIN_INTERVENCION"
    assert len(sentencias) == 1
    assert all(sql.lstrip().upper().startswith("WITH") for sql in sentencias)
    assert "password" not in r.text and "token" not in r.text


@pytest.mark.parametrize("tipo", ["INTERVENCIONES_SIN_RESPUESTA", "OFERTAS_EN_CURSO"])
def test_contrato_items_tipados(client, usuarios, db, datos, reloj_panel, tipo):
    identidad = por_id(db, usuarios["RECEPCION"].id_usuario)
    app.dependency_overrides[usuario_actual] = lambda: identidad
    if tipo == "OFERTAS_EN_CURSO":
        datos.cupo("EN_OFERTA")
    else:
        datos.inter(datos.cita())
    r = client.get(f"/panel/pendientes?tipo={tipo}")
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["tipo"] == tipo


def test_error_db_no_se_oculta_con_ceros(client, usuarios, db, monkeypatch):
    identidad = por_id(db, usuarios["RECEPCION"].id_usuario)
    app.dependency_overrides[usuario_actual] = lambda: identidad
    def falla(*args, **kwargs):
        raise SQLAlchemyError("Fallo simulado en base de pruebas")
    monkeypatch.setattr(consultas, "resumen", falla)
    # El manejador vigente puede propagar al TestClient, pero jamás devolver 200 con ceros.
    with pytest.raises(SQLAlchemyError):
        client.get("/panel/resumen")


def test_openapi_incremental_y_union_discriminada():
    api = app.openapi()
    assert set(api["paths"]["/panel/resumen"]) == {"get"}
    assert set(api["paths"]["/panel/pendientes"]) == {"get"}
    schema = api["components"]["schemas"]["PanelPendientesOut"]
    assert schema["properties"]["items"]["items"]["discriminator"]["propertyName"] == "tipo"
    assert "/citas" in api["paths"] and "/reportes/rep-03" in api["paths"]


def test_frontera_lectura_compuesta_del_panel():
    carpeta = Path(__file__).resolve().parents[2] / "app/modules/panel"
    modelos_permitidos = {"app.modules.citas.models", "app.modules.ia.models",
                          "app.modules.intervenciones.models", "app.modules.lista_espera.models"}
    for archivo in carpeta.glob("*.py"):
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.ImportFrom) and (nodo.module or "").endswith(".models"):
                assert archivo.name == "consultas.py" and nodo.module in modelos_permitidos
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute):
                assert nodo.func.attr not in {"commit", "flush", "add", "add_all", "delete", "with_for_update"}
