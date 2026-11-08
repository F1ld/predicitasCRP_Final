"""Runner host stdlib: PostgreSQL NUEVO, sin puertos/volúmenes operativos.

Conserva recursos/resultados para diagnóstico y detiene solo su contenedor propio.
Credenciales aleatorias en Temp privado, nunca en la evidencia pública.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def run(cmd, *, log=None, input=None, required=True):
    result = subprocess.run(cmd, input=input, text=True, capture_output=True)
    if log:
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
    if required and result.returncode:
        raise RuntimeError(f"Comando falló ({result.returncode}); revisar log local, no publicar credenciales")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ia-image", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,48}", args.run_id) or not re.fullmatch(r"sha256:[a-f0-9]{64}", args.ia_image):
        raise ValueError("Identidades explícitas inválidas")
    raw = ROOT / "runtime/test-results/fase-06" / args.run_id
    raw.mkdir(parents=True, exist_ok=False)
    private = Path(os.environ["LOCALAPPDATA"]) / "Temp/opencode" / ("seed-" + args.run_id)
    private.mkdir(exist_ok=False)
    user = run(["whoami"]).stdout.strip()
    run(["icacls", str(private), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"])
    identity = "predicitas-f6c-" + args.run_id
    db, network, volume = identity + "-db", identity + "-net", identity + "-pgdata"
    owner, app = secrets.token_hex(24), secrets.token_hex(24)
    database = "predicitas_f6c_test"
    pg_env = private / "postgres.env"
    pg_env.write_text(f"POSTGRES_USER=predicitas_owner\nPOSTGRES_DB={database}\nPOSTGRES_PASSWORD={owner}\n")
    app_env = private / "runtime.env"
    common = f"DATABASE_URL=postgresql+psycopg://predicitas_app:{app}@{db}/{database}\nSECRET_KEY={secrets.token_hex(32)}\nENVIRONMENT=test\n"
    app_env.write_text(common)
    admin_env = private / "migraciones.env"
    admin_env.write_text(common + f"DATABASE_URL_MIGRACIONES=postgresql+psycopg://predicitas_owner:{owner}@{db}/{database}\n")
    created = False
    try:
        for kind, name in (("container", db), ("network", network), ("volume", volume)):
            if run(["docker", kind, "inspect", name], required=False).returncode == 0:
                raise ValueError("Recurso preexistente; no adoptar ni detener")
        tag = "predicitas-backend:" + args.run_id
        if run(["docker", "image", "inspect", tag], required=False).returncode == 0:
            raise ValueError("Imagen preexistente; no sobrescribir")
        run(["docker", "build", "-t", tag, str(ROOT / "apps/backend")], log=raw / "build.log")
        image = run(["docker", "image", "inspect", "--format", "{{.Id}}", tag]).stdout.strip()
        source_paths = [ROOT / p for p in ("apps/backend/scripts/seed.py", "apps/backend/tests/test_seed_f6c.py", "compose.yaml", ".env.example")]
        source_paths += [HERE / "validar_seed_c.py", HERE / "probar_seed_c.py"]
        sources = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
        metadata = {"run_id": args.run_id, "backend_image": image, "ia_image": args.ia_image,
                    "db": db, "network": network, "volume": volume, "database": database, "sources_sha256": sources}
        (raw / "laboratorio.json").write_text(json.dumps(metadata, indent=2))
        run(["docker", "network", "create", "--internal", "--label", "predicitas.purpose=f6c-test", network])
        run(["docker", "volume", "create", "--label", "predicitas.purpose=f6c-test", volume])
        run(["docker", "run", "-d", "--name", db, "--network", network,
             "--label", "predicitas.purpose=f6c-test", "--env-file", str(pg_env),
             "--mount", f"type=volume,source={volume},target=/var/lib/postgresql/data", "postgres:16"])
        created = True
        for _ in range(90):
            ready = run(["docker", "exec", db, "pg_isready", "-h", "127.0.0.1", "-U", "predicitas_owner", "-d", database], required=False)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("PostgreSQL no listo")
        run(["docker", "exec", "-i", db, "psql", "-U", "predicitas_owner", "-d", database, "-v", "ON_ERROR_STOP=1"],
            input=f"CREATE ROLE predicitas_app LOGIN PASSWORD '{app}';\n")
        base = ["docker", "run", "--rm", "--network", network, "--read-only", "--tmpfs", "/tmp:rw,size=512m",
                "--cpus", "2", "--memory", "1g", "-e", "PYTHONPATH=/app"]
        mounts = ["--mount", f"type=bind,source={raw},target=/results",
                  "--mount", f"type=bind,source={HERE},target=/checks,readonly"]
        run([*base, "--env-file", str(admin_env), *mounts, image, "alembic", "upgrade", "head"], log=raw / "migraciones.log")
        runtime = [*base, "--env-file", str(app_env), *mounts, image]
        run([*runtime, "python", "-B", "-m", "pytest", "tests/test_seed_f6c.py", "--no-cov", "-q", "--junitxml=/results/focal.xml"], log=raw / "focal.log")
        collect = run([*runtime, "python", "-B", "-m", "pytest", "--collect-only", "--no-cov", "-q"], log=raw / "coleccion.log", required=False)
        (raw / "coleccion.json").write_text(json.dumps({"exit_code": collect.returncode}))
        # Dos verificadores de evidencia/árbol monorepo no son ejecutables desde
        # /app empaquetado: se caracterizan en colección, no se alteran ni se
        # presentan como aprobados. S-02 tests/ia sigue excluido explícitamente.
        run([*runtime, "python", "-B", "-m", "pytest", "--ignore=tests/ia",
             "--ignore=tests/sistema/test_evidencia_fase3.py", "--ignore=tests/sistema/test_archivos_fase3.py",
             "-q", "--cov=scripts.seed",
             "--junitxml=/results/diagnostico.xml", "--cov-report=json:/results/coverage.json"], log=raw / "diagnostico.log")
        # Generación canónica por proceso IA independiente, sin BD/modelo/clave.
        run(["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=256m",
             "--cpus", "2", "--memory", "1g", "--mount", f"type=bind,source={raw},target=/results", args.ia_image,
             "python", "-B", "-m", "training.cli", "--contracts-dir", "/contracts", "generar", "--version-dataset", "seed-c",
             "--semilla", "42", "--fecha-corte", "2026-10-29", "--generado-en", "2026-11-07T12:00:00-05:00",
             "--fuente", "SINTETICO_GENERADO", "--proximas", "80", "--directorio", "/results"], log=raw / "generacion.log")
        run([*base, "--env-file", str(app_env), *mounts, "--mount", f"type=bind,source={raw / 'seed-c'},target=/inputs,readonly",
             image, "python", "-B", "/checks/probar_seed_c.py"], log=raw / "integracion.log")
        print("Bloque C: focales, diagnóstico y seed CLI integral aprobados; revisar colección completa caracterizada.")
    finally:
        if created:
            info = json.loads(run(["docker", "inspect", db]).stdout)[0]
            env = dict(line.split("=", 1) for line in info["Config"]["Env"] if "=" in line)
            assert (info["Config"]["Labels"].get("predicitas.purpose") == "f6c-test"
                    and env.get("POSTGRES_PASSWORD") == owner
                    and network in info["NetworkSettings"]["Networks"])
            run(["docker", "stop", db], log=raw / "parada.log")
            (raw / "parada.json").write_text(json.dumps({"container": db, "stopped": True, "resources_preserved": True}))


if __name__ == "__main__":
    main()
