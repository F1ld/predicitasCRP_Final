"""Revalidación fase 3 por run-id: nunca sobrescribe ni mezcla generaciones.

El aprovisionamiento histórico no se repite. reanudar/detener solo operan el
laboratorio existente después de verificar volumen, red, puertos y destino BD.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import time

from evidencia import (ROOT, IMAGE, cargar_run, codigo_actual, contenedor,
                       destinos, escribir, fuentes, salida, verificar_laboratorio)


def registrar(raw, meta, nombre, command):
    target = raw / f"{nombre}.json"
    log = raw / f"{nombre}.log"
    if target.exists() or log.exists():
        raise FileExistsError(f"Acción ya intentada: {nombre}; usar otro run-id")
    start = time.monotonic()
    with log.open("x", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    record = {"run_id": meta["run_id"], "commit_tested": meta["commit_tested"],
              "image_id": meta.get("image_id"), "check": nombre,
              "exit_code": result.returncode, "seconds": round(time.monotonic() - start, 2),
              "log": log.relative_to(ROOT).as_posix()}
    escribir(target, record)
    print(json.dumps(record), flush=True)
    return result.returncode


def build(run_id):
    commit = codigo_actual()
    raw, public = destinos(run_id)
    if public.exists():
        raise FileExistsError("Ya existe evidencia pública de ese run-id")
    raw.mkdir(parents=True, exist_ok=False)
    meta = {"run_id": run_id, "commit_tested": commit, "image": IMAGE,
            "started_utc": datetime.now(timezone.utc).isoformat(), "source_files": fuentes()}
    if registrar(raw, meta, "build", ["docker", "build", "-t", IMAGE, str(ROOT / "apps/backend")]):
        raise SystemExit("Build fallido; conservar ejecución y usar otro run-id")
    meta["image_id"] = salida(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE])
    code = "import json,platform; print(json.dumps({'python':platform.python_version()}))"
    version = json.loads(salida(["docker", "run", "--rm", "--network", "none", meta["image_id"], "python", "-c", code]))
    freeze = salida(["docker", "run", "--rm", "--network", "none", meta["image_id"], "python", "-m", "pip", "freeze", "--all"])
    # Publicar solo pins, no URLs privadas, rutas ni credenciales de instalación.
    import re
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+", line) for line in freeze.splitlines()):
        raise ValueError("pip freeze contiene entradas que requieren revisión privada")
    meta["environment"] = {**version, "pip_freeze": freeze.splitlines(),
                           "pip_freeze_sha256": hashlib.sha256(freeze.encode()).hexdigest()}
    # No identificar como limpia una construcción durante la que cambió el código.
    if codigo_actual() != commit or fuentes() != meta["source_files"]:
        raise ValueError("El árbol cambió durante la construcción")
    escribir(raw / "ejecucion.json", meta)
    print(json.dumps({"run_id": run_id, "commit": commit, "image_id": meta["image_id"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accion", choices=("build", "unitarias", "integracion", "regresion", "reanudar", "detener"))
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.accion == "build":
        build(args.run_id)
        return
    raw, _, meta = cargar_run(args.run_id)
    if args.accion == "unitarias":
        code = registrar(raw, meta, "unitarias", [*contenedor(raw, meta["image_id"]), "python", "-m", "pytest",
                         "tests/sistema/test_archivos_fase3.py", "tests/sistema/test_evidencia_fase3.py",
                         "--no-cov", "--junitxml=/results/unitarias.xml"])
        raise SystemExit(code)
    lab, state = verificar_laboratorio()
    if args.accion == "reanudar":
        if state != "exited":
            raise SystemExit("Solo se reanuda un laboratorio previamente detenido")
        code = registrar(raw, meta, "reanudar", ["docker", "start", lab["db"]])
        if code:
            raise SystemExit(code)
        for _ in range(40):
            if subprocess.run(["docker", "exec", lab["db"], "pg_isready", "-U", "predicitas_owner", "-d", lab["database"]], capture_output=True).returncode == 0:
                return
            time.sleep(1)
        raise SystemExit("Laboratorio no listo; detenerlo conservando recursos")
    if state != "running":
        raise SystemExit("Laboratorio detenido: ejecutar reanudar con el mismo run-id")
    if args.accion == "detener":
        raise SystemExit(registrar(raw, meta, "detener", ["docker", "stop", lab["db"]]))
    base = contenedor(raw, meta["image_id"], lab)
    if args.accion == "integracion":
        if registrar(raw, meta, "alembic", [*base, "alembic", "upgrade", "head"]):
            raise SystemExit("No continuar sin migraciones de laboratorio")
        raise SystemExit(registrar(raw, meta, "integracion", [*base, "python", "/repo/docs/migracion/fase-03/probar_importacion.py"]))
    complete = registrar(raw, meta, "backend_completo", [*base, "python", "-m", "pytest", "--junitxml=/results/backend_completo.xml"])
    diagnostic = registrar(raw, meta, "backend_diagnostico", [*base, "python", "-m", "pytest", "--ignore=tests/ia",
                           "--junitxml=/results/backend_diagnostico.xml", "--cov-report=json:/results/backend_coverage.json"])
    print(json.dumps({"backend_completo": complete, "backend_diagnostico": diagnostic,
                      "note": "Los fallos previos se aceptan solo tras comparar casos en verificar_cierre.py"}))
    raise SystemExit(1 if complete or diagnostic else 0)


if __name__ == "__main__":
    main()
