"""Pruebas para inferencia individual y por lote (/v1/predict y /v1/predict-batch)."""
from __future__ import annotations

import uuid
from fastapi.testclient import TestClient

from app.config import VERSION_CONTRATO, VERSION_FEATURES


def test_predict_individual_success(client: TestClient, auth_headers: dict[str, str], sample_features: dict):
    req_id = str(uuid.uuid4())
    payload = {
        "version_contrato": VERSION_CONTRATO,
        "id_solicitud": req_id,
        "version_modelo": "LightGBM_v1.0.0",
        "version_features": VERSION_FEATURES,
        "features": sample_features,
    }
    response = client.post("/v1/predict", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id_solicitud"] == req_id
    assert data["version_modelo"] == "LightGBM_v1.0.0"
    assert data["version_features"] == "pre-cita-v1"
    assert 0.0 <= data["probabilidad_no_show"] <= 1.0
    assert data["nivel_riesgo"] in {"BAJO", "MEDIO", "ALTO"}
    assert "features_snapshot" in data
    assert data["features_snapshot"]["tasa_no_show_previa"] is not None
    assert data["features_snapshot"]["es_reserva_lejana"] in {0, 1}
    assert "Factores clave:" in data["explicabilidad_resumen"]
    assert len(data["explicabilidad_resumen"]) <= 255


def test_predict_version_mismatch_returns_409(client: TestClient, auth_headers: dict[str, str], sample_features: dict):
    payload = {
        "version_contrato": VERSION_CONTRATO,
        "id_solicitud": str(uuid.uuid4()),
        "version_modelo": "MODELO_INEXISTENTE_v999",
        "version_features": VERSION_FEATURES,
        "features": sample_features,
    }
    response = client.post("/v1/predict", headers=auth_headers, json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["error"]["codigo"] == "VERSION_MODELO_INCOMPATIBLE"


def test_predict_extra_field_prohibited_returns_422(client: TestClient, auth_headers: dict[str, str], sample_features: dict):
    features_leak = dict(sample_features)
    features_leak["target_no_show"] = 1  # Columna prohibida
    payload = {
        "version_contrato": VERSION_CONTRATO,
        "id_solicitud": str(uuid.uuid4()),
        "version_modelo": "LightGBM_v1.0.0",
        "version_features": VERSION_FEATURES,
        "features": features_leak,
    }
    response = client.post("/v1/predict", headers=auth_headers, json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["codigo"] == "VALIDACION"


def test_predict_payload_too_large_returns_413(client: TestClient, auth_headers: dict[str, str], sample_features: dict):
    # Enviar un cuerpo mayor a 256 KiB
    big_comment = "X" * (260 * 1024)
    response = client.post(
        "/v1/predict",
        headers={**auth_headers, "Content-Length": str(len(big_comment))},
        content=big_comment,
    )
    assert response.status_code == 413
    data = response.json()
    assert data["error"]["codigo"] == "SOLICITUD_DEMASIADO_GRANDE"


def test_predict_batch_success(client: TestClient, auth_headers: dict[str, str], sample_features: dict):
    req_id = str(uuid.uuid4())
    payload = {
        "version_contrato": VERSION_CONTRATO,
        "id_solicitud": req_id,
        "version_modelo": "LightGBM_v1.0.0",
        "version_features": VERSION_FEATURES,
        "items": [
            {"id_item": "CIT-001", "features": sample_features},
            {
                "id_item": "CIT-002",
                "features": {
                    "especialidad": "CARDIOLOGIA",
                    "tipo_paciente": "NUEVO",
                    "canal_origen": "WEB",
                    "franja_horaria": "MANANA",
                    "dia_semana": "LUNES",
                    "antelacion_dias": 5,
                    "inasistencias_previas": 0,
                    "asistencias_previas": 0,
                    "reprogramaciones_prev": 0,
                },
            },
        ],
    }
    response = client.post("/v1/predict-batch", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id_solicitud"] == req_id
    assert len(data["items"]) == 2
    assert data["items"][0]["id_item"] == "CIT-001"
    assert data["items"][1]["id_item"] == "CIT-002"
    assert "probabilidad_no_show" in data["items"][0]["resultado"]
    assert "probabilidad_no_show" in data["items"][1]["resultado"]


def test_predict_batch_duplicate_ids_returns_422(client: TestClient, auth_headers: dict[str, str], sample_features: dict):
    payload = {
        "version_contrato": VERSION_CONTRATO,
        "id_solicitud": str(uuid.uuid4()),
        "version_modelo": "LightGBM_v1.0.0",
        "version_features": VERSION_FEATURES,
        "items": [
            {"id_item": "MISMO-ID", "features": sample_features},
            {"id_item": "MISMO-ID", "features": sample_features},
        ],
    }
    response = client.post("/v1/predict-batch", headers=auth_headers, json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["codigo"] == "VALIDACION"
