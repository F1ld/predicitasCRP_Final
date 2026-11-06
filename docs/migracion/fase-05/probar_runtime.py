"""Sonda HTTP real dentro de la imagen aislada, sin publicar puertos."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import httpx


def main():
    from app.config import MODEL_PATH
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
        with httpx.Client(base_url="http://127.0.0.1:8100", timeout=10) as client:
            deadline = time.monotonic() + 30
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
            data = {"version_contrato": "1.0", "version_features": "pre-cita-v1", "version_modelo": metadata.json()["version_modelo"],
                "id_solicitud": str(uuid.uuid4()), "items": [{"id_item": str(i), "features": approval["smoke"]["features"]} for i in range(100)]}
            start = time.monotonic()
            result = client.post("/v1/predict-batch", headers=headers, json=data)
            elapsed = time.monotonic() - start
            assert result.status_code == 200 and len(result.json()["items"]) == 100
            assert elapsed < 10
        assert hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() == model_hash
        result = {"real_http": True, "ready": True, "no_auth_rejected": True, "batch_items": 100,
            "batch_seconds": elapsed, "batch_budget_seconds": 10, "uid": os.getuid(),
            "model_unchanged": True, "no_backend_mount_or_dsn": True, "network": "none", "workers": 1,
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
