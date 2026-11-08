"""Integridad y consumo explícito de datos QA sin ejecutar el generador legacy."""
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from scripts.csv_preparado import leer_preparado
from scripts.exportar_csv import exportar_csv
from tests.datos_preparados import DIRECTORIO, cargar


@pytest.mark.parametrize("name,count", [("citas", 44), ("rendimiento", 5000), ("predictor", 1080)])
def test_versioned_fixture_integrity(name, count):
    assert len(cargar(name)) == count


def test_exporter_has_no_generation_fallback(tmp_path, monkeypatch):
    from datetime import date
    monkeypatch.delenv("PREDICITAS_EXPORT_FIXTURES_DIR", raising=False)
    path = tmp_path / "sample.csv"
    with pytest.raises(ValueError, match="fuente"):
        exportar_csv(path, filas=3, semilla=7, fecha_referencia=date(2026, 11, 5))
    assert not path.exists()
    exportar_csv(path, filas=3, semilla=7, fecha_referencia=date(2026, 11, 5), fuente=DIRECTORIO)
    assert hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == "030259575c89a141f4ab57c6cd4c25e4cb5227a34b4827a2fe2adb7995f1e1f4"


@pytest.mark.parametrize("kind", ["hash", "count", "parameters", "traversal"])
def test_bad_source_rejected_without_writing(tmp_path, kind):
    folder = tmp_path / "source"
    folder.mkdir()
    shutil.copyfile(DIRECTORIO / "muestra3.csv", folder / "muestra3.csv")
    manifest = json.loads((DIRECTORIO / "manifest.json").read_text(encoding="utf-8"))
    if kind == "hash":
        (folder / "muestra3.csv").write_bytes(b"corrupt")
    elif kind == "count":
        manifest["files"]["muestra3"]["rows"] += 1
    elif kind == "parameters":
        manifest["version"] = 99
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        leer_preparado(folder, "../muestra3" if kind == "traversal" else "muestra3")


def test_no_consumer_imports_legacy_generator():
    import ast
    for name in ("scripts/exportar_csv.py", "tests/citas/test_citas.py", "tests/citas/test_m02_contrato.py", "tests/test_ia_predictor.py"):
        path = Path(__file__).resolve().parents[1] / name
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.ImportFrom):
                assert node.module != "app.modules.citas.synthetic"
