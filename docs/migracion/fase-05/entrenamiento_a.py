"""Gates adicionales de bloque A, invocados explícitamente por el runner formal."""
import hashlib
import json

from validar_ia import BACKEND_IMAGE, HERE, action, output, read, sha, write


def validate(raw, candidate_base):
    # Solo fixture QA temporal: usa el generador preservado, NO lo extrae (bloque B).
    dataset = output(["docker", "run", "--rm", "--network", "none", "--cpus", "2", "--memory", "1g",
        "-e", "OMP_NUM_THREADS=1", "-e", "DATABASE_URL=postgresql+psycopg://unused:unused@invalid/unused",
        "-e", "SECRET_KEY=offline-no-auth-no-connection", BACKEND_IMAGE, "python", "-c",
        "import json; from app.modules.ia.predictor import cargar_citas_historicas; print(json.dumps(cargar_citas_historicas()))"])
    records = json.loads(dataset)
    assert len(records) == 1000 and len({r["id_cita_externa"] for r in records}) == 1000
    write(raw / "training_fixture.json", records)
    reference = ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,nosuid,size=256m",
        "--cpus", "2", "--memory", "1g", "-e", "PYTHONPATH=/app", "-e", "OMP_NUM_THREADS=1",
        "-e", "OPENBLAS_NUM_THREADS=1", "-e", "MKL_NUM_THREADS=1",
        "-e", "DATABASE_URL=postgresql+psycopg://unused:unused@invalid/unused", "-e", "SECRET_KEY=offline-no-auth-no-connection",
        "--mount", f"type=bind,source={raw},target=/results", "--mount", f"type=bind,source={HERE},target=/checks,readonly", BACKEND_IMAGE]
    # Abrir la fixture desde /results: no credenciales/filas operativas ni stdin secreto.
    code = "import runpy,sys; sys.stdin=open('/results/training_fixture.json'); sys.argv=['probe',sys.argv[1],sys.argv[2]]; runpy.run_path('/checks/probar_entrenamiento_a.py',run_name='__main__')"
    action(raw, "training_reference", [*reference, "python", "-c", code, "reference", "/results/training_reference.json"])
    action(raw, "training_candidate", [*candidate_base, "python", "-c", code, "candidate", "/results/training_candidate.json"])
    old, new = read(raw / "training_reference.json"), read(raw / "training_candidate.json")
    assert old["comparison"] == new["comparison"], "Extracción cambió entrenamiento/evaluación"
    assert all(old["proof"].values()) and all(new["proof"].values())
    assert old["model_version"] == "LightGBM_v1.0.0" and new["model_version"] == "QA_A_CANDIDATE"
    # El reporte público no contiene filas de entrenamiento ni pipelines serializados.
    metadata = new["comparison"]["metadata"]
    result = {"records": len(records), "fixture_sha256": sha(raw / "training_fixture.json"),
        "source": "Generador legacy preservado, fixture QA explícita; sin extracción de generador en A",
        "backend_image": BACKEND_IMAGE, "same_preprocessing_estimators_hyperparameters": True,
        "same_split_indices": True, "same_raw_probabilities_all_1000_both_models": True,
        "same_metrics_equity_importance": True, "same_feature_normalization": True,
        "comparison_sha256": hashlib.sha256(json.dumps(new["comparison"], sort_keys=True).encode()).hexdigest(),
        "split_sizes": [s["rows"] for s in new["comparison"]["splits"]],
        "metricas_test": metadata["metricas_test"], "metricas_baseline_test": metadata["metricas_baseline_test"],
        "proof": new["proof"], "identity_differences_only": ["version_modelo", "dataset_info.version_dataset"],
        "scope": "Entrenamientos de prueba en /tmp nuevos; sin promoción, CLI productivo, registry ni pipeline fase 6"}
    write(raw / "training_a.json", result)
    return result
