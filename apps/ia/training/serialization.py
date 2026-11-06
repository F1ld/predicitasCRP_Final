"""Escritura offline exclusiva de candidatos; sin registry ni promoción."""
from pathlib import Path

import joblib

from app.config import MODEL_REGISTRY_DIR
from training.trainer import Entrenamiento, LEGACY_VERSION


def guardar_candidato(resultado: Entrenamiento, *, directorio_nuevo: Path) -> Path:
    if resultado.artefacto["version_modelo"] == LEGACY_VERSION:
        raise ValueError("Versión activa no permitida")
    target = Path(directorio_nuevo).resolve()
    active = MODEL_REGISTRY_DIR.resolve()
    if target == active or active in target.parents:
        raise ValueError("No se permite escribir en el registry activo")
    # El padre debe existir; no crear árboles amplios ni reutilizar directorios.
    target.mkdir(exist_ok=False)
    path = target / "candidate.joblib"
    with path.open("xb") as stream:
        joblib.dump(resultado.artefacto, stream)
    return path
