"""Recorrido limpio E: generar, validar, entrenar, promover y rollback.

Solo usa /work y /contracts; no abre BD, no lee el modelo legacy y no escribe
en el registry de serving. Los comandos se ejecutan como CLI reales.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

FECHA = "2026-11-07T12:00:00-05:00"
CASOS = [
    {"especialidad": "CARDIOLOGIA", "tipo_paciente": "NUEVO", "canal_origen": "WEB",
     "franja_horaria": "MANANA", "dia_semana": "LUNES", "antelacion_dias": 1,
     "inasistencias_previas": 0, "asistencias_previas": 0, "reprogramaciones_prev": 0},
    {"especialidad": "TRAUMATOLOGIA", "tipo_paciente": "CONTINUADOR", "canal_origen": "CALL_CENTER",
     "franja_horaria": "TARDE", "dia_semana": "VIERNES", "antelacion_dias": 30,
     "inasistencias_previas": 3, "asistencias_previas": 2, "reprogramaciones_prev": 2},
    {"especialidad": "PEDIATRIA", "tipo_paciente": "CONTINUADOR", "canal_origen": "PRESENCIAL",
     "franja_horaria": "MANANA", "dia_semana": "SABADO", "antelacion_dias": 15,
     "inasistencias_previas": 1, "asistencias_previas": 4, "reprogramaciones_prev": 0},
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, *, expected=0):
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != expected:
        raise RuntimeError(
            f"Comando {command[2:4]} terminó {result.returncode}, esperado {expected}: "
            + (result.stderr or result.stdout)[-500:]
        )
    return result


def cli(*args):
    return [sys.executable, "-B", "-m", "training.cli", "--contracts-dir", "/contracts", *args]


def management(*args):
    return [sys.executable, "-B", "-m", "management.cli", *args]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    args = parser.parse_args()
    work, results = args.work, args.results
    if not work.is_absolute() or not results.is_absolute() or not work.is_dir() or not results.is_dir():
        raise ValueError("Directorios absolutos existentes requeridos")
    datasets, candidates, registry = work / "datasets", work / "candidates", work / "registry"
    for folder in (datasets, candidates, registry):
        folder.mkdir(exist_ok=False)

    dataset = datasets / "e-dataset"
    run(cli("generar", "--version-dataset", "e-dataset", "--semilla", "42",
            "--fecha-corte", "2026-10-29", "--generado-en", FECHA,
            "--fuente", "SINTETICO_GENERADO", "--proximas", "80",
            "--directorio", str(datasets)))
    run(cli("validar", "--dataset", str(dataset)))

    seed_csv = dataset / "seed.csv"
    seed_manifest = json.loads((dataset / "seed-manifest.json").read_bytes())
    if sha(seed_csv) != seed_manifest["sha256"] or seed_manifest["filas"] != 1080:
        raise ValueError("Seed generado inconsistente")
    dataset_manifest = json.loads((dataset / "manifest.json").read_bytes())
    if dataset_manifest["total_historicas"] != 1000 or not dataset_manifest["linaje_completo"]:
        raise ValueError("Linaje del dataset inconsistente")

    for version in ("e-model-a", "e-model-b"):
        run(cli("entrenar", "--dataset", str(dataset), "--version-modelo", version,
                "--fecha", FECHA, "--directorio", str(candidates)))
    a, b = candidates / "e-model-a", candidates / "e-model-b"
    metrics_equal = (a / "metrics.json").read_bytes() == (b / "metrics.json").read_bytes()

    import joblib
    from app.core.inference import ejecutar_inferencia_individual
    from app.schemas import FeaturesPreCita
    artifacts = {name: joblib.load(folder / "candidate.joblib") for name, folder in (("a", a), ("b", b))}
    predictions = {}
    for name, artifact in artifacts.items():
        predictions[name] = [
            ejecutar_inferencia_individual(artifact["pipeline"], FeaturesPreCita(**case))
            for case in CASOS
        ]
    if predictions["a"] != predictions["b"]:
        raise ValueError("Los dos entrenamientos no son reproducibles en inferencia")
    if not metrics_equal:
        raise ValueError("Las métricas de los dos entrenamientos difieren")
    artifact_bytes_equal = (a / "candidate.joblib").read_bytes() == (b / "candidate.joblib").read_bytes()

    def promote(candidate, version, expected, *, expected_code=0):
        return run(management("promover", "--registry", str(registry), "--candidato", str(candidate),
                              "--manifest-sha256", sha(candidate / "manifest.json"),
                              "--aprobar-version", version, "--esperado", expected,
                              "--contracts-dir", "/contracts"), expected=expected_code)

    from management.releases import read_state
    promote(a, "e-model-a", "VACIO")
    state_a = read_state(registry)
    if state_a["active"]["release"] != "e-model-a" or state_a["previous"] is not None:
        raise ValueError("Promoción A incorrecta")

    tamper = work / "tamper"
    shutil.copytree(a, tamper)
    with (tamper / "candidate.joblib").open("ab") as stream:
        stream.write(b" ")
    state_before_tamper = (registry / "state.json").read_bytes()
    promote(tamper, "e-model-a", "e-model-a", expected_code=1)
    if (registry / "state.json").read_bytes() != state_before_tamper:
        raise ValueError("La promoción corrupta alteró el estado")

    promote(b, "e-model-b", "e-model-a")
    state_b = read_state(registry)
    if state_b["active"]["release"] != "e-model-b" or state_b["previous"]["release"] != "e-model-a":
        raise ValueError("Promoción B incorrecta")

    run(management("rollback", "--registry", str(registry), "--esperado", "e-model-b"))
    state_rollback_a = read_state(registry)
    if state_rollback_a["active"]["release"] != "e-model-a":
        raise ValueError("Rollback a A incorrecto")
    run(management("rollback", "--registry", str(registry), "--esperado", "e-model-a"))
    state_rollback_b = read_state(registry)
    if state_rollback_b["active"]["release"] != "e-model-b":
        raise ValueError("Rollback a B incorrecto")

    summary = {
        "dataset": {
            "version": dataset_manifest["version_dataset"],
            "manifest_sha256": sha(dataset / "manifest.json"),
            "raw_sha256": dataset_manifest["sha256_raw"],
            "seed_sha256": seed_manifest["sha256"],
            "seed_rows": seed_manifest["filas"],
            "total_historicas": dataset_manifest["total_historicas"],
            "particiones": {name: dataset_manifest["particiones"][name]["filas"]
                            for name in ("train", "val", "test")},
        },
        "candidates": {
            "a": {"manifest_sha256": sha(a / "manifest.json"),
                  "artifact_sha256": sha(a / "candidate.joblib"),
                  "metrics_sha256": sha(a / "metrics.json")},
            "b": {"manifest_sha256": sha(b / "manifest.json"),
                  "artifact_sha256": sha(b / "candidate.joblib"),
                  "metrics_sha256": sha(b / "metrics.json")},
            "metrics_equal": metrics_equal,
            "predictions_equal": True,
            "artifact_bytes_equal": artifact_bytes_equal,
        },
        "promotion": {
            "after_a": state_a,
            "after_b": state_b,
            "tamper_rejected": True,
            "state_unchanged_after_tamper": True,
            "after_rollback_a": state_rollback_a,
            "after_rollback_b": state_rollback_b,
        },
        "registry": {
            "final_active": state_rollback_b["active"]["release"],
            "approval_sha256": state_rollback_b["active"]["approval_sha256"],
            "release_files": sorted(p.name for p in (registry / "releases" / "e-model-b").iterdir()),
        },
        "scope": "Pipeline limpio sin BD, sin modelo legacy y sin escritura en el registry de serving",
    }
    with (results / "pipeline-e.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, sort_keys=True, indent=2)
    print("Pipeline E: dataset, dos entrenamientos, promoción, corrupción y rollback aprobados")


if __name__ == "__main__":
    main()
