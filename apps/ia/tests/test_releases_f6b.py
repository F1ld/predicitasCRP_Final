"""Registry temporal, modelos propios y legacy RO; sin promoción del entorno."""
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import joblib
import pytest

from app.config import MODEL_PATH
from app.core.inference import ejecutar_inferencia_individual
from app.schemas import FeaturesPreCita
from management import releases as r
from training.pipeline import generar, entrenar_candidato, sha, bytes_json

CONTRACTS = Path("/contracts")
FECHA = datetime(2026, 11, 7, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def candidate(tmp_path_factory):
    parent = tmp_path_factory.mktemp("release-candidate")
    dataset = generar(version_dataset="b-data", semilla=42, fecha_corte=date(2026, 10, 29),
        generado_en=FECHA, fuente="SINTETICO_GENERADO", directorio=parent,
        contracts=CONTRACTS, proximas=0)
    return entrenar_candidato(dataset=dataset, version_modelo="b-model", fecha=FECHA,
                              directorio=parent, contracts=CONTRACTS)


def promote(root, candidate, **changes):
    return r.promote(**(dict(registry=root, candidate=candidate,
        manifest_sha256=sha((candidate / "manifest.json").read_bytes()),
        approved_version="b-model", expected="VACIO", contracts=CONTRACTS) | changes))


def test_promote_parity_and_rollback_to_legacy(candidate, tmp_path, sample_features):
    original = MODEL_PATH.read_bytes()
    legacy = r.import_legacy(registry=tmp_path, model=MODEL_PATH, expected="VACIO")
    active = promote(tmp_path, candidate, expected="legacy-v1")
    state = r.read_state(tmp_path)
    assert state == {"active": active, "previous": legacy}
    served = r.validate_release(tmp_path, active)
    artifact = joblib.load(candidate / "candidate.joblib")
    for counter in range(25):
        features = FeaturesPreCita(**(sample_features | {"antelacion_dias": counter}))
        a = ejecutar_inferencia_individual(artifact["pipeline"], features)
        b = ejecutar_inferencia_individual(served.pipeline, features)
        assert a == b
    assert served.get_dataset_manifest()["proposito"] == "TRAINING_RUN"
    assert r.rollback(registry=tmp_path, expected="b-model", target_release="legacy-v1",
                      approval_sha256=legacy["approval_sha256"]) == legacy
    assert r.validate_release(tmp_path, r.read_state(tmp_path)["active"]).version_modelo == "LightGBM_v1.0.0"
    assert r.rollback(registry=tmp_path, expected="legacy-v1") == active
    assert MODEL_PATH.read_bytes() == original


@pytest.mark.parametrize("file", ["manifest.json", "candidate.joblib", "dataset-manifest.json", "metrics.json"])
def test_tampering_rejected_before_deserialization(candidate, tmp_path, file):
    source = tmp_path / "candidate"
    source.mkdir()
    for path in candidate.iterdir():
        (source / path.name).write_bytes(path.read_bytes())
    approved_hash = sha((source / "manifest.json").read_bytes())
    with (source / file).open("ab") as stream:
        stream.write(b" ")
    with patch.object(r.joblib, "load", side_effect=AssertionError("no deserializar")):
        with pytest.raises(ValueError, match="Hash"):
            promote(tmp_path, source, manifest_sha256=approved_hash)
    assert not (tmp_path / "state.json").exists()


@pytest.mark.parametrize("kind", ["dependencies", "threshold", "version", "f1", "dataset", "artifact-path"])
def test_incompatible_manifest_rejected(candidate, tmp_path, kind):
    source = tmp_path / "candidate"
    source.mkdir()
    for path in candidate.iterdir():
        (source / path.name).write_bytes(path.read_bytes())
    manifest = json.loads((source / "manifest.json").read_bytes())
    if kind == "dependencies":
        manifest["dependencias"]["numpy"] = "0.0"
    elif kind == "threshold":
        manifest["umbrales"]["alto"] = 0.9
    elif kind == "version":
        manifest["version_modelo"] = "wrong"
    elif kind == "f1":
        manifest["metricas_test"]["f1_score"] = 0.1
    elif kind == "dataset":
        manifest["version_dataset"] = "wrong"
    else:
        manifest["artifact"]["relative_path"] = "../evil.joblib"
    (source / "manifest.json").write_bytes(bytes_json(manifest))
    with patch.object(r.joblib, "load", side_effect=AssertionError("no deserializar")):
        with pytest.raises(Exception) as error:
            promote(tmp_path, source)
        assert not isinstance(error.value, AssertionError)
    assert not (tmp_path / "state.json").exists()


def test_no_overwrite_and_stale_state(candidate, tmp_path):
    promote(tmp_path, candidate)
    before = (tmp_path / "state.json").read_bytes()
    with pytest.raises(ValueError, match="activo cambió"):
        promote(tmp_path, candidate)
    with pytest.raises(FileExistsError):
        promote(tmp_path, candidate, expected="b-model")
    assert (tmp_path / "state.json").read_bytes() == before
    with pytest.raises(ValueError, match="anterior"):
        r.rollback(registry=tmp_path, expected="b-model")


def test_single_writer_lock(candidate, tmp_path):
    lock = tmp_path / ".writer.lock"
    lock.write_text("another writer")
    with pytest.raises(FileExistsError):
        promote(tmp_path, candidate)
    assert lock.read_text() == "another writer"


def test_targeted_rollback_requires_trusted_hash(candidate, tmp_path):
    promote(tmp_path, candidate)
    before = (tmp_path / "state.json").read_bytes()
    with pytest.raises(ValueError):
        r.rollback(registry=tmp_path, expected="b-model", target_release="b-model")
    with pytest.raises(ValueError):
        r.rollback(registry=tmp_path, expected="b-model", target_release="b-model", approval_sha256="0" * 64)
    with pytest.raises(ValueError):
        r.rollback(registry=tmp_path, expected="b-model", target_release="b-model", approval_sha256="")
    assert (tmp_path / "state.json").read_bytes() == before


def test_atomic_replace_failure_preserves_previous(candidate, tmp_path):
    r.import_legacy(registry=tmp_path, model=MODEL_PATH, expected="VACIO")
    before = (tmp_path / "state.json").read_bytes()
    with patch.object(r.os, "replace", side_effect=OSError("simulated")):
        with pytest.raises(OSError):
            promote(tmp_path, candidate, expected="legacy-v1")
    assert (tmp_path / "state.json").read_bytes() == before
    assert r.validate_release(tmp_path, r.read_state(tmp_path)["active"]).is_ready
    assert not (tmp_path / ".writer.lock").exists()


def test_failed_rollback_leaves_current(candidate, tmp_path):
    r.import_legacy(registry=tmp_path, model=MODEL_PATH, expected="VACIO")
    promote(tmp_path, candidate, expected="legacy-v1")
    before = (tmp_path / "state.json").read_bytes()
    (tmp_path / "releases/legacy-v1/model.joblib").write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        r.rollback(registry=tmp_path, expected="b-model")
    assert (tmp_path / "state.json").read_bytes() == before


@pytest.mark.parametrize("kind", ["features", "threshold", "version", "metrics", "dataset", "pipeline"])
def test_incompatible_artifact_never_changes_active(candidate, tmp_path, kind):
    r.import_legacy(registry=tmp_path, model=MODEL_PATH, expected="VACIO")
    before = (tmp_path / "state.json").read_bytes()
    source = tmp_path / "candidate"
    source.mkdir()
    for path in candidate.iterdir():
        (source / path.name).write_bytes(path.read_bytes())
    artifact = joblib.load(source / "candidate.joblib")
    if kind == "features":
        artifact["features_entrada"] = ["target_no_show"]
    elif kind == "threshold":
        artifact["umbral_alto"] = 0.9
    elif kind == "version":
        artifact["version_modelo"] = "wrong"
    elif kind == "metrics":
        artifact["metricas_test"]["f1_score"] = 0.1
    elif kind == "dataset":
        artifact["dataset_info"]["version_dataset"] = "wrong"
    else:
        artifact["pipeline"] = "not a pipeline"
    joblib.dump(artifact, source / "candidate.joblib")
    manifest = json.loads((source / "manifest.json").read_bytes())
    manifest["artifact"]["sha256"] = sha((source / "candidate.joblib").read_bytes())
    (source / "manifest.json").write_bytes(bytes_json(manifest))
    with pytest.raises(Exception):
        promote(tmp_path, source, expected="legacy-v1")
    assert (tmp_path / "state.json").read_bytes() == before
    assert r.validate_release(tmp_path, r.read_state(tmp_path)["active"]).is_ready


def test_startup_and_worker_pin_release(candidate, tmp_path):
    ref = promote(tmp_path, candidate)
    env = dict(os.environ, MODEL_REGISTRY_DIR=str(tmp_path), IA_RELEASE_VERSION=ref["release"],
               IA_APPROVAL_SHA256=ref["approval_sha256"])
    code = '''from fastapi.testclient import TestClient
from app.main import app
from app.core.model_registry import registry
from app.execution import IsolatedExecutor
with TestClient(app) as c:
 assert c.get('/health/ready').status_code == 200
 assert registry.version_modelo == 'b-model'
 from app.config import IA_API_KEY
 import uuid
 data={'version_contrato':'1.0','version_features':'pre-cita-v1','version_modelo':'b-model',
 'id_solicitud':str(uuid.uuid4()),'features':registry._require().metadata.features_autorizadas}
 features={'especialidad':'CARDIOLOGIA','tipo_paciente':'NUEVO','canal_origen':'WEB',
 'franja_horaria':'MANANA','dia_semana':'LUNES','antelacion_dias':3,'inasistencias_previas':0,
 'asistencias_previas':0,'reprogramaciones_prev':0}
 data['features']=features
 result=c.post('/v1/predict',json=data,headers={'X-IA-API-Key':IA_API_KEY})
 assert result.status_code == 200, result.text
 assert result.json()['version_modelo'] == 'b-model'
 response=c.get('/v1/dataset',headers={'X-IA-API-Key':IA_API_KEY})
 assert response.status_code == 200, response.text
 assert response.json()['proposito'] == 'TRAINING_RUN'
 response=c.get('/v1/metrics',headers={'X-IA-API-Key':IA_API_KEY})
 assert response.status_code == 200, response.text
 # Cambiar puntero no afecta proceso vivo ni worker reiniciado.
 from pathlib import Path
 from app.config import MODEL_REGISTRY_DIR
 (MODEL_REGISTRY_DIR/'state.json').write_text('estado administrativo modificado')
 from app.main import close_executor
 close_executor()
 result=c.post('/v1/predict',json=data,headers={'X-IA-API-Key':IA_API_KEY})
 assert result.status_code == 200, result.text
 assert result.json()['version_modelo'] == 'b-model'
 assert not any(n == 'training' or n.startswith('training.') for n in __import__('sys').modules)
'''
    result = subprocess.run([sys.executable, "-B", "-c", code], env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr
    # Hash fijado incorrecto: no fallback automático al legacy.
    env["IA_APPROVAL_SHA256"] = "0" * 64
    result = subprocess.run([sys.executable, "-B", "-c",
        "from app.core.model_registry import ModelRegistry; assert not ModelRegistry().load_model()"],
        env=env, capture_output=True, timeout=30)
    assert result.returncode == 0


def test_cli_legacy_status_and_rejects_rollback(tmp_path, capsys):
    from management.cli import main
    main(["importar-legacy", "--registry", str(tmp_path), "--modelo", str(MODEL_PATH), "--esperado", "VACIO"])
    assert json.loads(capsys.readouterr().out)["release"] == "legacy-v1"
    main(["estado", "--registry", str(tmp_path)])
    assert json.loads(capsys.readouterr().out)["previous"] is None
    with pytest.raises(SystemExit) as error:
        main(["rollback", "--registry", str(tmp_path), "--esperado", "legacy-v1"])
    assert error.value.code == 1
