"""Smoke HTTP del backend limpio: datos sembrados, sin IA ni modelo empaquetado.

No usa TestClient ni importa la app en este proceso: levanta uvicorn real y habla
TCP. Solo verifica los endpoints operativos acordados para E; no ejercita IA.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx


def wait_ready(client, process):
    for _ in range(160):
        if process.poll() is not None:
            raise RuntimeError("Backend terminó antes de estar vivo")
        try:
            if client.get("/health").status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.25)
    raise RuntimeError("Backend no arrancó")


def main():
    assert not list(Path("/app").rglob("*.joblib")), "El backend limpio no debe incluir modelo"
    assert not any(k in os.environ for k in ("IA_URL", "IA_API_KEY", "MODEL_REGISTRY_DIR")), \
        "El backend limpio no debe configurarse contra IA"
    password = os.environ["SEED_PASSWORD"]
    log = Path("/tmp/backend-e.log").open("w")
    process = subprocess.Popen(
        [sys.executable, "-B", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", "8000", "--log-level", "warning"],
        stdout=log, stderr=log,
    )
    try:
        with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
            wait_ready(client, process)
            health = client.get("/health")
            assert health.status_code == 200 and health.json() == {"estado": "ok"}, health.text

            login = client.post("/auth/login", data={"username": "admin@predicitas.crp",
                                                     "password": password})
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]
            assert token and login.json()["expires_in"] > 0
            headers = {"Authorization": "Bearer " + token}

            citas = client.get("/citas", params={"limite": 1}, headers=headers)
            assert citas.status_code == 200, citas.text
            pagina = citas.json()
            assert pagina["total"] == 1080 and pagina["limite"] == 1 and len(pagina["items"]) == 1

            usuarios = client.get("/usuarios", params={"limite": 1}, headers=headers)
            assert usuarios.status_code == 200, usuarios.text
            assert usuarios.json()["total"] == 3

            catalogos = client.get("/citas/catalogos", headers=headers)
            assert catalogos.status_code == 200, catalogos.text
            valores = catalogos.json()
            assert set(valores) == {"especialidades", "estados", "niveles_riesgo", "medicos",
                                    "canales_origen", "tipos_paciente"}
            assert valores["especialidades"] and valores["medicos"]

            rep02 = client.get("/reportes/rep-02", headers=headers)
            assert rep02.status_code == 200, rep02.text
            assert {"resumen", "por_canal", "filas"} <= set(rep02.json())

            rep03 = client.get("/reportes/rep-03", headers=headers)
            assert rep03.status_code == 200, rep03.text
            assert {"resumen", "por_especialidad", "filas"} <= set(rep03.json())

            summary = {
                "health": "ok",
                "login": "admin@predicitas.crp",
                "citas_total": pagina["total"],
                "usuarios_total": usuarios.json()["total"],
                "catalogos": sorted(valores),
                "rep_02": rep02.status_code,
                "rep_03": rep03.status_code,
                "modelo_empaquetado": False,
                "ia_configurada": False,
                "transporte": "uvicorn real + HTTP TCP",
            }
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log.close()
    with (Path("/results") / "backend-e.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, sort_keys=True, indent=2)
    print("Backend E: health, login, citas, usuarios, catálogos y reportes aprobados")


if __name__ == "__main__":
    main()
