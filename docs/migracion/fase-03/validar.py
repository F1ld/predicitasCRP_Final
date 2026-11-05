"""Validaciones reproducibles fase3. Solo PostgreSQL NUEVO y aislado; nunca principal."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RESULTS = ROOT / "runtime/test-results/fase-03"
IMAGE = "predicitas-fase3-backend:validacion"
SUFIJO = ""


def obtener_metadatos_imagen():
    try:
        img_id = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE], capture_output=True, text=True).stdout.strip()
    except Exception:
        img_id = "desconocido"
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = "desconocido"
    return {"image": IMAGE, "image_id": img_id, "commit": commit}


def ejecutar(command, *, env=None, input=None):
    result = subprocess.run(command, cwd=ROOT, env=env, input=input, text=True, encoding="utf-8", capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Fallo {command[0]}: {result.stderr}")
    return result.stdout


def registrar(nombre, command, *, env=None):
    nombre += SUFIJO
    RESULTS.mkdir(parents=True, exist_ok=True)
    log = RESULTS / f"{nombre}.log"
    with log.open("x", encoding="utf-8") as stream:
        start = time.monotonic()
        process = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    entry = {"check": nombre, "exit_code": process.returncode, "seconds": round(time.monotonic() - start, 2), "log": log.relative_to(ROOT).as_posix()}
    print(json.dumps(entry), flush=True)
    return entry


def contenedor(*, env_file=None, network="none", image=IMAGE):
    base = ["docker", "run", "--rm", "--network", network,
            "--mount", f"type=bind,source={ROOT},target=/repo,readonly",
            "--mount", f"type=bind,source={RESULTS},target=/results",
            "-w", "/repo/apps/backend", "-e", "PYTHONPATH=/repo/apps/backend"]
    if env_file:
        base += ["--env-file", str(env_file)]
    else:
        base += ["-e", "DATABASE_URL=postgresql+psycopg://test:test@invalid/predicitas_fase3_test", "-e", "SECRET_KEY=fase3-unitarias-sin-base-de-datos-0123456789"]
    return [*base, image]


def preparar_bd():
    target = HERE / "laboratorio.json"
    if target.exists():
        raise SystemExit("No reutilizar ni sobrescribir laboratorio")
    prep = json.loads((HERE / "preparacion.json").read_text(encoding="utf-8"))
    private = Path(prep["private_archive"]).parent
    runid = private.name.replace("fase3-", "predicitas-fase3-")
    volume, network, db = (runid + suffix for suffix in ("-test-pgdata", "-net", "-db"))
    existing = ejecutar(["docker", "volume", "ls", "--format", "{{.Name}}"]).splitlines()
    if volume in existing:
        raise SystemExit("Nombre de volumen ya existe; no adoptar ni borrar")
    owner, app = secrets.token_hex(32), secrets.token_hex(32)
    database = "predicitas_fase3_test"
    pg_env = private / "postgres-test.env"
    pg_env.write_text(f"POSTGRES_USER=predicitas_owner\nPOSTGRES_DB={database}\nPOSTGRES_PASSWORD={owner}\nAPP_DB_PASSWORD={app}\n", encoding="ascii")
    test_env = private / "backend-test.env"
    test_env.write_text(f"DATABASE_URL=postgresql+psycopg://predicitas_app:{app}@{db}:5432/{database}\nDATABASE_URL_MIGRACIONES=postgresql+psycopg://predicitas_owner:{owner}@{db}:5432/{database}\nSECRET_KEY={secrets.token_hex(32)}\nENVIRONMENT=fase3_test\nPYTHONDONTWRITEBYTECODE=1\n", encoding="ascii")
    ejecutar(["docker", "network", "create", "--internal", "--label", "predicitas.purpose=fase3-isolated-test", network])
    ejecutar(["docker", "volume", "create", "--label", "predicitas.purpose=fase3-isolated-test", volume])
    ejecutar(["docker", "run", "-d", "--name", db, "--network", network, "--label", "predicitas.purpose=fase3-isolated-test", "--env-file", str(pg_env),
              "--mount", f"type=volume,source={volume},target=/var/lib/postgresql/data",
              "--mount", f"type=bind,source={ROOT / 'apps/backend/db/init'},target=/docker-entrypoint-initdb.d,readonly", "postgres:16"])
    for _ in range(60):
        ready = subprocess.run(["docker", "exec", db, "pg_isready", "-U", "predicitas_owner", "-d", database], capture_output=True)
        if ready.returncode == 0:
            break
        time.sleep(1)
    else:
        raise SystemExit("BD de pruebas no lista; conservar recursos para diagnóstico")
    data = {"db": db, "network": network, "volume": volume, "database": database, "private_env": str(test_env), "source_volume_used": False, "host_ports": [], "fresh_authorized_test_volume": True}
    with target.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
    print("BD de pruebas nueva lista, sin montar originales ni publicar puertos.")


def main():
    global SUFIJO
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accion", choices=("unitarias", "preparar-bd", "integracion", "regresion", "frontend", "build", "detener"))
    parser.add_argument("--final", action="store_true", help="Guardar revalidación separada sin sobrescribir evidencia anterior")
    parser.add_argument("--sufijo", default=None, help="Sufijo personalizado para la corrida de evidencia")
    parser.add_argument("--sobrescribir", action="store_true", help="Sobrescribir archivo de evidencia existente si procede")
    args = parser.parse_args()
    action = args.accion
    if args.sufijo:
        SUFIJO = f"_{args.sufijo}"
    elif args.final:
        SUFIJO = "_final"
    else:
        SUFIJO = ""
    RESULTS.mkdir(parents=True, exist_ok=True)
    target = HERE / f"validacion_{action}{SUFIJO}.json"
    if target.exists() and not args.sobrescribir:
        raise SystemExit(f"No sobrescribir evidencia existente: {target.name}. Usa --sufijo o --sobrescribir.")
    results = []
    meta = obtener_metadatos_imagen()
    if action == "preparar-bd":
        preparar_bd()
        return
    if action == "unitarias":
        results.append(registrar("unitarias_archivos", [*contenedor(), "python", "-m", "pytest", "tests/sistema/test_archivos_fase3.py", "--no-cov", f"--junitxml=/results/unitarias_archivos{SUFIJO}.xml"]))
    elif action in ("integracion", "regresion", "detener"):
        lab = json.loads((HERE / "laboratorio.json").read_text(encoding="utf-8"))
        assert lab["db"].startswith("predicitas-fase3-") and lab["database"] == "predicitas_fase3_test"
        base = contenedor(env_file=lab["private_env"], network=lab["network"])
        if action == "integracion":
            results.append(registrar("alembic_test_upgrade", [*base, "alembic", "upgrade", "head"]))
            if results[-1]["exit_code"]:
                raise SystemExit("No continuar sin migraciones test")
            results.append(registrar("importacion_canonica", [*base, "python", "/repo/docs/migracion/fase-03/probar_importacion.py"]))
        elif action == "regresion":
            results.append(registrar("backend_completo", [*base, "python", "-m", "pytest", f"--junitxml=/results/backend_completo{SUFIJO}.xml"]))
            results.append(registrar("backend_diagnostico", [*base, "python", "-m", "pytest", "--ignore=tests/ia", f"--junitxml=/results/backend_diagnostico{SUFIJO}.xml", f"--cov-report=json:/results/backend_coverage{SUFIJO}.json"]))
        else:
            results.append(registrar("detener_test_db", ["docker", "stop", lab["db"]]))
    elif action == "frontend":
        for name in ("typecheck", "lint", "build", "test"):
            # --prefix no cambia código/configuración, fija inequívocamente la app.
            results.append(registrar(f"frontend_{name}", ["npm.cmd", "--prefix", str(ROOT / "apps/frontend"), "run", name]))
    else:
        results.append(registrar("docker_build_backend", ["docker", "build", "-t", "predicitas-fase3-backend:validacion", str(ROOT / "apps/backend")]))
    payload = {"metadata": meta, "results": results}
    with target.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)


if __name__ == "__main__":
    main()
