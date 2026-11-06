"""Configuración del servicio autónomo de IA (Fase 5).

No depende de base de datos relacional, JWT de negocio ni modelos backend.
"""
from __future__ import annotations

import os
from pathlib import Path

_FILE_PATH = Path(__file__).resolve()
_PARENTS = _FILE_PATH.parents
_PROJECT_ROOT = _PARENTS[3] if len(_PARENTS) > 3 else _PARENTS[1] if len(_PARENTS) > 1 else _PARENTS[0]

# Directorio por defecto para el registro de modelos
_DEFAULT_REGISTRY_CANDIDATES = [
    _PROJECT_ROOT / "artifacts" / "models" / "legacy-import",
    _PROJECT_ROOT / "apps" / "backend" / "app" / "modules" / "ia" / "artifacts",
    Path("/app/artifacts/models/legacy-import"),
    Path("/app/app/modules/ia/artifacts"),
]


def _resolver_directorio_modelos() -> Path:
    env_dir = os.getenv("MODEL_REGISTRY_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.exists():
            return p
    for candidate in _DEFAULT_REGISTRY_CANDIDATES:
        if candidate.exists():
            return candidate
    return _DEFAULT_REGISTRY_CANDIDATES[0]


IA_API_KEY: str = os.getenv("IA_API_KEY", "predicitas-ia-internal-secret-key")
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

MODEL_REGISTRY_DIR: Path = _resolver_directorio_modelos()
MODEL_FILENAME: str = os.getenv("MODEL_FILENAME", "modelo_predicitas_v1.joblib")
MODEL_PATH: Path = MODEL_REGISTRY_DIR / MODEL_FILENAME
