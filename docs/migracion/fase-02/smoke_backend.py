"""Smoke transaccional solo en BD desechable fase2, nunca en principal."""
import hashlib
import json
from pathlib import Path
import secrets
import sys

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import engine, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import Usuario
from app.modules.ia.predictor import RUTA_ARTEFACTO, predecir_cita_dict


def main():
    if "predicitas-fase2-" not in get_settings().database_url or not get_settings().database_url.endswith("/predicitas_fase2_smoke"):
        raise SystemExit("Solo BD fase2_smoke aislada")
    stage = sys.argv[1]
    dest = Path("/evidence") / f"smoke_{stage}.json"
    if dest.exists() or not RUTA_ARTEFACTO.is_file():
        raise SystemExit("No sobrescribir evidencia ni permitir entrenamiento")
    before = hashlib.sha256(RUTA_ARTEFACTO.read_bytes()).hexdigest()
    cases = [
        {"especialidad": "TRAUMATOLOGIA", "tipo_paciente": "CONTINUADOR", "canal_origen": "CALL_CENTER", "franja_horaria": "TARDE", "dia_semana": "VIERNES", "antelacion_dias": 32, "inasistencias_previas": 3, "asistencias_previas": 1, "reprogramaciones_prev": 2},
        {"especialidad": "PEDIATRIA", "tipo_paciente": "CONTINUADOR", "canal_origen": "WEB", "franja_horaria": "MANANA", "dia_semana": "LUNES", "antelacion_dias": 2, "inasistencias_previas": 0, "asistencias_previas": 12, "reprogramaciones_prev": 0},
        {"especialidad": "CARDIOLOGIA", "tipo_paciente": "NUEVO", "canal_origen": "PRESENCIAL", "franja_horaria": "MANANA", "dia_semana": "MIERCOLES", "antelacion_dias": 8, "inasistencias_previas": 0, "asistencias_previas": 0, "reprogramaciones_prev": 0},
    ]
    predictions = [predecir_cita_dict(case) for case in cases]
    results = []
    with engine.connect() as conn:
        outer = conn.begin()
        session = Session(bind=conn, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False)
        password = secrets.token_hex(24)
        try:
            users = []
            for role in ("ADMINISTRADOR", "RECEPCION", "TECNICO_IA"):
                user = Usuario(nombre_completo=f"Fase2 {role}", correo_institucional=f"fase2.{role.lower()}@example.invalid", password_hash=hash_password(password), rol=role)
                session.add(user)
                users.append(user)
            session.flush()
            app.dependency_overrides[get_db] = lambda: session
            with TestClient(app, raise_server_exceptions=False) as client:
                for path in ("/health", "/citas"):
                    response = client.get(path)
                    results.append({"role": "ANONIMO", "path": path, "status": response.status_code})
                for user in users:
                    response = client.post("/auth/login", data={"username": user.correo_institucional, "password": password})
                    results.append({"role": user.rol, "path": "/auth/login", "status": response.status_code})
                    token = response.json().get("access_token")
                    if not token:
                        raise AssertionError("Login smoke fallido")
                    for path in ("/auth/me", "/citas?limite=1", "/citas/catalogos", "/ia/metricas", "/ia/dataset-resumen"):
                        r = client.get(path, headers={"Authorization": f"Bearer {token}"})
                        results.append({"role": user.rol, "path": path, "status": r.status_code})
        finally:
            app.dependency_overrides.clear()
            session.close()
            outer.rollback()
    after = hashlib.sha256(RUTA_ARTEFACTO.read_bytes()).hexdigest()
    assert before == after
    data = {"results": results, "predictions": predictions, "model_sha256": after, "model_unchanged": True, "openapi": app.openapi(), "isolated_database": True, "users_rolled_back": True}
    with dest.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({"results": results, "model_unchanged": True}))


if __name__ == "__main__":
    main()
