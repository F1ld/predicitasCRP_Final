"""Bloque A: entrenamiento offline explícito y separación respecto de serving."""
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import joblib
import numpy as np
import pytest

from app.config import MODEL_PATH
from app.core.features import FEATURES_ENTRADA_MODELO
from app.core.model_registry import registry
from training import evaluation, metrics, preprocessing, serialization, trainer

NOW = datetime(2026, 11, 6, 8, tzinfo=timezone.utc)
IDENTITY = {"version_modelo": "QA_A_CANDIDATE", "version_dataset": "QA_A_FIXTURE", "fecha_entrenamiento": NOW}


@pytest.fixture(scope="module")
def registros():
    # Fixture de prueba únicamente: no es extracción del generador/dataset oficial.
    return [{"id_cita_externa": f"QA-A-{n}", "especialidad": ["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"][n % 3],
        "tipo_paciente": "CONTINUADOR", "canal_origen": ["WEB", "CALL_CENTER", "PRESENCIAL"][n % 3],
        "franja_horaria": ["MANANA", "TARDE"][n % 2], "dia_semana": ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO"][n % 6],
        "antelacion_dias": n % 30, "inasistencias_previas": n % 5, "asistencias_previas": (n // 5) % 6,
        "reprogramaciones_prev": n % 4, "target_no_show": int(n % 5 >= 3)} for n in range(1000)]


@pytest.fixture(scope="module")
def resultado(registros):
    before = deepcopy(registros)
    state = registry._state
    digest = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    result = trainer.entrenar(registros, **IDENTITY)
    assert before == registros
    assert registry._state is state
    assert hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() == digest
    return result


def test_real_training_and_split(resultado, registros):
    split = resultado.particiones
    assert [len(split.train), len(split.val), len(split.test)] == [700, 150, 150]
    assert set(split.train) | set(split.val) | set(split.test) == set(range(1000))
    assert not (set(split.train) & set(split.val) or set(split.train) & set(split.test) or set(split.val) & set(split.test))
    other = evaluation.particionar(np.array([r["target_no_show"] for r in registros]))
    for field in ("train", "val", "test"):
        assert np.array_equal(getattr(split, field), getattr(other, field))
    artifact = resultado.artefacto
    assert artifact["metricas_test"]["f1_score"] >= 0.82
    assert artifact["dataset_info"]["control_leakage"]["aprobado"] is True
    assert artifact["fecha_entrenamiento"] == NOW.isoformat()
    assert artifact["version_modelo"] == IDENTITY["version_modelo"]
    assert artifact["dataset_info"]["version_dataset"] == IDENTITY["version_dataset"]


def test_preprocessing_keeps_legacy_order_and_defaults():
    raw = {"especialidad": "cardiologia", "tipo_paciente": "nuevo", "canal_origen": "web",
        "franja_horaria": "manana", "dia_semana": "lunes", "antelacion_dias": "15", "inasistencias_previas": None}
    matrix, snapshots = preprocessing.construir_matriz([raw])
    assert matrix.dtype == object and matrix.shape == (1, 11)
    assert matrix.tolist() == [[snapshots[0][key] for key in FEATURES_ENTRADA_MODELO]]
    assert matrix.tolist()[0][:6] == [15, 0, 0, 0, 0.0, 1]
    assert snapshots[0]["especialidad"] == "CARDIOLOGIA"


def test_hyperparameters_frozen():
    baseline, principal = trainer.crear_modelos()
    assert {k: baseline.named_steps["clf"].get_params()[k] for k in ("C", "max_iter", "random_state")} == {"C": 0.05, "max_iter": 1000, "random_state": 42}
    expected = {"objective": "binary", "n_estimators": 220, "learning_rate": 0.045, "num_leaves": 23,
        "max_depth": 5, "min_child_samples": 12, "subsample": 0.85, "colsample_bytree": 0.85,
        "class_weight": "balanced", "random_state": 42, "verbose": -1}
    assert {k: principal.named_steps["clf"].get_params()[k] for k in expected} == expected
    prep = principal.named_steps["prep"]
    assert prep.remainder == "drop"
    assert prep.transformers[0][2] == list(range(6)) and prep.transformers[1][2] == list(range(6, 11))


@pytest.mark.parametrize("patch", [
    {"version_modelo": ""}, {"version_modelo": "LightGBM_v1.0.0"},
    {"version_dataset": " "}, {"version_dataset": "x" * 101},
    {"fecha_entrenamiento": datetime(2026, 11, 6)}, {"fecha_entrenamiento": None},
])
def test_identity_must_be_explicit_and_not_active(patch):
    with pytest.raises(ValueError):
        trainer.entrenar([], **{**IDENTITY, **patch})


def test_requires_minimum_data_before_fit(monkeypatch):
    create = Mock()
    monkeypatch.setattr(trainer, "crear_modelos", create)
    with pytest.raises(ValueError, match="1,000"):
        trainer.entrenar([], **IDENTITY)
    create.assert_not_called()


def test_f1_gate_not_weakened(registros, monkeypatch):
    baseline, principal = Mock(), Mock()
    for model in (baseline, principal):
        model.predict_proba.side_effect = lambda x: np.tile([0.5, 0.5], (len(x), 1))
    monkeypatch.setattr(trainer, "crear_modelos", lambda: (baseline, principal))
    monkeypatch.setattr(trainer, "calcular_metricas", lambda *args: {"f1_score": 0.81})
    with pytest.raises(RuntimeError, match="0.82"):
        trainer.entrenar(registros, **IDENTITY)
    assert baseline.fit.call_args.args[0].shape == (700, 11)
    assert principal.fit.call_args.args[0].shape == (700, 11)


@pytest.mark.parametrize("kind", ["overlap", "negative", "nuevo", "forbidden"])
def test_leakage_guards_unchanged(registros, kind, monkeypatch):
    rows = deepcopy(registros)
    split = evaluation.particionar(np.array([r["target_no_show"] for r in rows]))
    if kind == "overlap":
        rows[split.val[0]]["id_cita_externa"] = rows[split.train[0]]["id_cita_externa"]
    elif kind == "negative":
        rows[0]["antelacion_dias"] = -1
    elif kind == "nuevo":
        rows[1]["tipo_paciente"] = "NUEVO"
    else:
        monkeypatch.setattr(evaluation, "FEATURES_ENTRADA_MODELO", [*FEATURES_ENTRADA_MODELO, "target_no_show"])
    with pytest.raises(ValueError):
        evaluation.verificar_sin_data_leakage(rows, split.train, split.val, split.test)


def test_metrics_threshold_is_greater_or_equal_not_risk_classifier():
    result = metrics.calcular_metricas(np.array([0, 1]), np.array([0.45, 0.45]), 0.45)
    assert result == {"umbral": 0.45, "f1_score": 0.6667, "precision": 0.5, "recall": 1.0,
        "roc_auc": 0.5, "pr_auc": 0.5, "matriz_confusion": {"tn": 0, "fp": 1, "fn": 0, "tp": 1}}


def test_equity_excludes_single_class_groups():
    rows = [{"especialidad": "A", "tipo_paciente": "NUEVO", "franja_horaria": "MANANA"},
        {"especialidad": "A", "tipo_paciente": "CONTINUADOR", "franja_horaria": "MANANA"},
        {"especialidad": "B", "tipo_paciente": "CONTINUADOR", "franja_horaria": "TARDE"}]
    result = metrics.auditar_equidad_subgrupos(rows, np.array([0, 1, 0]), np.array([0.1, 0.9, 0.2]), 0.45)
    assert set(result["especialidad"]) == {"A"}
    assert set(result["tipo_paciente"]) == {"CONTINUADOR"}
    assert set(result["franja_horaria"]) == {"MANANA"}


def test_serialization_exclusive_and_roundtrip(resultado, registros, tmp_path):
    matrix, _ = preprocessing.construir_matriz(registros)
    path = serialization.guardar_candidato(resultado, directorio_nuevo=tmp_path / "candidate")
    loaded = joblib.load(path)  # Candidato creado por esta misma prueba, no archivo externo.
    assert np.array_equal(loaded["pipeline"].predict_proba(matrix), resultado.artefacto["pipeline"].predict_proba(matrix))
    with pytest.raises(FileExistsError):
        serialization.guardar_candidato(resultado, directorio_nuevo=path.parent)
    assert path.name == "candidate.joblib"
    code = '''import importlib.abc,sys,joblib
class NoTraining(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname == 'training' or fullname.startswith('training.'):
   raise AssertionError('El candidato serializado depende de training')
sys.meta_path.insert(0,NoTraining())
artifact=joblib.load(sys.argv[1])
assert artifact['pipeline'].n_features_in_ == 11
assert not any(k == 'training' or k.startswith('training.') for k in sys.modules)
'''
    result = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_serialization_blocks_active_registry(resultado, tmp_path, monkeypatch):
    monkeypatch.setattr(serialization, "MODEL_REGISTRY_DIR", tmp_path / "active")
    for target in (tmp_path / "active", tmp_path / "active/subdir"):
        with pytest.raises(ValueError, match="registry"):
            serialization.guardar_candidato(resultado, directorio_nuevo=target)
    modified = dict(resultado.artefacto, version_modelo="LightGBM_v1.0.0")
    with pytest.raises(ValueError, match="activa"):
        serialization.guardar_candidato(trainer.Entrenamiento(modified, resultado.particiones), directorio_nuevo=tmp_path / "other")
    assert not list(tmp_path.iterdir())


def test_serving_cannot_import_or_execute_training():
    # Proceso fresco: la colección pytest sí puede importar entrenamiento offline.
    code = '''import importlib.abc,sys
from unittest.mock import patch
class NoTraining(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname == 'training' or fullname.startswith('training.'):
   raise AssertionError('Serving intentó importar entrenamiento')
sys.meta_path.insert(0,NoTraining())
from fastapi.testclient import TestClient
with patch('sklearn.pipeline.Pipeline.fit', side_effect=AssertionError('fit desde serving')), patch('joblib.dump', side_effect=AssertionError('escritura desde serving')):
 from app.main import app
 with TestClient(app) as client:
  assert client.get('/health/ready').status_code == 200
assert not any(k == 'training' or k.startswith('training.') for k in sys.modules)
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_offline_import_does_not_train_load_write_or_require_key():
    code = '''import os,sys
from unittest.mock import patch
os.environ.pop('IA_API_KEY',None)
with patch('sklearn.pipeline.Pipeline.fit', side_effect=AssertionError('fit por import')), patch('joblib.dump', side_effect=AssertionError('dump por import')), patch('joblib.load', side_effect=AssertionError('load por import')):
 import training.trainer,training.metrics,training.evaluation,training.serialization
assert 'app.main' not in sys.modules and 'app.core.model_registry' not in sys.modules
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_offline_imports_have_no_operational_or_serving_coordinator_dependency():
    for path in Path("/app/training").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(n.startswith(("sqlalchemy", "psycopg", "app.modules", "app.main", "app.core.model_registry")) for n in names), path
