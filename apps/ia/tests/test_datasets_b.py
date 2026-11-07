"""Bloque B: datos/CSV autónomos, sin alterar consumidores actuales."""
from copy import deepcopy
from datetime import date, datetime, timedelta
import json
import random
from pathlib import Path
import subprocess
import sys

import pytest

from datasets import operational_csv as csv_io
from datasets.synthetic import generar_citas, _sigmoide, _calibrar, _fecha_laborable
from datasets.temporal import LIMA, derivar_variables, FechasInconsistentes, FechaEnDomingo
from datasets.training_rows import fila_entrenamiento
from tests.test_contracts import validator


@pytest.fixture(scope="module")
def rows():
    return generar_citas(historicas=1000, proximas=80, semilla=42, desde=date(2026, 11, 6), con_invalidas=False)


def test_determinism_and_no_global_random_state(rows):
    state = random.getstate()
    assert rows == generar_citas(historicas=1000, proximas=80, semilla=42, desde=date(2026, 11, 6), con_invalidas=False)
    assert random.getstate() == state


def test_generated_rows_invariants_and_frozen_operational_contract(rows):
    assert len(rows) == 1080 and len({r["id_cita_externa"] for r in rows}) == 1080
    check = validator("data/cita-import-normalizada.v1.schema.json")
    for i, row in enumerate(rows):
        check.validate(csv_io.proyectar_operacional(row))
        appointment = datetime.fromisoformat(row["fecha_hora_cita"])
        registered = datetime.fromisoformat(row["fecha_registro_cita"])
        assert registered < appointment and appointment.weekday() != 6
        assert 0 <= row["antelacion_dias"] <= 60
        assert {k: row[k] for k in ("antelacion_dias", "franja_horaria", "dia_semana")} == derivar_variables(appointment, registered)
        if row["tipo_paciente"] == "NUEVO":
            assert row["asistencias_previas"] == row["inasistencias_previas"] == 0
        if i < 1000:
            assert row["target_no_show"] == int(row["estado_actual"] == "NO_SHOW")
        else:
            assert row["estado_actual"] == "RECIBIDA" and row["target_no_show"] is None


@pytest.mark.parametrize("historicas,proximas,invalidas,expected", [(0, 0, True, 0), (0, 5, False, 5), (5, 0, False, 5), (1, 1, True, 6)])
def test_small_empty_and_invalid_cases(historicas, proximas, invalidas, expected):
    rows = generar_citas(historicas=historicas, proximas=proximas, semilla=7, con_invalidas=invalidas)
    assert len(rows) == expected
    if invalidas and rows:
        assert rows[-4]["sede"] == "MIRAFLORES" and rows[-3]["especialidad"] == "DERMATOLOGIA"
        assert rows[-2]["id_cita_externa"] == rows[0]["id_cita_externa"]


def test_csv_projection_roundtrip_no_targets_or_derived_features(rows, tmp_path):
    before = deepcopy(rows)
    path = csv_io.guardar_csv_operacional(rows, ruta_nueva=tmp_path / "seed.csv")
    data = path.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data
    assert data.splitlines()[0].decode() == ",".join(csv_io.COLUMNAS)
    loaded = csv_io.leer_csv_operacional(path)
    assert loaded == [{k: str(r[k]) for k in csv_io.COLUMNAS} for r in rows]
    assert all("target_no_show" not in r and "antelacion_dias" not in r for r in loaded)
    assert before == rows
    with pytest.raises(FileExistsError):
        csv_io.guardar_csv_operacional(rows, ruta_nueva=path)


def test_csv_nulls_unicode_quoting_and_bom(rows, tmp_path):
    row = {**rows[-1], "medico": 'Dra. Núñez, "QA"\nTurno', "inasistencias_previas": None,
        "asistencias_previas": None, "reprogramaciones_prev": None, "estado_actual": None}
    path = tmp_path / "bom.csv"
    path.write_bytes(b"\xef\xbb\xbf" + csv_io.construir_csv_operacional([row]))
    loaded = csv_io.leer_csv_operacional(path)
    assert loaded[0]["medico"] == row["medico"]
    assert not set(("inasistencias_previas", "asistencias_previas", "reprogramaciones_prev", "estado_actual")) & loaded[0].keys()
    assert "None" not in path.read_text(encoding="utf-8-sig")


def test_csv_limits_and_no_output_on_invalid_data(rows, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="filas"):
        csv_io.guardar_csv_operacional([], ruta_nueva=tmp_path / "empty.csv")
    with pytest.raises(ValueError, match="básicos"):
        csv_io.guardar_csv_operacional([{}], ruta_nueva=tmp_path / "invalid.csv")
    monkeypatch.setattr(csv_io, "MAX_FILAS", 2)
    with pytest.raises(ValueError, match="5000"):
        csv_io.guardar_csv_operacional(rows[:3], ruta_nueva=tmp_path / "many.csv")
    monkeypatch.setattr(csv_io, "MAX_BYTES", 20)
    with pytest.raises(ValueError, match="2 MiB"):
        csv_io.guardar_csv_operacional(rows[:1], ruta_nueva=tmp_path / "big.csv")
    assert not list(tmp_path.iterdir())


