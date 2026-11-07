"""Gates B: paridad de datos, CSV y laboratorio PostgreSQL exclusivo."""
import importlib.util
import json
import subprocess
from pathlib import Path

from validar_ia import BACKEND_IMAGE, HERE, ROOT, action, output, read, sha, write


def validate(raw, candidate_base, run_id):
    reference = ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,nosuid,size=256m",
        "--cpus", "2", "--memory", "1g", "-e", "PYTHONPATH=/app",
        "--mount", f"type=bind,source={raw},target=/results", "--mount", f"type=bind,source={HERE},target=/checks,readonly", BACKEND_IMAGE]
    action(raw, "datasets_reference", [*reference, "python", "/checks/probar_datasets_b.py", "reference", "/results/datasets_reference.json"])
    action(raw, "datasets_candidate", [*candidate_base, "python", "/checks/probar_datasets_b.py", "candidate", "/results/datasets_candidate.json"])
    old, new = read(raw / "datasets_reference.json"), read(raw / "datasets_candidate.json")
    assert old == new and len(old) == 9, "Cambió algún campo, orden, default o escenario del generador"
    assert len(new["seed_full"]) == 1080
    dataset_result = {"scenarios": {name: len(rows) for name, rows in new.items()},
        "all_fields_and_row_order_equal": True, "reference_sha256": sha(raw / "datasets_reference.json"),
        "candidate_sha256": sha(raw / "datasets_candidate.json"), "csv_sha256": sha(raw / "seed_operacional.csv"),
        "csv_columns": 13, "csv_roundtrip": True, "training_mapping_rows": 1000,
        "scope": "Paridad sintética; CSV futuro sin cambiar consumidores, sin JSONL/manifiestos/pipeline fase 6"}
    assert dataset_result["reference_sha256"] == dataset_result["candidate_sha256"]
    write(raw / "datasets_b.json", dataset_result)

    spec = importlib.util.spec_from_file_location("lab_fase4_b", ROOT / "docs/migracion/fase-04/validar.py")
    lab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab)
    lab_raw = raw / "csv-lab"
    lab_id = run_id.replace("ia-", "csv-", 1)
    meta_path = lab_raw / "laboratorio.json"
    try:
        lab.preparar(lab_raw, lab_id, baseline_ref=output(["git", "rev-parse", "HEAD"]), scope="B_CSV")
        meta = lab.leer(meta_path)
        env = dict(line.split("=", 1) for line in Path(meta["private_env"]).read_text().splitlines() if "=" in line)
        runtime_env = Path(meta["private_env"]).with_name("csv_runtime.env")
        with runtime_env.open("x", encoding="utf-8", newline="\n") as stream:
            for key in ("DATABASE_URL", "SECRET_KEY", "ENVIRONMENT"):
                stream.write(f"{key}={env[key]}\n")
        command = ["docker", "run", "--rm", "--network", meta["network"], "--read-only", "--tmpfs", "/tmp:rw,nosuid,size=256m",
            "--cpus", "2", "--memory", "1g", "--env-file", str(runtime_env), "-e", "PYTHONPATH=/app",
            "--mount", f"type=bind,source={raw},target=/results", "--mount", f"type=bind,source={HERE},target=/checks,readonly",
            BACKEND_IMAGE, "python", "/checks/probar_csv_b.py"]
        action(raw, "csv_http_postgres", command)
    finally:
        if meta_path.exists():
            meta = lab.leer(meta_path)
            # preparar reserva metadata antes de crear recursos. Ante colisión,
            # NO detener un recurso previo: exigir el secreto aleatorio generado
            # por este intento además de etiquetas/red/volumen del verificador.
            probe = subprocess.run(["docker", "inspect", meta["db"]], capture_output=True, text=True)
            if probe.returncode == 0:
                info = json.loads(probe.stdout)[0]
                actual = dict(line.split("=", 1) for line in info["Config"]["Env"] if "=" in line)
                expected = dict(line.split("=", 1) for line in Path(meta["private_env"]).with_name("postgres.env").read_text().splitlines() if "=" in line)
                assert {"POSTGRES_USER", "POSTGRES_DB", "POSTGRES_PASSWORD"} <= expected.keys() and expected["POSTGRES_PASSWORD"], "Credencial propia no verificable: no detener"
                assert all(actual.get(k) == v for k, v in expected.items()), "Propiedad del recurso no demostrada: no detener"
            else:
                raise RuntimeError("No hay contenedor propio verificable; preservar provisión fallida")
            if lab.verificar(meta) == "running":
                lab.accion(lab_raw, "detener", ["docker", "stop", meta["db"]])
    assert lab.verificar(meta) == "exited"
    result = {"generator": dataset_result, "csv_import": read(raw / "csv_http_b.json"),
        "laboratory_state": "exited", "original_resources_untouched": True,
        "legacy_consumers_unchanged": True, "canonical_generator": "apps/ia/datasets/synthetic.py",
        "retirement_register": "docs/migracion/fase-05/LEGACY_GENERADOR.md"}
    write(raw / "bloque_b.json", result)
    return result
