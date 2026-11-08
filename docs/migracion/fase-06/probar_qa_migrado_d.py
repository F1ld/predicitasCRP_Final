"""QA de payloads frontend con backend empaquetado y PostgreSQL aislado."""
import importlib.util
import json
from pathlib import Path
import secrets

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.database import Base, engine, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.citas.importer import importar_citas
from app.modules.usuarios.models import Usuario


def main():
    if engine.url.database != "predicitas_f6c_test" or not (engine.url.host or "").startswith("predicitas-f6c-"):
        raise SystemExit("Solo laboratorio nuevo de fase 6")
    spec = importlib.util.spec_from_file_location("qa_diseno_migrado", "/qa/apps/frontend/tests/validar_diseno.py")
    qa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qa)
    observer = create_engine(engine.url, poolclass=NullPool)
    def snapshot():
        with observer.connect() as connection:
            return {t.name: [dict(row) for row in connection.execute(select(t).order_by(*t.primary_key.columns)).mappings()]
                    for t in Base.metadata.sorted_tables}
    initial = snapshot()
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False)
    try:
        records = qa.cargar_qa("ux45", "UX-MIGRADO-D")
        api = qa.cargar_qa("uxapi20", "UXAPI-MIGRADO-D")
        web = qa.cargar_qa("uxweb20", "UXWEB-MIGRADO-D")
        assert [len(records), len(api), len(web)] == [49, 24, 24]
        result = importar_citas(db, records, id_usuario=None, ip="127.0.0.1", origen="QA D con rollback")
        assert (result.aceptadas, result.rechazadas) == (45, 4)
        password = "QA9-" + secrets.token_urlsafe(18)
        email = "qa-d-" + secrets.token_hex(6) + "@example.invalid"
        user = Usuario(nombre_completo="QA D sintético", correo_institucional=email,
                       password_hash=hash_password(password), rol="RECEPCION", activo=True)
        db.add(user)
        db.commit()
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            response = client.post("/auth/login", data={"username": email, "password": password})
            assert response.status_code == 200
            headers = {"Authorization": "Bearer " + response.json()["access_token"]}
            for rows in (api, web):
                data = qa.csv_bytes(rows)
                result = client.post("/citas/importar", headers=headers, files={"archivo": ("qa.csv", data, "text/csv")})
                assert result.status_code == 200
                assert (result.json()["aceptadas"], result.json()["rechazadas"]) == (20, 4)
                repeat = client.post("/citas/importar", headers=headers, files={"archivo": ("qa.csv", data, "text/csv")})
                assert (repeat.json()["aceptadas"], repeat.json()["rechazadas"]) == (0, 24)
        assert snapshot() == initial
    finally:
        app.dependency_overrides.clear()
        db.close()
        transaction.rollback()
        connection.close()
    assert snapshot() == initial
    observer.dispose()
    output = {"initial_fixture": {"accepted": 45, "rejected": 4},
              "api_and_browser_fixtures": {"each_accepted": 20, "each_rejected": 4, "repeat_rejected": 24},
              "rollback_independent_observer": True, "browser_visual_validation": False,
              "scope": "Payloads QA nuevos y ASGI real; no se ejecuta navegador ni servidor QA persistente"}
    with Path("/results/qa-migrado.json").open("x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2)
    print("QA D: 45/4 y 2x20/4; repetición 0/24; rollback independiente aprobado")


if __name__ == "__main__":
    main()
