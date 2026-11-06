"""Regresiones de los hallazgos de revisión, sin modificar el modelo legado."""
import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock, patch
import uuid

import httpx
import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import config
from app.body_limit import MaxBodySizeMiddleware
from app.core.inference import clasificar_nivel_riesgo, ejecutar_inferencia_individual
from app.core.model_registry import ModelRegistry, registry
from app.main import app
from app.schemas import FeaturesPreCita


def payload(features):
    return {"version_contrato": "1.0", "version_features": "pre-cita-v1",
            "version_modelo": "LightGBM_v1.0.0", "id_solicitud": str(uuid.uuid4()), "features": features}


@pytest.mark.parametrize("key", ["", "   "])
def test_startup_fails_closed_without_key(monkeypatch, key):
    monkeypatch.setattr(config, "IA_API_KEY", key)
    with pytest.raises(RuntimeError, match="IA_API_KEY"):
        with TestClient(app):
            pytest.fail("Arrancó sin clave")


@pytest.mark.parametrize("field", ["version_contrato", "version_features"])
def test_versions_required(client, auth_headers, sample_features, field):
    data = payload(sample_features)
    data.pop(field)
    assert client.post("/v1/predict", json=data, headers=auth_headers).status_code == 422


@pytest.mark.parametrize("value", [True, False, "3", 3.5, None, -1])
@pytest.mark.parametrize("field", ["antelacion_dias", "inasistencias_previas", "asistencias_previas", "reprogramaciones_prev"])
def test_integer_input_no_coercion(client, auth_headers, sample_features, field, value):
    data = payload({**sample_features, field: value})
    assert client.post("/v1/predict", json=data, headers=auth_headers).status_code == 422


@pytest.mark.parametrize("n,expected", [(0, 422), (1, 200), (100, 200), (101, 422)])
def test_batch_boundaries(client, auth_headers, sample_features, n, expected):
    data = payload(sample_features)
    data.pop("features")
    data["items"] = [{"id_item": str(i), "features": sample_features} for i in range(n)]
    assert client.post("/v1/predict-batch", json=data, headers=auth_headers).status_code == expected


@pytest.mark.parametrize("prob,level", [(0, "BAJO"), (0.299, "BAJO"), (0.300, "MEDIO"),
    (0.449, "MEDIO"), (0.450, "MEDIO"), (0.451, "ALTO"), (1, "ALTO")])
def test_exact_thresholds(prob, level):
    assert clasificar_nivel_riesgo(prob) == level


@pytest.mark.parametrize("prob", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_not_fallback(prob, sample_features):
    pipeline = Mock()
    pipeline.predict_proba.return_value = np.array([[0.0, prob]])
    with pytest.raises(ValueError, match="finita"):
        ejecutar_inferencia_individual(pipeline, FeaturesPreCita(**sample_features))


@pytest.mark.parametrize("kind", ["missing", "hash", "corrupt", "pipeline", "version", "libraries", "features", "smoke", "thresholds", "python", "metadata"])
def test_bad_artifacts_not_ready(tmp_path, kind):
    approved = json.loads(config.MANIFEST_PATH.read_text())
    target = tmp_path / "model.joblib"
    if kind != "missing":
        target.write_bytes(config.MODEL_PATH.read_bytes())
    if kind in ("corrupt", "pipeline", "version", "features", "thresholds", "metadata"):
        if kind == "corrupt":
            target.write_bytes(b"not a pickle")
        else:
            model = joblib.load(config.MODEL_PATH)
            if kind == "pipeline":
                model["pipeline"] = "NOT_A_PIPELINE"
            elif kind == "version":
                model["version_modelo"] = "wrong"
            elif kind == "thresholds":
                model["umbral_alto"] = 0.9
            elif kind == "metadata":
                model.pop("dataset_info")
            else:
                model["features_entrada"] = []
            joblib.dump(model, target)
        # Simular un archivo aprobado pero incompatible; no cambia la aprobación real.
        approved["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    elif kind == "hash":
        target.write_bytes(b"untrusted")
    elif kind == "libraries":
        approved["libraries"]["joblib"] = "0.0.0"
    elif kind == "python":
        approved["python_major_minor"] = "0.0"
    elif kind == "smoke":
        approved["smoke"]["probabilidad_no_show"] = 0.123
    manifest = tmp_path / "approval.json"
    manifest.write_text(json.dumps(approved), encoding="utf-8")
    local = ModelRegistry()
    assert local.load_model()
    assert not local.load_model(target, manifest_path=manifest)
    assert not local.is_ready and local.pipeline is None and local.version_modelo is None
    if kind in ("hash", "libraries", "missing", "python"):
        with patch("app.core.model_registry.joblib.load") as load:
            assert not local.load_model(target, manifest_path=manifest)
            load.assert_not_called()


def test_invalid_manifest_before_deserialization(tmp_path):
    target = tmp_path / "manifest.json"
    target.write_text("{}")
    with patch("app.core.model_registry.joblib.load") as load:
        assert not ModelRegistry().load_model(manifest_path=target)
        load.assert_not_called()


def test_real_startup_missing_model(monkeypatch, tmp_path, auth_headers, sample_features):
    import app.core.model_registry as module
    monkeypatch.setattr(registry, "_state", registry._state)
    monkeypatch.setattr(module, "MODEL_PATH", tmp_path / "absent")
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        for route in ("model", "metrics", "dataset"):
            assert client.get("/v1/" + route, headers=auth_headers).status_code == 503
        assert client.post("/v1/predict", json=payload(sample_features), headers=auth_headers).status_code == 503


@pytest.mark.parametrize("size,status", [(256 * 1024, 204), (256 * 1024 + 1, 413)])
def test_stream_stops_at_limit(size, status):
    async def run():
        consumed = []
        async def body():
            # Primer chunk llega al límite exacto. El tercero nunca debe leerse.
            yield b"x" * min(size, 256 * 1024)
            if size > 256 * 1024:
                consumed.append("excess")
                yield b"x"
                consumed.append("too_far")
                yield b"unread"
        async def downstream(scope, receive, send):
            from starlette.responses import Response
            assert len((await receive())["body"]) == size
            await Response(status_code=204)(scope, receive, send)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=MaxBodySizeMiddleware(downstream)), base_url="http://test") as client:
            response = await client.post("/", content=body())
            assert response.status_code == status
        assert "too_far" not in consumed
    asyncio.run(run())


def test_invalid_content_length(client):
    assert client.post("/v1/predict", content=b"", headers={"Content-Length": "invalid"}).status_code == 422


def test_receive_timeout():
    async def run():
        async def receive():
            await asyncio.sleep(1)
        messages = []
        async def send(message):
            messages.append(message)
        async def downstream(*args):
            pytest.fail("No debe alcanzar endpoint")
        await MaxBodySizeMiddleware(downstream, receive_timeout=0.01)({"type": "http", "headers": []}, receive, send)
        assert messages[0]["status"] == 422
    asyncio.run(run())
