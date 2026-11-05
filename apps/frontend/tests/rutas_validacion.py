"""Rutas de salida de QA, sin importar backend ni abrir conexiones."""
import os
from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parents[3]


def validar_base_pruebas(database: str | None, expected: str | None) -> None:
    if not expected or database != expected or not re.search(r"(^|[_-])(test|qa)([_-]|$)", database or "", re.I):
        raise ValueError("QA exige PREDICITAS_QA_DATABASE_NAME explícito e idéntico a una BD test/qa; nunca principal")


def crear_directorio_resultados(marca: str, base: Path | None = None) -> Path:
    if not re.fullmatch(r"[0-9a-f]{8}", marca):
        raise ValueError("Identificador QA inválido")
    base = base if base is not None else Path(os.environ.get(
        "PREDICITAS_TEST_RESULTS_DIR", str(RAIZ / "runtime/test-results"),
    ))
    if not base.is_absolute():
        raise ValueError("PREDICITAS_TEST_RESULTS_DIR debe ser absoluto")
    base = base.resolve()
    if base.is_relative_to(RAIZ) and not base.is_relative_to(RAIZ / "runtime/test-results"):
        raise ValueError("Salidas QA dentro del repositorio solo en runtime/test-results")
    destino = base / "diseno" / marca
    destino.mkdir(parents=True, exist_ok=False)
    return destino
