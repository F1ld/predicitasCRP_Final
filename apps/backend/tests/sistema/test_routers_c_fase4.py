"""Bloque C: routers como adaptadores y proyección pura de bitácora."""
import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.modules.auditoria.public import EventoEntidad
from app.modules.lista_espera.ofertas import proyectar

APP = Path(__file__).resolve().parents[2] / "app"


@pytest.mark.parametrize("router", sorted((APP / "modules").glob("*/router.py")), ids=lambda p: p.parent.name)
def test_routers_sin_persistencia_ni_imports_privados(router):
    tree = ast.parse(router.read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names = (node.module or "").split(".") + [a.name for a in node.names]
            assert not any(n in {"models", "repository"} for n in names), router
            assert not ((node.module or "").startswith("sqlalchemy") and node.module != "sqlalchemy.orm")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"commit", "rollback", "flush", "execute", "scalar", "scalars", "query", "refresh"}
            if isinstance(node.func.value, ast.Name):
                assert not (node.func.value.id == "db" and node.func.attr in {"get", "add", "delete"})
                assert not (node.func.value.id == "service" and node.func.attr.startswith("_"))


def evento(id_log, accion, datos):
    return EventoEntidad(id_log, accion, 1, datetime(2026, 11, 6, tzinfo=timezone.utc), datos)


def test_historial_proyecta_cierres_por_identidad_no_por_timestamp():
    # Mismos timestamps dentro de transacciones: el ID y la referencia son decisivos.
    rows = [evento(1, "OFERTAR", {"id_candidato": 5}),
            evento(2, "RECHAZAR", {"id_oferta": 1, "cierre": "RECHAZA"}),
            evento(3, "OFERTAR", {"id_candidato": 6}),
            evento(4, "DESISTIR", {"id_oferta": 1, "cierre": "SIN_RESPUESTA"})]
    result = proyectar(rows)
    assert result.vigente.id_log == 3
    assert [h.cierre for h in result.historial] == ["RECHAZA", None]
    rows.append(evento(5, "CERRAR_OFERTA", {"id_oferta": 3, "cierre": "REASIGNADO"}))
    result = proyectar(rows)
    assert result.vigente is None
    assert [h.cierre for h in result.historial] == ["RECHAZA", "REASIGNADO"]


def test_evento_legacy_sin_identidad_no_inventa_candidato():
    result = proyectar([evento(1, "OFERTAR", {})])
    assert result.vigente is None and result.historial == ()
