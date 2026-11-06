"""Configuración del servicio autónomo de IA (Fase 5).

No depende de base de datos relacional, JWT de negocio ni modelos backend.
"""
from __future__ import annotations

import os
from pathlib import Path

IA_API_KEY: str = os.getenv("IA_API_KEY", "")


def require_api_key() -> str:
    # Sin fallback conocido, tampoco ante una variable vacía o solo espacios.
    if not IA_API_KEY.strip():
        raise RuntimeError("IA_API_KEY debe configurarse explícitamente")
    return IA_API_KEY
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8100"))

# Límites de contrato estricto (contracts/ia/openapi.objetivo.v1.json)
MAX_BODY_SIZE_BYTES: int = 256 * 1024  # 256 KiB
MAX_BATCH_SIZE: int = 100
MIN_BATCH_SIZE: int = 1

# Versiones de contrato y perfil
VERSION_CONTRATO: str = "1.0"
VERSION_FEATURES: str = "pre-cita-v1"
UMBRAL_MEDIO: float = 0.300
UMBRAL_ALTO: float = 0.450

ROTULO_ETICO: str = "Resultado simulado — Dataset sintético acreditado (RF-056)"
ES_SIMULACION: bool = True

FEATURES_AUTORIZADAS: list[str] = [
    "especialidad",
    "tipo_paciente",
    "canal_origen",
    "franja_horaria",
    "dia_semana",
    "antelacion_dias",
    "inasistencias_previas",
    "asistencias_previas",
    "reprogramaciones_prev",
]

MODEL_REGISTRY_DIR = Path(os.getenv("MODEL_REGISTRY_DIR", "/models"))
MODEL_FILENAME: str = os.getenv("MODEL_FILENAME", "modelo_predicitas_v1.joblib")
MODEL_PATH: Path = MODEL_REGISTRY_DIR / MODEL_FILENAME
MANIFEST_PATH = Path(__file__).resolve().parents[1] / "manifests/legacy-approved.json"
