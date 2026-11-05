"""Importación canónica real sobre BD fase3 NUEVA, usuarios y cargas revertidos."""
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import secrets

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import Usuario
from app.modules.citas.importer import validar_fila
from app.modules.citas.router import reloj
from app.modules.ia.predictor import RUTA_ARTEFACTO, predecir_cita_dict

ROOT = Path("/repo")
RESULTS = Path("/results")
AHORA = datetime.fromisoformat("2026-11-05T08:00:00-05:00")
MUESTRAS = (("citas_para_importar_variado.csv", 40, 0), ("citas_demo.csv", 20, 4))


def clasificar(path):
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    seen, errors = set(), []
    for index, raw in enumerate(rows, 1):
        clean = {k: v for k, v in raw.items() if k and v not in (None, "")}
        try:
            normalized, _ = validar_fila(clean, AHORA)
            if normalized.id_cita_externa in seen:
                raise ValueError("duplicada dentro del mismo archivo")
            seen.add(normalized.id_cita_externa)
        except ValidationError as exc:
            errors.append({"fila": index, "tipo": "validacion", "campos": [".".join(map(str, e["loc"])) for e in exc.errors()]})
        except ValueError as exc:
            errors.append({"fila": index, "tipo": str(exc)})
    return {"archivo": path.name, "recibidas": len(rows), "aceptables_sin_duplicados_bd": len(rows) - len(errors), "rechazadas": len(errors), "rechazos": errors}


def conteos(conn):
    return {name: conn.execute(text(f"SELECT count(*) FROM {name}")).scalar_one()
            for name in ("citas", "historial_estados_cita", "auditoria_eventos", "usuarios")}


def probar_upload(path, accepted, rejected, bom=False):
    contenido = path.read_bytes()
    if bom:
        contenido = b"\xef\xbb\xbf" + contenido
    with engine.connect() as conn:
        outer = conn.begin()
        initial = conteos(conn)
        session = Session(bind=conn, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False)
        try:
            password = secrets.token_hex(24)
            user = Usuario(nombre_completo="Fase3 temporal", correo_institucional="fase3.api@example.invalid", password_hash=hash_password(password), rol="RECEPCION")
            session.add(user)
            session.flush()
            app.dependency_overrides[get_db] = lambda: session
            app.dependency_overrides[reloj] = lambda: AHORA
            with TestClient(app, raise_server_exceptions=False) as client:
                login = client.post("/auth/login", data={"username": user.correo_institucional, "password": password})
                assert login.status_code == 200
                headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
                files = {"archivo": (path.name, contenido, "text/csv")}
                first = client.post("/citas/importar", headers=headers, files=files)
                assert first.status_code == 200, first.text
                body = first.json()
                assert (body["aceptadas"], body["rechazadas"]) == (accepted, rejected), body
                second = client.post("/citas/importar", headers=headers, files=files)
                assert second.status_code == 200
                assert second.json()["aceptadas"] == 0
                assert second.json()["rechazadas"] == accepted + rejected
                assert conteos(conn)["citas"] == initial["citas"] + accepted
                result = {"archivo": path.name, "bom": bom, "primera_carga": body, "segunda_carga": {k: second.json()[k] for k in ("recibidas", "aceptadas", "rechazadas")}}
        finally:
            app.dependency_overrides.clear()
            session.close()
            outer.rollback()
        with conn.begin():
            assert conteos(conn) == initial, "La transacción de prueba debe revertir usuarios, citas, historial y auditoría"
    result["rollback_verified"] = True
    return result


def main():
    url = get_settings().database_url
    if "@predicitas-fase3-" not in url or not url.endswith("/predicitas_fase3_test"):
        raise SystemExit("Prohibido ejecutar fuera de BD fase3_test aislada")
    target = RESULTS / "importacion_canonica.json"
    if target.exists() or not RUTA_ARTEFACTO.is_file():
        raise SystemExit("No sobrescribir evidencia ni permitir entrenamiento automático")
    model_before = hashlib.sha256(RUTA_ARTEFACTO.read_bytes()).hexdigest()
    cases = json.loads((ROOT / "docs/migracion/fase-00/ia_baseline.json").read_text(encoding="utf-8"))["predictions"]
    predictions = [predecir_cita_dict(case["features"]) for case in cases]
    baseline = json.loads((ROOT / "docs/migracion/fase-02/smoke_antes.json").read_text(encoding="utf-8"))
    assert json.loads(json.dumps(predictions, default=str)) == baseline["predictions"]
    samples, uploads = [], []
    for filename, accepted, rejected in MUESTRAS:
        path = ROOT / "data/samples/importacion" / filename
        classification = clasificar(path)
        assert (classification["aceptables_sin_duplicados_bd"], classification["rechazadas"]) == (accepted, rejected)
        samples.append(classification)
        for bom in (False, True):
            uploads.append(probar_upload(path, accepted, rejected, bom))
    model_after = hashlib.sha256(RUTA_ARTEFACTO.read_bytes()).hexdigest()
    assert model_before == model_after
    assert app.openapi() == baseline["openapi"]
    result = {"reference_clock": AHORA.isoformat(), "samples": samples, "uploads": uploads, "model_hash_unchanged": model_before == model_after, "prediction_parity": True, "openapi_unchanged": True, "database_isolated": True, "new_retention_enabled": False}
    with target.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, default=str)
    print("Importación API canónica 40/0 y 20/4, BOM, duplicados, rollback, OpenAPI y tres predicciones: PASÓ")


if __name__ == "__main__":
    main()
