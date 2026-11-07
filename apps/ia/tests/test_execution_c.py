"""Bloque C: plazo duro, cupo único, worker aislado y mapeo 503.

No cambia fórmulas ni el esquema de respuesta. Las pruebas de ejecución usan
workers falsos de la biblioteca estándar; la paridad usa el worker real.
"""
from __future__ import annotations

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
        out = {"status": "ok", "version_modelo": "v1"}
        sys.stdout.buffer.write(json.dumps(out).encode() + b"\n")
        sys.stdout.buffer.flush()
        continue
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
