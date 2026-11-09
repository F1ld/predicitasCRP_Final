"""Recorrido HTTP y persistencia en la base sintética de fase 10."""
import json
from time import monotonic

import httpx
from sqlalchemy import func, select

import app.bootstrap.models
from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.modules.citas.importer import importar_citas
from app.modules.ia.models import PrediccionIA
from app.modules.usuarios.models import Usuario
from tests.test_ia_endpoints import CITAS_PRUEBA_IA

assert engine.url.host == "db" and engine.url.database == "predicitas_f10_test"
password = "SoloLaboratorioFase10!"
roles = ("ADMINISTRADOR", "RECEPCION", "TECNICO_IA")
with SessionLocal() as db:
    for role in roles:
        db.add(Usuario(nombre_completo=role, correo_institucional=f"{role.lower()}@predicitas.crp",
                       password_hash=hash_password(password), rol=role, activo=True))
    db.flush()
    admin = db.scalar(select(Usuario).where(Usuario.rol == "ADMINISTRADOR"))
    importar_citas(db, CITAS_PRUEBA_IA, id_usuario=admin.id_usuario, ip="127.0.0.1", origen="fase10-e2e")
    db.commit()

with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30, trust_env=False) as client:
    assert client.get("/citas").status_code == 401
    for role in roles:
        login = client.post("/auth/login", data={"username": f"{role.lower()}@predicitas.crp", "password": password})
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        assert client.get("/auth/me", headers=headers).json()["rol"] == role
        assert client.get("/citas?limite=1", headers=headers).status_code == 200
        expected = 200 if role == "ADMINISTRADOR" else 403
        assert client.get("/usuarios", headers=headers).status_code == expected

    from app.modules.citas.models import Cita
    with SessionLocal() as db:
        appointment = db.scalar(select(Cita.id_cita).order_by(Cita.id_cita))
    start = monotonic()
    individual = client.post(f"/ia/predecir/{appointment}", headers=headers)
    individual_time = monotonic() - start
    assert individual.status_code == 200
    assert individual.json()["id_cita"] == appointment
    start = monotonic()
    batch = client.post("/ia/predecir-lote?forzar=true", headers=headers)
    batch_time = monotonic() - start
    assert batch.status_code == 200
    assert batch.json()["evaluadas"] == len(CITAS_PRUEBA_IA)
    assert client.get("/ia/metricas", headers=headers).status_code == 200
    assert client.get("/ia/dataset-resumen", headers=headers).status_code == 200

with SessionLocal() as db:
    assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == len(CITAS_PRUEBA_IA)

print(json.dumps({"roles": roles, "unauthenticated": 401, "individual_seconds": round(individual_time, 3),
                  "batch_seconds": round(batch_time, 3), "batch_size": len(CITAS_PRUEBA_IA)}))
