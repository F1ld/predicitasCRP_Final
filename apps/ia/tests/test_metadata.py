"""Pruebas para endpoints de metadatos /v1/model, /v1/metrics y /v1/dataset."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_get_model_metadata(client: TestClient, auth_headers: dict[str, str]):
    response = client.get("/v1/model", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["version_contrato"] == "1.0"
    assert data["version_features"] == "pre-cita-v1"
    assert data["version_modelo"] == "LightGBM_v1.0.0"
    assert data["version_dataset"] == "DS_SINTETICO_CRP_v1.0"
    assert data["umbrales"] == {"medio": 0.3, "alto": 0.45}
    assert len(data["features_autorizadas"]) == 9
    assert data["es_simulacion"] is True
    assert "Resultado simulado" in data["rotulo_etico"]


def test_get_model_metrics(client: TestClient, auth_headers: dict[str, str]):
    response = client.get("/v1/metrics", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["version_modelo"] == "LightGBM_v1.0.0"
    assert data["algoritmo"] in ("LightGBM", "LGBMClassifier")
    assert data["cumple_meta_f1_82"] is True
    assert "metricas_test" in data
    assert "f1_score" in data["metricas_test"]
    assert data["metricas_test"]["f1_score"] >= 0.82


def test_get_dataset_metadata(client: TestClient, auth_headers: dict[str, str]):
    response = client.get("/v1/dataset", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["version_contrato"] == "1.0"
    assert data["version_dataset"] == "DS_SINTETICO_CRP_v1.0"
    assert data["proposito"] == "LEGACY_IMPORT"
    assert data["fuente"] == "LEGACY_METADATA_ONLY"
    assert data["linaje_completo"] is False
    assert data["total_historicas"] == 1000
    assert data["control_leakage"]["aprobado"] is True