def test_csv_destination_guard(rows, tmp_path):
    for path in (Path("relative.csv"), Path("/app/datasets/new.csv"), tmp_path / "not_csv.txt"):
        with pytest.raises(ValueError):
            csv_io.guardar_csv_operacional(rows[:1], ruta_nueva=path)
    link = tmp_path / "link.csv"
    link.symlink_to(tmp_path / "target.csv")
    with pytest.raises(ValueError):
        csv_io.guardar_csv_operacional(rows[:1], ruta_nueva=link)
    assert not (tmp_path / "target.csv").exists()


@pytest.mark.parametrize("kind", ["header", "extra", "missing", "empty", "too_many", "too_big", "utf8"])
def test_reader_rejects_invalid_physical_format(rows, tmp_path, monkeypatch, kind):
    path = tmp_path / "invalid.csv"
    data = csv_io.construir_csv_operacional(rows[:2])
    if kind == "header":
        data = b"wrong\nvalue\n"
    elif kind in ("extra", "missing"):
        header, rest = data.split(b"\n", 1)
        data = header + b"\n" + (b"x," * 14 if kind == "extra" else b"x,y") + b"\n"
    elif kind == "empty":
        data = data.split(b"\n", 1)[0] + b"\n"
    elif kind == "too_many":
        monkeypatch.setattr(csv_io, "MAX_FILAS", 1)
    elif kind == "too_big":
        monkeypatch.setattr(csv_io, "MAX_BYTES", 1)
    else:
        data = b"\xff"
    path.write_bytes(data)
    with pytest.raises((ValueError, UnicodeDecodeError)):
        csv_io.leer_csv_operacional(path)


def test_training_mapping_preserves_order_features_and_metadata(rows):
    check = validator("data/training-row.v1.schema.json")
    mapped = [fila_entrenamiento(r, corte=datetime(2026, 11, 6, 8, tzinfo=LIMA)) for r in rows[:1000]]
    assert [r["id_cita_externa"] for r in mapped] == [r["id_cita_externa"] for r in rows[:1000]]
    for raw, row in zip(rows, mapped):
        check.validate(row)
        assert row["features"] == {k: raw[k] for k in row["features"]}
        assert not {"target_no_show", "id_cita_externa", "estado_actual", "fecha_hora_cita"} & row["features"].keys()


@pytest.mark.parametrize("kind", ["target", "bool", "state", "id", "naive", "future", "catalog", "counter", "temporal", "nuevo"])
def test_training_mapping_rejects_incoherence(rows, kind):
    row = dict(rows[0])
    cut = datetime(2026, 11, 6, 8, tzinfo=LIMA)
    if kind == "target":
        row["target_no_show"] = 1 - row["target_no_show"]
    elif kind == "bool":
        row["target_no_show"] = bool(row["target_no_show"])
    elif kind == "state":
        row["estado_actual"] = "RECIBIDA"
    elif kind == "id":
        row["id_cita_externa"] = "REAL-1"
    elif kind == "naive":
        cut = cut.replace(tzinfo=None)
    elif kind == "future":
        cut = datetime(1900, 1, 1, tzinfo=LIMA)
    elif kind == "catalog":
        row["especialidad"] = "DERMATOLOGIA"
    elif kind == "counter":
        row["asistencias_previas"] = True
    elif kind == "temporal":
        row["antelacion_dias"] += 1
    else:
        row["tipo_paciente"] = "NUEVO"
        row["asistencias_previas"] = 1
    with pytest.raises(ValueError):
        fila_entrenamiento(row, corte=cut)


def test_temporal_boundaries_keep_lima_calendar_rule():
    at = datetime(2026, 11, 6, 13, tzinfo=LIMA)
    assert derivar_variables(at, at - timedelta(minutes=30))["franja_horaria"] == "TARDE"
    assert derivar_variables(at.replace(hour=12), at.replace(hour=14))["antelacion_dias"] == 0
    with pytest.raises(FechasInconsistentes):
        derivar_variables(at, at + timedelta(days=1))
    with pytest.raises(FechaEnDomingo):
        derivar_variables(datetime(2026, 11, 8, 9, tzinfo=LIMA), at)
    assert _sigmoide(-1000) == 0 and _sigmoide(1000) == 1
    assert abs(_calibrar([0.0], 0.5)) < 1e-10
    # Rango que incluye domingo: conserva muestreo por rechazo legacy.
    assert _fecha_laborable(random.Random(42), date(2026, 11, 8), date(2026, 11, 9)).weekday() != 6


def test_datasets_independent_and_not_imported_by_serving():
    code = '''import importlib.abc,sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname in ('app','training','fastapi','sqlalchemy','joblib','numpy') or fullname.startswith(('app.','training.')):
   raise AssertionError(fullname)
sys.meta_path.insert(0,Block())
from datasets.synthetic import generar_citas
from datasets import operational_csv,training_rows
assert len(generar_citas(historicas=1,proximas=1,con_invalidas=False)) == 2
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    code = '''import importlib.abc,sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname == 'datasets' or fullname.startswith('datasets.'):
   raise AssertionError('Serving importó datasets')
sys.meta_path.insert(0,Block())
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
 assert client.get('/health/ready').status_code == 200
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
