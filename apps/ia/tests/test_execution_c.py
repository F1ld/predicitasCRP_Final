"""Bloque C: plazo duro, cupo único, worker aislado y mapeo 503.

No cambia fórmulas ni el esquema de respuesta. Las pruebas de ejecución usan
workers falsos de la biblioteca estándar; la paridad usa el worker real.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import time
import uuid

import pytest

from app.execution import (
    CapacityUnavailable,
    ComputationExpired,
    IsolatedExecutor,
    WorkerFailed,
)

_FAKE = r'''
import json, os, sys, time
mode = __MODE__
state = __STATE__
for line in sys.stdin.buffer:
    req = json.loads(line)
    if req.get("action") == "ping":
        out = {"status": "error"} if mode == "pingbad" else {"status": "ok", "version_modelo": "v1"}
        sys.stdout.buffer.write(json.dumps(out).encode() + b"\n")
        sys.stdout.buffer.flush()
        continue
    if mode == "nonl":
        sys.stdout.buffer.write(b'{"status":"ok"}')
        sys.stdout.buffer.flush()
        raise SystemExit(0)
    if mode == "huge":
        sys.stdout.buffer.write(b"x" * 64 + b"\n")
        sys.stdout.buffer.flush()
        raise SystemExit(0)
    if mode == "slow":
        time.sleep(60)
    if mode == "delay":
        time.sleep(0.6)
    if mode == "crash":
        raise SystemExit(7)
    if mode == "bad":
        sys.stdout.buffer.write(b"not-json\n")
        sys.stdout.buffer.flush()
        continue
    if mode == "error":
        sys.stdout.buffer.write(b'{"status":"error"}\n')
        sys.stdout.buffer.flush()
        continue
    if mode == "wrongversion":
        out = {"status": "ok", "version_modelo": "otro", "items": []}
    elif mode == "short":
        out = {"status": "ok", "version_modelo": req["version_modelo"], "items": [{"n": 0}]}
    elif mode == "list":
        out = [1, 2]
    elif mode == "recover":
        if not os.path.exists(state):
            open(state, "x").close()
            time.sleep(60)
        out = {"status": "ok", "version_modelo": req["version_modelo"],
               "items": [{"n": i} for i, _ in enumerate(req["features"])]}
    else:
        out = {"status": "ok", "version_modelo": req["version_modelo"],
               "items": [{"n": i} for i, _ in enumerate(req["features"])]}
    sys.stdout.buffer.write(json.dumps(out).encode() + b"\n")
    sys.stdout.buffer.flush()
'''


def _command(mode: str, state: str = "") -> list[str]:
    code = _FAKE.replace("__MODE__", repr(mode)).replace("__STATE__", repr(state))
    return [sys.executable, "-u", "-c", code]


def _payload(n: int = 2) -> dict:
    return {"action": "predict", "version_modelo": "v1", "features": [{} for _ in range(n)]}


def test_warm_and_worker_reuse():
    executor = IsolatedExecutor(timeout=5, command=_command("echo"))
    try:
        executor.warm()
        pid = executor._worker.pid
        assert executor.run(_payload())["items"] == [{"n": 0}, {"n": 1}]
        assert executor.run(_payload(1))["items"] == [{"n": 0}]
        assert executor._worker.pid == pid, "El worker debe reutilizarse entre solicitudes"
    finally:
        executor.close()


def test_timeout_kills_worker_and_releases_capacity():
    executor = IsolatedExecutor(timeout=0.3, command=_command("slow"))
    try:
        start = time.monotonic()
        with pytest.raises(ComputationExpired):
            executor.run(_payload())
        assert time.monotonic() - start < 5
        assert executor._worker is None, "El worker vencido no debe reutilizarse"
        assert not executor._slot.locked()
    finally:
        executor.close()


def test_restart_after_timeout(tmp_path):
    state = tmp_path / "recover.state"
    executor = IsolatedExecutor(timeout=0.4, command=_command("recover", str(state)))
    try:
        with pytest.raises(ComputationExpired):
            executor.run(_payload())
        assert executor.run(_payload(3))["items"] == [{"n": 0}, {"n": 1}, {"n": 2}]
    finally:
        executor.close()


def test_single_slot_rejects_concurrency_without_queueing():
    executor = IsolatedExecutor(timeout=5, command=_command("delay"))
    outcome = {}

    def first():
        try:
            outcome["result"] = executor.run(_payload())
        except BaseException as exc:  # se reporta abajo
            outcome["error"] = exc

    thread = threading.Thread(target=first)
    try:
        thread.start()
        deadline = time.monotonic() + 5
        while not executor._slot.locked() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert executor._slot.locked()
        with pytest.raises(CapacityUnavailable):
            executor.run(_payload())
        thread.join(timeout=10)
        assert not thread.is_alive() and "error" not in outcome
        assert outcome["result"]["items"] == [{"n": 0}, {"n": 1}]
    finally:
        executor.close()


@pytest.mark.parametrize("mode", ["crash", "bad", "error", "wrongversion"])
def test_invalid_worker_is_discarded(mode):
    executor = IsolatedExecutor(timeout=3, command=_command(mode))
    try:
        with pytest.raises(WorkerFailed):
            executor.run(_payload())
        assert executor._worker is None
        assert not executor._slot.locked()
    finally:
        executor.close()


def test_oversized_internal_request_does_not_spawn():
    executor = IsolatedExecutor(timeout=3, command=_command("echo"))
    try:
        with pytest.raises(WorkerFailed, match="excesiva"):
            executor.run({"action": "predict", "version_modelo": "v1",
                          "features": [{"x": "a" * (600 * 1024)}]})
        assert executor._worker is None
    finally:
        executor.close()


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True, "10"])
def test_invalid_timeout_rejected(timeout):
    with pytest.raises(ValueError):
        IsolatedExecutor(timeout=timeout)


def test_close_is_final():
    executor = IsolatedExecutor(timeout=3, command=_command("echo"))
    executor.warm()
    executor.close()
    assert executor.closed
    with pytest.raises(CapacityUnavailable):
        executor.run(_payload())
    executor.close()  # idempotente


# ---------------------------------------------------------------------------
# Integración HTTP: mapeo de errores, plazo real y paridad con el worker
# ---------------------------------------------------------------------------


def _request(features: dict) -> dict:
    return {"version_contrato": "1.0", "version_features": "pre-cita-v1",
            "version_modelo": "LightGBM_v1.0.0", "id_solicitud": str(uuid.uuid4()),
            "features": features}


class _BrokenExecutor:
    def __init__(self, exc):
        self.exc = exc

    def run(self, payload):
        raise self.exc

    def close(self):
        return None


@pytest.mark.parametrize("exc,motivo", [
    (CapacityUnavailable("ocupado"), "CAPACIDAD_OCUPADA"),
    (ComputationExpired("plazo"), "PLAZO_AGOTADO"),
    (WorkerFailed("worker"), "WORKER_FALLIDO"),
])
def test_http_maps_executor_failures_to_503(monkeypatch, client, auth_headers, sample_features, exc, motivo):
    import app.main as main_module
    monkeypatch.setattr(main_module, "_executor", _BrokenExecutor(exc))
    response = client.post("/v1/predict", headers=auth_headers, json=_request(sample_features))
    assert response.status_code == 503
    body = response.json()["error"]
    assert body["codigo"] == "MODELO_NO_DISPONIBLE"
    assert body["campos"]["motivo"] == motivo


def test_http_timeout_returns_503_and_does_not_hang(monkeypatch, client, auth_headers, sample_features):
    import app.main as main_module
    executor = IsolatedExecutor(timeout=0.3, command=_command("slow"))
    monkeypatch.setattr(main_module, "_executor", executor)
    try:
        start = time.monotonic()
        response = client.post("/v1/predict", headers=auth_headers, json=_request(sample_features))
        assert time.monotonic() - start < 5
        assert response.status_code == 503
        assert response.json()["error"]["campos"]["motivo"] == "PLAZO_AGOTADO"
    finally:
        executor.close()


def test_worker_matches_direct_inference(sample_features):
    import app.main as main_module
    from app.core.inference import ejecutar_inferencia_individual
    from app.core.model_registry import registry
    from app.schemas import FeaturesPreCita
    features = FeaturesPreCita(**sample_features)
    prob, level, snapshot, explanation = ejecutar_inferencia_individual(registry.pipeline, features)
    items = main_module.ejecutar_aislado(registry.version_modelo, [features])
    assert items == [{
        "probabilidad_no_show": prob,
        "nivel_riesgo": level,
        "features_snapshot": snapshot.model_dump(mode="json"),
        "explicabilidad_resumen": explanation,
    }]


def test_worker_does_not_import_training_datasets_sqlalchemy_or_backend_modules():
    code = """
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(("training", "datasets", "sqlalchemy", "alembic", "app.modules")):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
from app.inference_worker import main
raise SystemExit(main())
"""
    result = subprocess.run([sys.executable, "-c", code], input=b'{"action":"ping"}\n',
                            capture_output=True, timeout=60, env=os.environ.copy())
    assert result.returncode == 0, result.stderr.decode(errors="replace")[-1000:]
    assert json.loads(result.stdout.splitlines()[-1])["status"] == "ok"


# ---------------------------------------------------------------------------
# Ramas límite del ejecutor (sin worker real)
# ---------------------------------------------------------------------------


def test_warm_rejects_unready_worker():
    executor = IsolatedExecutor(timeout=3, command=_command("pingbad"))
    try:
        with pytest.raises(WorkerFailed, match="no quedó listo"):
            executor.warm()
        assert executor._worker is None
        assert not executor._slot.locked()
    finally:
        executor.close()


def test_warm_returns_immediately_when_slot_is_busy():
    executor = IsolatedExecutor(timeout=3, command=_command("echo"))
    try:
        assert executor._slot.acquire(blocking=False)
        try:
            assert executor.warm() is None
        finally:
            executor._slot.release()
        assert executor._worker is None, "No debe arrancar worker sin cupo"
    finally:
        executor.close()


def test_environment_filters_secrets_and_forces_single_thread(monkeypatch):
    monkeypatch.setenv("IA_API_KEY", "secreto-que-no-debe-pasar")
    monkeypatch.setenv("DATABASE_URL", "postgresql://no-debe-pasar")
    monkeypatch.setenv("SECRET_KEY", "no-debe-pasar")
    monkeypatch.setenv("MODEL_FILENAME", "modelo.joblib")
    executor = IsolatedExecutor(timeout=3, command=_command("echo"))
    try:
        env = executor._environment()
        assert "IA_API_KEY" not in env and "DATABASE_URL" not in env and "SECRET_KEY" not in env
        assert env["MODEL_FILENAME"] == "modelo.joblib"
        assert env["OMP_NUM_THREADS"] == env["OPENBLAS_NUM_THREADS"] == env["MKL_NUM_THREADS"] == "1"
        assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    finally:
        executor.close()


def test_spawn_after_close_is_rejected():
    executor = IsolatedExecutor(timeout=3, command=_command("echo"))
    executor.close()
    with pytest.raises(CapacityUnavailable, match="cerrado"):
        executor._spawn()


def test_unstartable_worker_is_reported_as_worker_failed():
    executor = IsolatedExecutor(timeout=3, command=["predicitas-no-existe-xyz"])
    try:
        with pytest.raises(WorkerFailed, match="No se pudo iniciar"):
            executor.run(_payload())
        assert executor._worker is None
        assert not executor._slot.locked()
    finally:
        executor.close()


def test_dead_worker_is_replaced_before_next_request():
    executor = IsolatedExecutor(timeout=5, command=_command("echo"))
    try:
        executor.warm()
        first_pid = executor._worker.pid
        executor._worker.kill()
        executor._worker.wait(timeout=5)
        assert executor.run(_payload())["items"] == [{"n": 0}, {"n": 1}]
        assert executor._worker.pid != first_pid
    finally:
        executor.close()


def test_partial_response_without_newline_is_discarded():
    executor = IsolatedExecutor(timeout=3, command=_command("nonl"))
    try:
        with pytest.raises(WorkerFailed, match="sin respuesta completa"):
            executor.run(_payload())
        assert executor._worker is None
    finally:
        executor.close()


def test_oversized_response_is_discarded(monkeypatch):
    import app.execution as execution
    monkeypatch.setattr(execution, "MAX_RESPONSE_BYTES", 64)
    executor = IsolatedExecutor(timeout=3, command=_command("huge"))
    try:
        with pytest.raises(WorkerFailed, match="Respuesta interna excesiva"):
            executor.run(_payload())
        assert executor._worker is None
    finally:
        executor.close()


@pytest.mark.parametrize("mode", ["short", "list"])
def test_incompatible_response_shape_is_discarded(mode):
    executor = IsolatedExecutor(timeout=3, command=_command(mode))
    try:
        with pytest.raises(WorkerFailed, match="incompatible"):
            executor.run(_payload())
        assert executor._worker is None
    finally:
        executor.close()


def test_non_serializable_payload_does_not_spawn():
    executor = IsolatedExecutor(timeout=3, command=_command("echo"))
    try:
        with pytest.raises(WorkerFailed, match="no serializable"):
            executor.run({"action": "predict", "version_modelo": "v1",
                          "features": [{"x": object()}]})
        assert executor._worker is None
    finally:
        executor.close()


# ---------------------------------------------------------------------------
# Worker privado, ejecutado en proceso para que la cobertura lo observe
# ---------------------------------------------------------------------------


class _WorkerModel:
    def __init__(self, pipeline=None, version="LightGBM_v1.0.0", ready=True):
        self.pipeline = pipeline
        self.version_modelo = version
        self._ready = ready

    def load_model(self):
        return self._ready

    def version_matches(self, version):
        return self._ready and version == self.version_modelo


class _Input:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


class _Output:
    def __init__(self):
        self.buffer = io.BytesIO()


def _run_worker_main(monkeypatch, model, data: bytes):
    import app.core.model_registry as registry_module
    import app.inference_worker as worker
    monkeypatch.setattr(registry_module, "ModelRegistry", lambda: model)
    monkeypatch.setattr(sys, "stdin", _Input(data))
    output = _Output()
    monkeypatch.setattr(sys, "stdout", output)
    code = worker.main()
    return code, output.buffer.getvalue()


def _last_message(raw: bytes) -> dict:
    return json.loads(raw.splitlines()[-1])


def test_worker_predict_matches_direct_inference(sample_features):
    from app.core.inference import ejecutar_inferencia_individual
    from app.core.model_registry import registry
    from app.inference_worker import _predict
    model = _WorkerModel(registry.pipeline, registry.version_modelo)
    result = _predict(model, {"version_modelo": model.version_modelo, "features": [sample_features]})
    from app.schemas import FeaturesPreCita
    prob, level, snapshot, explanation = ejecutar_inferencia_individual(
        registry.pipeline, FeaturesPreCita(**sample_features)
    )
    assert result == {
        "status": "ok",
        "version_modelo": model.version_modelo,
        "items": [{
            "probabilidad_no_show": prob,
            "nivel_riesgo": level,
            "features_snapshot": snapshot.model_dump(mode="json"),
            "explicabilidad_resumen": explanation,
        }],
    }


@pytest.mark.parametrize("payload_request", [
    {"version_modelo": 1, "features": [{}]},
    {"version_modelo": "v1", "features": "no-es-lista"},
    {"version_modelo": "v1", "features": []},
    {"version_modelo": "v1", "features": [{}] * 101},
    {"version_modelo": "otro", "features": [{}]},
])
def test_worker_predict_rejects_invalid_request(payload_request):
    from app.inference_worker import _predict
    model = _WorkerModel(version="v1")
    with pytest.raises(ValueError):
        _predict(model, payload_request)


@pytest.mark.parametrize("data,expected_code,expected_status", [
    (b'{"action":"ping"}\n', 0, "ok"),
    (b"", 0, None),
    (b"not-json\n", 4, "error"),
    (b"[]\n", 4, "error"),
    (b'{"action":"drop"}\n', 4, "error"),
    (b'{"action":"predict","version_modelo":"LightGBM_v1.0.0"}\n', 4, "error"),
    (b'{"action":"predict","version_modelo":"otro","features":[{}]}\n', 4, "error"),
])
def test_worker_main_protocol(monkeypatch, data, expected_code, expected_status):
    model = _WorkerModel(version="LightGBM_v1.0.0")
    code, raw = _run_worker_main(monkeypatch, model, data)
    assert code == expected_code
    if expected_status is None:
        assert raw == b""
    else:
        assert _last_message(raw)["status"] == expected_status


def test_worker_main_load_failure_returns_two(monkeypatch):
    code, raw = _run_worker_main(monkeypatch, _WorkerModel(ready=False), b'{"action":"ping"}\n')
    assert code == 2
    assert raw == b""


def test_worker_main_predict_success(monkeypatch, sample_features):
    from app.core.model_registry import registry
    model = _WorkerModel(registry.pipeline, registry.version_modelo)
    line = json.dumps({"action": "predict", "version_modelo": model.version_modelo,
                       "features": [sample_features]}).encode() + b"\n"
    code, raw = _run_worker_main(monkeypatch, model, line)
    assert code == 0
    payload = _last_message(raw)
    assert payload["status"] == "ok" and len(payload["items"]) == 1
    assert payload["version_modelo"] == model.version_modelo
    assert 0.0 <= payload["items"][0]["probabilidad_no_show"] <= 1.0


def test_worker_main_rejects_oversized_line(monkeypatch):
    import app.inference_worker as worker
    model = _WorkerModel(version="LightGBM_v1.0.0")
    oversized = b'{"action":"ping","pad":"' + b"a" * (worker.MAX_INPUT_BYTES + 1) + b'"}\n'
    code, raw = _run_worker_main(monkeypatch, model, oversized)
    assert code == 3
    assert _last_message(raw)["status"] == "error"
