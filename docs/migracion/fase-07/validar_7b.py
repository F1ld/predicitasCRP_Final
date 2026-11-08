"""7B: imagen nueva + PostgreSQL nuevo interno + IA real. Sin Compose/principal."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
IA_IMAGE = "sha256:6d1ee8581301819845e0d324fe3864fc2f48cb1fe35b68529fddd8e2e29a2853"


def run(command, *, log=None, required=True, input=None):
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", input=input)
    if log:
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
    if required and result.returncode:
        raise RuntimeError(f"Comando falló ({result.returncode}); revisar log local {log}")
    return result


def sha(paths):
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nombre", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", args.nombre):
        parser.error("Nombre no válido")
    raw = ROOT / "runtime/fase-07" / args.nombre
    raw.mkdir(parents=True, exist_ok=False)
    private = Path(os.environ["LOCALAPPDATA"]) / "Temp/opencode" / ("f7b-" + args.nombre)
    private.mkdir(exist_ok=False)
    user = run(["whoami"]).stdout.strip()
    run(["icacls", str(private), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"])
    identity = "predicitas-f7b-" + args.nombre
    db, ia, network, volume = (identity + suffix for suffix in ("-db", "-ia", "-net", "-pgdata"))
    database = "predicitas_f7b_test"
    protected = [ROOT / p for p in (".env", "compose.yaml", "apps/backend/app/modules/ia/predictor.py",
        "apps/backend/app/modules/citas/public.py")]
    protected += list((ROOT / "contracts").rglob("*.json")) + list((ROOT / "artifacts/models").rglob("*.joblib"))
    protected += list((ROOT / "apps/backend/app/modules/ia/artifacts").rglob("*.joblib"))
    before, running = sha(protected), run(["docker", "ps", "-q"]).stdout.splitlines()
    owner, app_password, key = (secrets.token_hex(24) for _ in range(3))
    common = f"DATABASE_URL=postgresql+psycopg://predicitas_app:{app_password}@{db}/{database}\nSECRET_KEY={secrets.token_hex(32)}\nENVIRONMENT=test\nIA_API_KEY={key}\nIA_HTTP_TEST_URL=http://{ia}:8100\n"
    (private / "postgres.env").write_text(f"POSTGRES_USER=predicitas_owner\nPOSTGRES_DB={database}\nPOSTGRES_PASSWORD={owner}\n")
    (private / "app.env").write_text(common)
    (private / "admin.env").write_text(common + f"DATABASE_URL_MIGRACIONES=postgresql+psycopg://predicitas_owner:{owner}@{db}/{database}\n")
    (private / "ia.env").write_text(f"IA_API_KEY={key}\n")
    created = []
    try:
        for kind, name in (("container", db), ("container", ia), ("network", network), ("volume", volume)):
            if run(["docker", kind, "inspect", name], required=False).returncode == 0:
                raise RuntimeError("Recurso preexistente; no adoptar")
        tag = "predicitas-backend:" + args.nombre
        if run(["docker", "image", "inspect", tag], required=False).returncode == 0:
            raise RuntimeError("Imagen preexistente; no sobrescribir")
        run(["docker", "build", "-t", tag, str(ROOT / "apps/backend")], log=raw / "build.log")
        image = run(["docker", "image", "inspect", "--format", "{{.Id}}", tag]).stdout.strip()
        run(["docker", "network", "create", "--internal", network])
        run(["docker", "volume", "create", volume])
        run(["docker", "run", "-d", "--name", db, "--network", network, "--env-file", str(private / "postgres.env"),
            "--mount", f"type=volume,source={volume},target=/var/lib/postgresql/data", "postgres:16"])
        created.append(db)
        for _ in range(90):
            if run(["docker", "exec", db, "pg_isready", "-U", "predicitas_owner", "-d", database], required=False).returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("PostgreSQL no listo")
        run(["docker", "exec", "-i", db, "psql", "-U", "predicitas_owner", "-d", database, "-v", "ON_ERROR_STOP=1"],
            input=f"CREATE ROLE predicitas_app LOGIN PASSWORD '{app_password}';\n")
        base = ["docker", "run", "--rm", "--network", network, "--read-only", "--tmpfs", "/tmp:rw,size=512m",
            "--cpus", "2", "--memory", "1g", "-e", "OMP_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1", "-e", "MKL_NUM_THREADS=1",
            "--mount", f"type=bind,source={raw},target=/results", "--mount", f"type=bind,source={HERE},target=/checks,readonly"]
        run([*base, "--env-file", str(private / "admin.env"), image, "alembic", "upgrade", "head"], log=raw / "migraciones.log")
        run(["docker", "run", "-d", "--name", ia, "--network", network, "--read-only", "--tmpfs", "/tmp:rw,size=256m",
            "--cpus", "2", "--memory", "1g", "--env-file", str(private / "ia.env"),
            "--mount", f"type=bind,source={ROOT / 'artifacts/models/legacy-import'},target=/models,readonly", IA_IMAGE])
        created.append(ia)
        for _ in range(120):
            if run(["docker", "exec", ia, "curl", "-fsS", "http://127.0.0.1:8100/health/ready"], required=False).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("IA no lista")
        runtime = [*base, "--env-file", str(private / "app.env"), image]
        run([*runtime, "python", "-B", "-m", "pytest", "tests/test_motor_7b.py", "--no-cov", "-q", "--junitxml=/results/focal.xml"], log=raw / "focal.log")
        run([*runtime, "python", "-B", "-m", "pytest", "--collect-only", "--no-cov", "-q"], log=raw / "coleccion.log", required=False)
        run([*runtime, "python", "-B", "-m", "pytest", "--ignore=tests/ia", "--ignore=tests/sistema/test_evidencia_fase3.py",
            "--ignore=tests/sistema/test_archivos_fase3.py", "--no-cov", "-q", "--junitxml=/results/regresion.xml"], log=raw / "regresion.log")
        run([*runtime, "python", "-B", "/checks/probar_concurrencia_7b.py"], log=raw / "concurrencia.log")
        counts = {}
        for name in ("focal", "regresion"):
            suites = ET.parse(raw / f"{name}.xml").getroot()
            counts[name] = {k: sum(int(s.get(k, "0")) for s in suites.iter("testsuite")) for k in ("tests", "failures", "errors", "skipped")}
        concurrency = json.loads((raw / "concurrencia.json").read_text())
        summary = dict(run_id=args.nombre, baseline="3700c5f + 7A sin commit", backend_image=image, ia_image=IA_IMAGE,
            tests=counts, concurrency=concurrency, database=database, db=db, ia=ia, network=network, volume=volume,
            sources=sha(list((ROOT / "apps/backend/app/modules/ia").glob("*.py")) + [ROOT / p for p in
                ("apps/backend/app/main.py", "apps/backend/app/core/config.py", "apps/backend/app/modules/citas/router.py", "apps/backend/tests/test_motor_7b.py")]),
            protected_unchanged=before == sha(protected), full_suite_green=False, default_motor="integrado", schema_changed=False)
    finally:
        for container in reversed(created):
            run(["docker", "stop", container], log=raw / f"stop-{container}.log")
        assert before == sha(protected), "Archivo protegido cambió"
        assert sorted(running) == sorted(run(["docker", "ps", "-q"]).stdout.splitlines()), "Cambió el conjunto activo"
    summary.update(resources_preserved=True, containers_stopped=True, running_containers_unchanged=True)
    (raw / "resumen.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
