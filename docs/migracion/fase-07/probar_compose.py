"""Smoke HTTP del Compose aislado. Solo acepta la base del laboratorio."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
from time import monotonic

import httpx
from sqlalchemy import func, select

import app.bootstrap.models
from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.citas.importer import importar_citas
from app.modules.ia.models import PrediccionIA
from app.modules.usuarios.models import Usuario
from tests.test_ia_endpoints import CITAS_PRUEBA_IA

EMAIL = "smoke-compose@predicitas.crp"
PASSWORD = "SoloLaboratorio123"
LOT = "/ia/predecir-lote?forzar=true"


def medir_concurrencia(client, headers):
    barrier = Barrier(2, timeout=10)

    def request():
        barrier.wait()
        start = monotonic()
        response = client.post(LOT, headers=headers)
        elapsed = round(monotonic() - start, 3)
        if response.status_code == 200:
            assert response.json()["evaluadas"] == 500
        else:
            assert response.status_code == 503, response.text
            assert response.json()["error"]["codigo"] == "MOTOR_IA_NO_DISPONIBLE"
        return {"status": response.status_code, "seconds": elapsed}

    def check(successes):
        with SessionLocal() as db:
            count = db.scalar(select(func.count(PrediccionIA.id_prediccion)))
            audits = db.scalar(select(func.count(AuditoriaEvento.id_log)).where(AuditoriaEvento.modulo == "IA"))
            assert count == (500 if successes else 0)
            assert audits == successes

    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent = list(pool.map(lambda _: request(), range(2)))
    successes = sum(result["status"] == 200 for result in concurrent)
    check(successes)
    start = monotonic()
    recovered = client.post(LOT, headers=headers)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["evaluadas"] == 500
    check(successes + 1)
    print(json.dumps({"citas_por_lote": 500, "concurrentes": concurrent,
                      "recuperacion_segundos": round(monotonic() - start, 3)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["sin-ia", "recuperado", "retorno", "concurrencia"])
    args = parser.parse_args()
    assert engine.url.host == "db" and engine.url.database == "predicitas_f7_compose"
    if args.phase in {"sin-ia", "concurrencia"}:
        with SessionLocal() as db:
            user = Usuario(nombre_completo="Smoke Compose", correo_institucional=EMAIL,
                           password_hash=hash_password(PASSWORD), rol="ADMINISTRADOR", activo=True)
            db.add(user)
            db.flush()
            rows = CITAS_PRUEBA_IA
            if args.phase == "concurrencia":
                rows = [CITAS_PRUEBA_IA[i % len(CITAS_PRUEBA_IA)] |
                        {"id_cita_externa": f"CONC-{i}", "paciente_anon_id": f"PAC-CONC-{i}"}
                        for i in range(500)]
            importar_citas(db, rows, id_usuario=user.id_usuario,
                           ip="127.0.0.1", origen="smoke-compose")
            db.commit()
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30, trust_env=False) as client:
        assert client.get("/health").status_code == 200
        auth = client.post("/auth/login", data={"username": EMAIL, "password": PASSWORD})
        assert auth.status_code == 200
        headers = {"Authorization": "Bearer " + auth.json()["access_token"]}
        if args.phase == "concurrencia":
            medir_concurrencia(client, headers)
            return
        result = client.post(LOT, headers=headers)
        expected = 503 if args.phase == "sin-ia" else 200
        assert result.status_code == expected, result.text
        if expected == 503:
            assert result.json()["error"]["codigo"] == "MOTOR_IA_NO_DISPONIBLE"
        else:
            assert result.json()["evaluadas"] == len(CITAS_PRUEBA_IA)
        print(json.dumps({"fase": args.phase, "health": 200, "lote": result.status_code}))


if __name__ == "__main__":
    main()
