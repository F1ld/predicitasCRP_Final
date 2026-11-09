"""Carga exclusivamente sintética para el laboratorio de rendimiento."""
import json
import os
from time import monotonic

import httpx
from sqlalchemy import select
from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.modules.citas.models import Cita
from app.modules.usuarios.models import Usuario

assert engine.url.host == "db" and engine.url.database == "predicitas_f10_perf"
password = os.environ["FASE10_DEMO_PASSWORD"]
email = "rendimiento@predicitas.crp"
mode = os.environ["FASE10_PERF_MODE"]

if mode == "usuario":
    with SessionLocal() as db:
        db.add(Usuario(nombre_completo="Rendimiento sintético", correo_institucional=email,
                       password_hash=hash_password(password), rol="ADMINISTRADOR", activo=True))
        db.commit()
else:
    with SessionLocal() as db:
        ids = list(db.scalars(select(Cita.id_cita).order_by(Cita.id_cita)))
    assert len(ids) == 500
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30, trust_env=False) as client:
        login = client.post("/auth/login", data={"username": email, "password": password})
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        result = {"individual_seconds": [], "batch_500_seconds": []}
        cases = [(f"/ia/predecir/{appointment}", "individual_seconds") for appointment in ids[:3]]
        cases += [("/ia/predecir-lote?forzar=true", "batch_500_seconds")] * 3
        for route, key in cases:
            start = monotonic()
            response = client.post(route, headers=headers)
            elapsed = monotonic() - start
            assert response.status_code == 200, response.text
            if key == "batch_500_seconds":
                assert response.json()["evaluadas"] == 500
            result[key].append(round(elapsed, 3))
    print(json.dumps(result))
