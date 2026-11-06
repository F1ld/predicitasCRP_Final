"""Pruebas de autenticación interna X-IA-API-Key."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_missing_api_key_returns_401(client: TestClient):
    response = client.get("/v1/model")
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["codigo"] == "NO_AUTENTICADO"
    assert "X-IA-API-Key" in data["error"]["mensaje"] or "X-IA-API-Key" in str(data["error"]["campos"])


def test_invalid_api_key_returns_401(client: TestClient):
    response = client.get("/v1/model", headers={"X-IA-API-Key": "clave-falsa-invalida"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["codigo"] == "NO_AUTENTICADO"


def test_valid_api_key_allows_access(client: TestClient, auth_headers: dict[str, str]):
    response = client.get("/v1/model", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["version_contrato"] == "1.0"
