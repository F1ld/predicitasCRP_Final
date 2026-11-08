"""Fixtures CSV explícitos producidos por IA; sin imports cruzados de aplicaciones."""
from datetime import datetime
from pathlib import Path

from scripts.csv_preparado import leer_preparado

DIRECTORIO = Path(__file__).resolve().parent / "fixtures/generados-v1"


def cargar(nombre, *, normalizar=False):
    rows, _, _ = leer_preparado(DIRECTORIO, nombre)
    if not normalizar:
        return rows
    from app.modules.citas.importer import validar_fila
    from app.modules.citas.reglas import ESTADOS_DESENLACE
    output = []
    for row in rows:
        reg, derived = validar_fila(row, datetime.fromisoformat("2026-11-07T12:00:00-05:00"))
        output.append(reg.model_dump(mode="json") | derived | {"target_no_show": ESTADOS_DESENLACE.get(reg.estado_actual)})
    return output
