"""Fixtures de pruebas para el servicio autónomo de IA."""
from __future__ import annotations

import os
import secrets
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("IA_API_KEY", secrets.token_urlsafe(32))

from app.config import IA_API_KEY, MODEL_PATH
from app.core.model_registry import registry
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_model():
    """Asegura que el artefacto del modelo esté cargado para toda la sesión de pruebas."""
    loaded = registry.load_model(MODEL_PATH)
    assert loaded, f"No se pudo cargar el modelo desde {MODEL_PATH}"
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    class Headers(dict):
        def __repr__(self):
            return "<cabecera interna protegida>"
    return Headers({"X-IA-API-Key": IA_API_KEY})


@pytest.fixture
def sample_features() -> dict:
    return {
        "especialidad": "TRAUMATOLOGIA",
        "tipo_paciente": "CONTINUADOR",
        "canal_origen": "CALL_CENTER",
        "franja_horaria": "TARDE",
        "dia_semana": "VIERNES",
        "antelacion_dias": 32,
        "inasistencias_previas": 3,
        "asistencias_previas": 1,
        "reprogramaciones_prev": 2,
    }
