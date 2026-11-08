"""CLI trasladado a IA: contrato de muestras preservado sin backend ni BD."""
from datetime import date
import csv
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from datasets import exportar_csv as exporter


def create(path, **changes):
    return exporter.exportar_csv(path, **(dict(filas=3, semilla=7, fecha_referencia=date(2026, 11, 5)) | changes))


def test_frozen_csv_parity_and_four_intentional_rejections(tmp_path):
    path = create(tmp_path / "new/sub/muestra.csv")
    data = path.read_bytes()
    assert hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == "030259575c89a141f4ab57c6cd4c25e4cb5227a34b4827a2fe2adb7995f1e1f4"
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames) == exporter.COLUMNAS
        rows = list(reader)
    assert len(rows) == 7 and all(len(row) == 13 for row in rows)
    assert rows[-4]["sede"] == "MIRAFLORES" and rows[-3]["especialidad"] == "DERMATOLOGIA"
    assert rows[-2]["id_cita_externa"] == rows[0]["id_cita_externa"]


def test_reproducible_and_explicit_date(tmp_path):
    first = create(tmp_path / "a.csv").read_bytes()
    assert create(tmp_path / "b.csv").read_bytes() == first
    assert create(tmp_path / "c.csv", fecha_referencia=date(2026, 11, 6)).read_bytes() != first


def test_no_overwrite_or_race(tmp_path, monkeypatch):
    path = tmp_path / "a.csv"
    path.write_bytes(b"preservar")
    with pytest.raises(FileExistsError):
        create(path)
    monkeypatch.setattr(exporter, "resolver_salida", lambda p: p)
    with pytest.raises(FileExistsError):
        create(path)
    assert path.read_bytes() == b"preservar"


@pytest.mark.parametrize("name", ["relative.csv", "sub/file.csv"])
def test_absolute_destination_required(name):
    with pytest.raises(ValueError, match="absoluta"):
        create(Path(name))


@pytest.mark.parametrize("name", ["a.json", "a", "a.joblib"])
def test_csv_extension_required(tmp_path, name):
    with pytest.raises(ValueError, match=".csv"):
        create(tmp_path / name)


@pytest.mark.parametrize("count", [0, -1])
def test_positive_rows_required(tmp_path, count):
    with pytest.raises(ValueError, match="mayor"):
        create(tmp_path / "a.csv", filas=count)


def test_code_directory_is_read_only_target():
    with pytest.raises(ValueError, match="código"):
        create(exporter.APP_DIR / "forbidden.csv")


def test_cli_from_other_cwd(tmp_path):
    output = tmp_path / "sub/a.csv"
    env = dict(os.environ, PYTHONPATH=str(exporter.APP_DIR))
    result = subprocess.run([sys.executable, "-B", "-m", "datasets.exportar_csv", "--salida", str(output),
        "--fecha-referencia", "2026-11-05", "--filas", "2"], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "6 filas (4 de rechazo intencional)" in result.stdout
    assert output.exists()
    assert subprocess.run([sys.executable, "-m", "datasets.exportar_csv"], cwd=tmp_path, env=env,
                          capture_output=True).returncode == 2
