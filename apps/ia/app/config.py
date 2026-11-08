"""Configuración del servicio autónomo de IA (Fase 5).

No depende de base de datos relacional, JWT de negocio ni modelos backend.
"""
from __future__ import annotations

import math
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

# Presupuesto total de una inferencia aislada: arranque/validación del modelo,
# cómputo, explicabilidad y serialización. Se aplica por lote completo.
try:
    COMPUTE_TIMEOUT_SECONDS: float = float(os.getenv("IA_COMPUTE_TIMEOUT_SECONDS", "10"))
except ValueError:
    raise RuntimeError("IA_COMPUTE_TIMEOUT_SECONDS debe ser numérico") from None
if not math.isfinite(COMPUTE_TIMEOUT_SECONDS) or COMPUTE_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("IA_COMPUTE_TIMEOUT_SECONDS debe ser positivo y finito")

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

# Opt-in: versión inmutable y hash fijados al reiniciar, nunca reload automático.
# Sin estas variables se conserva exactamente el camino legacy.
RELEASE_VERSION = os.getenv("IA_RELEASE_VERSION", "")
APPROVAL_SHA256 = os.getenv("IA_APPROVAL_SHA256", "")
if RELEASE_VERSION or APPROVAL_SHA256:
    import re
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", RELEASE_VERSION)
            or not re.fullmatch(r"[a-f0-9]{64}", APPROVAL_SHA256)):
        raise RuntimeError("Release y hash de aprobación explícitos requeridos")
    MODEL_PATH = MODEL_REGISTRY_DIR / "releases" / RELEASE_VERSION / "model.joblib"
    MANIFEST_PATH = MODEL_PATH.parent / "approval.json"
