"""OpenAPI y smoke real con transaccion externa revertida, solo en servidor fase0."""
import json
from pathlib import Path
import secrets

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import Usuario


def main():
    url = get_settings().database_url
    if "predicitas-fase0-20261103-2200-restore:5432/predicitas" not in url:
        raise SystemExit("Solo se permite el servidor restore aislado.")
    evidence = Path("/evidence")
    with (evidence / "openapi_baseline.json").open("x", encoding="utf-8") as stream:
        json.dump(app.openapi(), stream, ensure_ascii=False, indent=2)
    results = []
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False)
    password = secrets.token_hex(24)
    users = {}
    try:
        for role in ("ADMINISTRADOR", "RECEPCION", "TECNICO_IA"):
            user = Usuario(nombre_completo=f"Fase0 {role}", correo_institucional=f"fase0.{role.lower()}@example.invalid", password_hash=hash_password(password), rol=role)
            session.add(user)
            users[role] = user
        session.flush()
        app.dependency_overrides[get_db] = lambda: session
        with TestClient(app, raise_server_exceptions=False) as client:
            for path in ("/health", "/citas"):
                response = client.get(path)
                results.append({"role": "ANONIMO", "method": "GET", "path": path, "status": response.status_code, "body": response.json()})
            for role, user in users.items():
                login = client.post("/auth/login", data={"username": user.correo_institucional, "password": password})
                token = login.json().get("access_token")
                results.append({"role": role, "method": "POST", "path": "/auth/login", "status": login.status_code, "token_returned": bool(token)})
                if not token:
                    continue
                headers = {"Authorization": f"Bearer {token}"}
                for path in ("/auth/me", "/citas?limite=1", "/citas/catalogos", "/ia/metricas", "/ia/dataset-resumen"):
                    response = client.get(path, headers=headers)
                    body = response.json() if "json" in response.headers.get("content-type", "") else response.text[:100]
                    # No capturar filas de datos ni correos originales de la copia BD.
                    example = body
                    if path.startswith("/citas?") and isinstance(body, dict):
                        example = {key: value for key, value in body.items() if not isinstance(value, list)}
                        example["row_collections_omitted"] = True
                    if path == "/auth/me":
                        example = {"rol": body.get("rol"), "activo": body.get("activo")}
                    results.append({"role": role, "method": "GET", "path": path, "status": response.status_code, "body": example})
    finally:
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()
    with (evidence / "api_smoke_baseline.json").open("x", encoding="utf-8") as stream:
        json.dump({"isolated_server": True, "temporary_users_rolled_back": True, "tokens_and_passwords_omitted": True, "results": results}, stream, ensure_ascii=False, indent=2, default=str)
    print(json.dumps([{key: row[key] for key in ("role", "method", "path", "status")} for row in results], ensure_ascii=False))


if __name__ == "__main__":
    main()
