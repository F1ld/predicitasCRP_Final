"""Compara backend antes/después dentro de contenedores y PostgreSQL aislados."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    stage = sys.argv[1]
    assert stage in ("antes", "despues")
    lab = json.loads((HERE / "laboratorio.json").read_text(encoding="utf-8"))
    private = Path(lab["private_directory"])
    folder = ROOT / ("backend-predicitas" if stage == "antes" else "apps/backend")
    image = "predicitas-crp-backend:latest" if stage == "antes" else "predicitas-fase2-backend:validacion"
    output = HERE / f"backend_{stage}.json"
    if output.exists():
        raise SystemExit("No sobrescribir evidencia")
    if stage == "antes":
        for sql in ("CREATE DATABASE predicitas_fase2_smoke OWNER predicitas_owner;",):
            subprocess.run(["docker", "exec", "-i", lab["db"], "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "predicitas_owner", "-d", "postgres"], input=sql, text=True, check=True, capture_output=True)
        subprocess.run(["docker", "exec", lab["db"], "pg_restore", "-U", "predicitas_owner", "-d", "predicitas_fase2_smoke", "/tmp/crp.dump"], check=True, capture_output=True)
        smoke = private / "smoke.env"
        smoke.write_text(smoke.read_text(encoding="utf-8").replace(":5432/predicitas\n", ":5432/predicitas_fase2_smoke\n"), encoding="utf-8")
    common = ["docker", "run", "--rm", "--network", lab["network"], "--mount", f"type=bind,source={folder},target=/workspace,readonly", "--mount", f"type=bind,source={HERE},target=/evidence", "-w", "/workspace"]
    checks = [
        ("alembic_test_upgrade", "tests.env", ["alembic", "upgrade", "head"]),
        ("alembic_existing_current", "smoke.env", ["alembic", "current"]),
        ("alembic_heads", "tests.env", ["alembic", "heads"]),
        ("pytest_completo", "tests.env", ["python", "-m", "pytest", f"--junitxml=/evidence/backend_{stage}_completo.xml"]),
        ("pytest_diagnostico", "tests.env", ["python", "-m", "pytest", "--ignore=tests/ia", f"--junitxml=/evidence/backend_{stage}_diagnostico.xml", f"--cov-report=json:/evidence/backend_{stage}_coverage.json"]),
        ("smoke", "smoke.env", ["python", "/evidence/smoke_backend.py", stage]),
    ]
    results = []
    for name, envfile, cmd in checks:
        if stage == "despues" and name == "alembic_test_upgrade":
            cmd = ["alembic", "current"]  # No reaplicar migraciones a una BD de tests existente.
        log = HERE / f"backend_{stage}_{name}.log"
        start = time.monotonic()
        with log.open("x", encoding="utf-8") as stream:
            result = subprocess.run([*common, "--env-file", str(private / envfile), image, *cmd], stdout=stream, stderr=subprocess.STDOUT)
        results.append({"check": name, "command": cmd, "exit_code": result.returncode, "seconds": round(time.monotonic() - start, 2), "log": log.name})
        print(f"{stage}: {name}: {result.returncode}", flush=True)
        if name.startswith("alembic") and result.returncode:
            raise SystemExit("Gate Alembic fallo; detener pruebas")
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
