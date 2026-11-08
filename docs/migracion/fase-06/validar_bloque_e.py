"""Orquesta el bloque E: paquete limpio, imágenes limpias, laboratorio nuevo.

Recorre generar → validar → entrenar → promover → servir → sembrar → backend
sin tocar la BD, el compose ni el modelo activos. Conserva recursos del
laboratorio propio para diagnóstico y detiene solo su contenedor.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

from soporte_e import package, sha, source_index, tree_hashes, unpack

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PROTECTED = (
    ".env",
    "apps/backend/.env",
    "apps/frontend/.env",
    "apps/backend/app/modules/ia/artifacts/modelo_predicitas_v1.joblib",
    "artifacts/models/legacy-import/modelo_predicitas_v1.joblib",
)
SOURCES = (
    "docs/migracion/fase-06/soporte_e.py",
    "docs/migracion/fase-06/servidor_guardado_e.py",
    "docs/migracion/fase-06/probar_serving_e.py",
    "docs/migracion/fase-06/probar_pipeline_e.py",
    "docs/migracion/fase-06/probar_seed_e.py",
    "docs/migracion/fase-06/probar_backend_e.py",
    "docs/migracion/fase-06/validar_bloque_e.py",
    "apps/ia/training/pipeline.py",
    "apps/ia/management/releases.py",
    "apps/backend/scripts/seed.py",
)


def run(command, log=None, *, input=None, required=True):
    result = subprocess.run(command, input=input, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if log is not None:
        with Path(log).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write((result.stdout or "") + (result.stderr or ""))
    if required and result.returncode:
        raise RuntimeError(f"Comando falló ({result.returncode}): {' '.join(command[:4])}; revisar log")
    return result


def wait_postgres(container, database):
    for _ in range(90):
        ready = run(["docker", "exec", container, "pg_isready", "-h", "127.0.0.1",
                     "-U", "predicitas_owner", "-d", database], required=False)
        if ready.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("PostgreSQL no listo")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,40}", args.run_id):
        raise ValueError("run-id inválido")
    raw = ROOT / "runtime/test-results/fase-06" / args.run_id
    raw.mkdir(parents=True, exist_ok=False)
    private = Path(os.environ["LOCALAPPDATA"]) / "Temp/opencode" / ("e-" + args.run_id)
    private.mkdir(exist_ok=False)
    user = run(["whoami"]).stdout.strip()
    run(["icacls", str(private), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"])

    protected = [ROOT / name for name in PROTECTED]
    protected_before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in protected if p.is_file()}
    running_before = set(run(["docker", "ps", "--format", "{{.ID}}"]).stdout.split())
    sources = {name: sha(ROOT / name) for name in SOURCES}

    # 1. Índice, paquete y reconstrucción limpia sin artefactos, secretos ni runtime.
    index = source_index(ROOT)
    (raw / "fuente-limpia.indice.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    archive = raw / "fuente-limpia.zip"
    package(ROOT, archive, index)
    clean = raw / "fuente-limpia"
    unpack(archive, clean, index)
    reconstructed = tree_hashes(clean)
    assert reconstructed == index, "La reconstrucción no coincide con el índice"
    assert not any(name.endswith(".joblib") or "/artifacts/" in name for name in reconstructed)
    assert not any(Path(name).name.startswith(".env") and Path(name).name != ".env.example"
                   for name in reconstructed)
    package_summary = {
        "files": len(index),
        "archive_sha256": sha(archive),
        "index_sha256": hashlib.sha256(json.dumps(index, sort_keys=True).encode()).hexdigest(),
        "reconstructed_equal": True,
        "no_joblib": True,
        "no_artifacts": True,
        "no_secrets": True,
    }

    # 2. Imágenes construidas solo desde el árbol limpio reconstruido.
    ia_tag = "predicitas-ia:e-" + args.run_id
    backend_tag = "predicitas-backend:e-" + args.run_id
    for tag in (ia_tag, backend_tag):
        if run(["docker", "image", "inspect", tag], required=False).returncode == 0:
            raise ValueError("Imagen preexistente; no sobrescribir")
    run(["docker", "build", "--build-context", f"contracts={clean / 'contracts'}",
         "-f", str(clean / "apps/ia/Dockerfile"), "-t", ia_tag, str(clean / "apps/ia")],
        raw / "build-ia.log")
    ia_image = run(["docker", "image", "inspect", "--format", "{{.Id}}", ia_tag]).stdout.strip()
    run(["docker", "build", "-f", str(clean / "apps/backend/Dockerfile"), "-t", backend_tag,
         str(clean / "apps/backend")], raw / "build-backend.log")
    backend_image = run(["docker", "image", "inspect", "--format", "{{.Id}}", backend_tag]).stdout.strip()
    assert re.fullmatch(r"sha256:[a-f0-9]{64}", ia_image)
    assert re.fullmatch(r"sha256:[a-f0-9]{64}", backend_image)
    backend_has_model = run([
        "docker", "run", "--rm", "--network", "none", backend_image, "python", "-B", "-c",
        "from pathlib import Path; raise SystemExit(0 if list(Path('/app').rglob('*.joblib')) else 1)",
    ], required=False).returncode == 0
    assert not backend_has_model, "La imagen backend limpia no debe incluir modelo"
    ia_has_db = run([
        "docker", "run", "--rm", "--network", "none", ia_image, "python", "-B", "-c",
        "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('sqlalchemy') else 1)",
    ], required=False).returncode == 0
    assert not ia_has_db, "La imagen IA limpia no debe incluir SQLAlchemy"
    image_summary = {
        "ia_tag": ia_tag, "ia_image": ia_image, "backend_tag": backend_tag,
        "backend_image": backend_image, "backend_without_model": True,
        "ia_without_database_dependencies": True,
    }

    # 3. Laboratorio PostgreSQL nuevo, sin puertos ni volúmenes operativos.
    identity = "predicitas-f6e-" + args.run_id
    db, network, volume = identity + "-db", identity + "-net", identity + "-pgdata"
    owner, app = secrets.token_hex(24), secrets.token_hex(24)
    database = "predicitas_f6e_test"
    pg_env = private / "postgres.env"
    pg_env.write_text(f"POSTGRES_USER=predicitas_owner\nPOSTGRES_DB={database}\nPOSTGRES_PASSWORD={owner}\n")
    runtime_env = private / "runtime.env"
    common = (f"DATABASE_URL=postgresql+psycopg://predicitas_app:{app}@{db}:5432/{database}\n"
              f"SECRET_KEY={secrets.token_hex(32)}\nENVIRONMENT=test\n")
    runtime_env.write_text(common)
    admin_env = private / "migraciones.env"
    admin_env.write_text(common + f"DATABASE_URL_MIGRACIONES=postgresql+psycopg://predicitas_owner:{owner}@{db}:5432/{database}\n")
    seed_password = "QA9-" + secrets.token_urlsafe(24)
    ia_key = secrets.token_urlsafe(32)

    for kind, name in (("container", db), ("network", network), ("volume", volume)):
        if run(["docker", kind, "inspect", name], required=False).returncode == 0:
            raise ValueError("Recurso preexistente; no adoptar ni detener")
    run(["docker", "network", "create", "--internal", "--label", "predicitas.purpose=f6e-test", network])
    run(["docker", "volume", "create", "--label", "predicitas.purpose=f6e-test", volume])
    created = False
    shared = ["--mount", f"type=bind,source={HERE},target=/checks,readonly",
              "--mount", f"type=bind,source={raw},target=/results"]
    base = ["docker", "run", "--rm", "--network", network, "--read-only", "--tmpfs", "/tmp:rw,size=512m",
            "--cpus", "2", "--memory", "1g", "-e", "PYTHONPATH=/app"]
    try:
        run(["docker", "run", "-d", "--name", db, "--network", network,
             "--label", "predicitas.purpose=f6e-test", "--env-file", str(pg_env),
             "--mount", f"type=volume,source={volume},target=/var/lib/postgresql/data", "postgres:16"])
        created = True
        wait_postgres(db, database)
        run(["docker", "exec", "-i", db, "psql", "-U", "predicitas_owner", "-d", database, "-v", "ON_ERROR_STOP=1"],
            input=f"CREATE ROLE predicitas_app LOGIN PASSWORD '{app}';\n")

        run([*base, "--env-file", str(admin_env), *shared, backend_image, "alembic", "upgrade", "head"],
            raw / "migraciones.log")

        work = raw / "work"
        work.mkdir()
        isolated = ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=512m",
                    "--cpus", "2", "--memory", "1g", "-e", "PYTHONPATH=/app", "-e", "OMP_NUM_THREADS=1"]
        contracts = clean / "contracts"
        run([*isolated, "--mount", f"type=bind,source={contracts},target=/contracts,readonly",
             "--mount", f"type=bind,source={HERE},target=/checks,readonly",
             "--mount", f"type=bind,source={work},target=/work",
             "--mount", f"type=bind,source={raw},target=/results",
             ia_image, "python", "-B", "/checks/probar_pipeline_e.py", "--work", "/work",
             "--results", "/results"], raw / "pipeline.log")
        pipeline = json.loads((raw / "pipeline-e.json").read_text(encoding="utf-8"))
        assert pipeline["dataset"]["seed_rows"] == 1080 and pipeline["dataset"]["total_historicas"] == 1000
        assert pipeline["candidates"]["metrics_equal"] and pipeline["candidates"]["predictions_equal"]
        assert pipeline["promotion"]["tamper_rejected"] and pipeline["promotion"]["state_unchanged_after_tamper"]
        assert pipeline["registry"]["final_active"] == "e-model-b"
        approval = pipeline["registry"]["approval_sha256"]
        assert re.fullmatch(r"[a-f0-9]{64}", approval)

        run([*isolated, "-e", f"IA_API_KEY={ia_key}", "-e", "IA_RELEASE_VERSION=e-model-b",
             "-e", f"IA_APPROVAL_SHA256={approval}", "-e", "MODEL_REGISTRY_DIR=/models",
             "--mount", f"type=bind,source={work / 'registry'},target=/models,readonly",
             "--mount", f"type=bind,source={contracts},target=/contracts,readonly",
             "--mount", f"type=bind,source={HERE},target=/checks,readonly",
             "--mount", f"type=bind,source={raw},target=/results",
             ia_image, "python", "-B", "/checks/probar_serving_e.py", "--version", "e-model-b",
             "--nombre", "serving-e"], raw / "serving.log")

        empty = raw / "registro-vacio"
        empty.mkdir()
        run([*isolated, "-e", f"IA_API_KEY={ia_key}", "-e", "MODEL_REGISTRY_DIR=/models",
             "--mount", f"type=bind,source={empty},target=/models,readonly",
             "--mount", f"type=bind,source={contracts},target=/contracts,readonly",
             "--mount", f"type=bind,source={HERE},target=/checks,readonly",
             "--mount", f"type=bind,source={raw},target=/results",
             ia_image, "python", "-B", "/checks/probar_serving_e.py", "--version", "ninguno",
             "--nombre", "serving-e-sin-modelo", "--no-listo"], raw / "serving-sin-modelo.log")

        dataset_dir = work / "datasets" / "e-dataset"
        run([*base, "--env-file", str(runtime_env), "-e", f"SEED_PASSWORD={seed_password}",
             "--mount", f"type=bind,source={dataset_dir},target=/inputs,readonly", *shared,
             backend_image, "python", "-B", "/checks/probar_seed_e.py"], raw / "seed.log")
        run([*base, "--env-file", str(runtime_env), "-e", f"SEED_PASSWORD={seed_password}", *shared,
             backend_image, "python", "-B", "/checks/probar_backend_e.py"], raw / "backend.log")
    finally:
        if created:
            info = json.loads(run(["docker", "inspect", db]).stdout)[0]
            env = dict(line.split("=", 1) for line in info["Config"]["Env"] if "=" in line)
            assert (info["Config"]["Labels"].get("predicitas.purpose") == "f6e-test"
                    and env.get("POSTGRES_PASSWORD") == owner
                    and network in info["NetworkSettings"]["Networks"])
            run(["docker", "stop", db], raw / "parada.log")
            (raw / "parada.json").write_text(json.dumps(
                {"container": db, "stopped": True, "resources_preserved": True}), encoding="utf-8")

    gate = run([sys.executable, "-B", str(HERE / "inventariar_legacy_d.py"),
                "--exigir-cierre-programado"], raw / "inventario.json")
    inventory = json.loads(gate.stdout)
    assert inventory["scheduled_closure_ready"] and len(inventory["references"]) == 2
    assert not inventory["retirement_allowed"]
    assert protected_before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in protected if p.is_file()}
    running_after = set(run(["docker", "ps", "--format", "{{.ID}}"]).stdout.split())
    assert running_after == running_before, "El conjunto de contenedores en ejecución cambió"
    assert sources == {name: sha(ROOT / name) for name in SOURCES}

    pipeline = json.loads((raw / "pipeline-e.json").read_text(encoding="utf-8"))
    serving = json.loads((raw / "serving-e.json").read_text(encoding="utf-8"))
    no_model = json.loads((raw / "serving-e-sin-modelo.json").read_text(encoding="utf-8"))
    seed = json.loads((raw / "seed-e.json").read_text(encoding="utf-8"))
    backend = json.loads((raw / "backend-e.json").read_text(encoding="utf-8"))
    result = {
        "run_id": args.run_id,
        "package": package_summary,
        "images": image_summary,
        "pipeline": {
            "dataset_manifest_sha256": pipeline["dataset"]["manifest_sha256"],
            "seed_sha256": pipeline["dataset"]["seed_sha256"],
            "seed_rows": pipeline["dataset"]["seed_rows"],
            "metrics_equal": pipeline["candidates"]["metrics_equal"],
            "predictions_equal": pipeline["candidates"]["predictions_equal"],
            "artifact_bytes_equal": pipeline["candidates"]["artifact_bytes_equal"],
            "tamper_rejected": pipeline["promotion"]["tamper_rejected"],
            "final_active": pipeline["registry"]["final_active"],
            "approval_sha256": pipeline["registry"]["approval_sha256"],
        },
        "serving": {
            "ready": serving["ready"], "http_tcp": serving["http_tcp"],
            "worker_guardado": serving["worker_guardado"], "batch_cases": serving["batch_cases"],
            "registry_unchanged": serving["registry_unchanged"],
            "prediction_digest": serving["prediction_digest"],
            "sin_modelo_ready": no_model["ready"], "sin_modelo_http_tcp": no_model["http_tcp"],
        },
        "seed": seed,
        "backend": backend,
        "legacy_gate": {
            "references": len(inventory["references"]),
            "scheduled_closure_ready": inventory["scheduled_closure_ready"],
            "retirement_allowed": inventory["retirement_allowed"],
        },
        "lab": {"db": db, "network": network, "volume": volume, "database": database,
                "container_stopped": True, "resources_preserved": True},
        "protected_unchanged": True,
        "running_containers_unchanged": True,
        "sources": sources,
        "scope": "Bloque E: recorrido limpio aislado; sin tocar BD/compose/modelo activos; fase 7 no iniciada.",
    }
    (raw / "resumen.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2),
                                      encoding="utf-8")
    print("Bloque E: paquete e imágenes limpias, pipeline, serving, seed y backend aprobados.")


if __name__ == "__main__":
    main()
