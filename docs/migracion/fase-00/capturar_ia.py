"""Ejecutar en imagen Python 3.12 con codigo/modelo actuales montados RO."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re

from app.modules.ia.predictor import RUTA_ARTEFACTO, obtener_artefacto_modelo, predecir_cita_dict


def main():
    if not RUTA_ARTEFACTO.is_file():
        raise SystemExit("Falta artefacto: se prohibe entrenamiento automatico en fase 0.")
    before = hashlib.sha256(RUTA_ARTEFACTO.read_bytes()).hexdigest()
    cases = [
        {"especialidad": "TRAUMATOLOGIA", "tipo_paciente": "CONTINUADOR", "canal_origen": "CALL_CENTER", "franja_horaria": "TARDE", "dia_semana": "VIERNES", "antelacion_dias": 32, "inasistencias_previas": 3, "asistencias_previas": 1, "reprogramaciones_prev": 2},
        {"especialidad": "PEDIATRIA", "tipo_paciente": "CONTINUADOR", "canal_origen": "WEB", "franja_horaria": "MANANA", "dia_semana": "LUNES", "antelacion_dias": 2, "inasistencias_previas": 0, "asistencias_previas": 12, "reprogramaciones_prev": 0},
        {"especialidad": "CARDIOLOGIA", "tipo_paciente": "NUEVO", "canal_origen": "PRESENCIAL", "franja_horaria": "MANANA", "dia_semana": "MIERCOLES", "antelacion_dias": 8, "inasistencias_previas": 0, "asistencias_previas": 0, "reprogramaciones_prev": 0},
    ]
    predictions = [{"features": case, "prediction": predecir_cita_dict(case)} for case in cases]
    artifact = obtener_artefacto_modelo()
    after = hashlib.sha256(RUTA_ARTEFACTO.read_bytes()).hexdigest()
    installed = {re.sub(r"[-_.]+", "-", d.metadata["Name"]).lower(): d.version for d in importlib.metadata.distributions()}
    requirements = []
    for line in Path("requirements.txt").read_text(encoding="utf-8-sig").splitlines():
        if "==" in line:
            package, wanted = line.strip().split("==")
            actual = installed.get(re.sub(r"[-_.]+", "-", package).lower())
            requirements.append({"package": package, "required": wanted, "installed": actual, "matches": wanted == actual})
    result = {
        "python": platform.python_version(), "model_sha256_before": before, "model_sha256_after": after,
        "model_unchanged": before == after, "version_modelo": artifact["version_modelo"],
        "dataset_info": artifact["dataset_info"], "metricas_test": artifact["metricas_test"],
        "predictions": predictions, "requirements_installed": requirements,
        "all_pinned_requirements_match": all(row["matches"] for row in requirements),
        "note": "Verifica entorno instalado en imagen existente; no acredita descarga limpia del indice de paquetes.",
    }
    with Path("/evidence/ia_baseline.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({"model_unchanged": result["model_unchanged"], "all_requirements_match": result["all_pinned_requirements_match"], "version_modelo": result["version_modelo"], "predictions": predictions}, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
