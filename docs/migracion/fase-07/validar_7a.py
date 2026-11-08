"""Laboratorio 7A sin BD ni Compose. Conserva contenedores detenidos y evidencia."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[3]
IMAGE = "sha256:5e797c24b24b0f4056eb4cbf79184225eaebf14db7c2078e9ad28d0b288eba54"


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8", **kwargs).stdout


def hashes(paths):
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nombre", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,50}", args.nombre):
        parser.error("Nombre de ejecución no válido")
    evidence = ROOT / "runtime/fase-07" / args.nombre
    evidence.mkdir(parents=True, exist_ok=False)
    protected = [ROOT / p for p in (".env", "compose.yaml", "apps/backend/app/main.py",
        "apps/backend/app/modules/ia/service.py", "apps/backend/app/modules/ia/predictor.py",
        "apps/backend/app/modules/ia/router.py", "apps/backend/app/modules/citas/public.py")]
    protected += list((ROOT / "contracts").rglob("*.json"))
    protected += list((ROOT / "artifacts/models").rglob("*.joblib"))
    protected += list((ROOT / "apps/backend/app/modules/ia/artifacts").rglob("*.joblib"))
    before = hashes(protected)
    running = run(["docker", "ps", "-q"]).splitlines()
    assert run(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE]).strip() == IMAGE
    base = ["docker", "run", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,nosuid,size=256m",
        "--cpus", "2", "--memory", "1g", "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "OMP_NUM_THREADS=1", "--env", "OPENBLAS_NUM_THREADS=1", "--env", "MKL_NUM_THREADS=1",
        "--env", "BACKEND_SOURCE_DIR=/backend"]
    for source, target, readonly in ((ROOT / "apps/backend", "/backend", True),
            (ROOT / "apps/ia", "/ia", True), (ROOT / "artifacts/models/legacy-import", "/models", True),
            (ROOT / "docs/migracion/fase-07", "/checks", True), (evidence, "/evidence", False)):
        base += ["--mount", f"type=bind,source={source},target={target}" + (",readonly" if readonly else "")]
    containers = []
    try:
        for suffix, script in (("unit", "test_motor_7a.py"), ("http", "probar_http_7a.py")):
            name = f"predicitas-f7a-{args.nombre}-{suffix}"
            containers.append(name)
            env = os.environ.copy()
            env["IA_API_KEY"] = secrets.token_hex(32)
            command = base + ["--name", name, "--env", "IA_API_KEY", "--entrypoint", "python", IMAGE,
                              "-B", f"/checks/{script}"]
            result = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8")
            (evidence / f"{suffix}.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
            if result.returncode:
                raise RuntimeError(f"Falló {suffix}; revisar evidencia privada {evidence}")
        http = json.loads((evidence / "http-7a.json").read_text(encoding="utf-8"))
    finally:
        assert before == hashes(protected), "Cambió un archivo protegido"
        assert sorted(running) == sorted(run(["docker", "ps", "-q"]).splitlines()), "Cambió el conjunto de contenedores activos"
    source_paths = list((ROOT / "docs/migracion/fase-07").glob("*.py")) + [ROOT / f"apps/backend/app/modules/ia/{p}.py"
        for p in ("puerto", "motor_http", "motor_integrado")]
    summary = dict(run_id=args.nombre, baseline="3700c5f", image=IMAGE, tests_unitarios=19,
        http=http, sources=hashes(source_paths), protected_unchanged=True, running_containers_unchanged=True,
        containers=containers, containers_stopped=True, database_used=False,
        limits="Sin cableado de rutas ni regresión BD; imágenes con fuentes RO, no build limpio nuevo.")
    (evidence / "resumen.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
