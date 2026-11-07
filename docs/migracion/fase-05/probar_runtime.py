"""Sonda HTTP real dentro de la imagen aislada, sin publicar puertos.

Comprueba además el plazo duro (mata el cómputo), el cupo único bajo concurrencia
y la memoria del servidor más su worker. No publica secretos ni datos.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import httpx

ONE_GIB = 1024 ** 3


def _read_int(path: str) -> int | None:
    try:
        value = Path(path).read_text().strip()
        return int(value) if value.isdigit() else None
    except (OSError, ValueError):
        return None


def _read_kb(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return None


def _child_pids(pid: int) -> list[int]:
    children = []
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return children
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            for line in (entry / "status").read_text().splitlines():
                if line.startswith("PPid:") and int(line.split()[1]) == pid:
                    children.append(int(entry.name))
                    break
        except (OSError, ValueError):
            continue
    return children


def _tree_rss(pid: int) -> int:
    total = _read_kb(pid) or 0
    for child in _child_pids(pid):
        total += _read_kb(child) or 0
        for grandchild in _child_pids(child):
            total += _read_kb(grandchild) or 0
    return total


def main():
    from app.config import COMPUTE_TIMEOUT_SECONDS, MODEL_PATH
    from app.execution import ComputationExpired, IsolatedExecutor
    from app.main import app
    assert os.getuid() == 1000
    assert not any(os.environ.get(k) for k in ("DATABASE_URL", "DATABASE_URL_MIGRACIONES", "SECRET_KEY"))
    assert not any(Path(p).exists() for p in ("/repo", "/app/.env", "/app/app/modules"))
    target = Path(sys.argv[1])
    assert not target.exists()
    model_hash = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    server = subprocess.Popen(["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8100",
        "--workers", "1", "--limit-concurrency", "16", "--timeout-keep-alive", "5"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url="http://127.0.0.1:8100", timeout=30) as client:
            deadline = time.monotonic() + 60
            while True:
                try:
                    if client.get("/health/ready").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                assert time.monotonic() < deadline and server.poll() is None, "Servidor no quedó listo"
                time.sleep(0.05)
            assert client.get("/health/live").json() == {"estado": "vivo"}
            assert client.get("/v1/model").status_code == 401
            headers = {"X-IA-API-Key": os.environ["IA_API_KEY"]}
            metadata = client.get("/v1/model", headers=headers)
            assert metadata.status_code == 200
            approval = json.loads(Path("/app/manifests/legacy-approved.json").read_text())
            item = {"id_item": "0", "features": approval["smoke"]["features"]}
            data = {"version_contrato": "1.0", "version_features": "pre-cita-v1",
                "version_modelo": metadata.json()["version_modelo"],
                "id_solicitud": str(uuid.uuid4()), "items": [item]}

            # Medición de memoria de servidor + worker durante el lote máximo.
            samples: list[int] = []
            stop = threading.Event()

            def monitor():
                while not stop.is_set():
                    samples.append(_tree_rss(server.pid))
                    time.sleep(0.01)

            sampler = threading.Thread(target=monitor, daemon=True)
            sampler.start()
            data["items"] = [{"id_item": str(i), "features": approval["smoke"]["features"]} for i in range(100)]
            start = time.monotonic()
            result = client.post("/v1/predict-batch", headers=headers, json=data)
            elapsed = time.monotonic() - start
            stop.set()
            sampler.join(timeout=2)
            assert result.status_code == 200 and len(result.json()["items"]) == 100
            assert elapsed < COMPUTE_TIMEOUT_SECONDS

            procfs_peak = max(samples) if samples else _tree_rss(server.pid)
            cgroup_peak = _read_int("/sys/fs/cgroup/memory.peak")
            cgroup_current = _read_int("/sys/fs/cgroup/memory.current")
            if cgroup_peak is None:
                cgroup_peak = _read_int("/sys/fs/cgroup/memory/memory.max_usage_in_bytes")
            peak = max([value for value in (procfs_peak, cgroup_peak, cgroup_current) if value is not None])
            memory = {"method": "procfs-vmrss+cgroup", "procfs_peak_bytes": procfs_peak,
                "cgroup_peak_bytes": cgroup_peak, "cgroup_current_bytes": cgroup_current,
                "peak_bytes": peak, "limit_bytes": ONE_GIB, "under_limit": peak < ONE_GIB}

            # Plazo duro: un worker que no responde debe morir y liberar el cupo.
            timeout_executor = IsolatedExecutor(timeout=0.3, command=[
                sys.executable, "-u", "-c",
                "import sys,time; sys.stdin.buffer.readline(); time.sleep(60)"])
            timeout_start = time.monotonic()
            try:
                try:
                    timeout_executor.run({"action": "predict", "version_modelo": "x", "features": [{}]})
                except ComputationExpired:
                    pass
                else:
                    raise AssertionError("El plazo no interrumpió el cómputo")
            finally:
                timeout_executor.close()
            timeout_kill_seconds = time.monotonic() - timeout_start
            assert timeout_kill_seconds < 5

            # Concurrencia: un cupo; la segunda petición no se encola.
            barrier = threading.Barrier(2)

            def concurrent_call():
                barrier.wait()
                with httpx.Client(base_url="http://127.0.0.1:8100", timeout=30) as own:
                    return own.post("/v1/predict-batch", headers=headers, json=data)

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: concurrent_call(), range(2)))
            statuses = sorted(response.status_code for response in responses)
            assert statuses == [200, 503], statuses
            busy = next(response for response in responses if response.status_code == 503).json()
            assert busy["error"]["codigo"] == "MODELO_NO_DISPONIBLE"
            assert busy["error"]["campos"]["motivo"] == "CAPACIDAD_OCUPADA"
            recovered = client.post("/v1/predict", headers=headers, json={
                "version_contrato": "1.0", "version_features": "pre-cita-v1",
                "version_modelo": metadata.json()["version_modelo"],
                "id_solicitud": str(uuid.uuid4()), "features": approval["smoke"]["features"]})
            assert recovered.status_code == 200
        assert hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() == model_hash
        result = {"real_http": True, "ready": True, "no_auth_rejected": True, "batch_items": 100,
            "batch_seconds": elapsed, "batch_budget_seconds": COMPUTE_TIMEOUT_SECONDS,
            "compute_timeout_seconds": COMPUTE_TIMEOUT_SECONDS,
            "execution_isolation": "un worker persistente, proceso separado, cupo único",
            "timeout_enforced": True, "timeout_kill_seconds": timeout_kill_seconds,
            "concurrency": {"simultaneous": 2, "ok": 1, "busy": 1,
                "busy_error": "CAPACIDAD_OCUPADA", "recovered": True},
            "memory": memory, "uid": os.getuid(), "model_unchanged": True,
            "no_backend_mount_or_dsn": True, "network": "none", "workers": 1,
            "receive_timeout_seconds": 10, "openapi": app.openapi()}
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


if __name__ == "__main__":
    main()
