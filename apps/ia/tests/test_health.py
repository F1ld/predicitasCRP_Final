"""Pruebas para los endpoints de salud /health/* del servicio IA."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.model_registry import ModelRegistry, registry


def test_health_live(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"estado": "vivo"}


def test_health_ready_ok(client: TestClient):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"estado": "listo"}


def test_health_ready_model_unavailable(client: TestClient, monkeypatch):
    # Simular que el registro no tiene modelo cargado
    monkeypatch.setattr(registry, "_pipeline", None)
    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert "error" in data
    assert data["error"]["codigo"] == "MODELO_NO_DISPONIBLE"
