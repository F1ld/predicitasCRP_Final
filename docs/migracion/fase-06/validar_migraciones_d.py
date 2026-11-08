"""Orquesta la migración D: paridad, regresiones y QA en laboratorio propio."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REFERENCE_IMAGE = "sha256:421227ed06dabde3f18c67692a97aa573283731aa51204ecd74a80b795871bd8"


def run(command, log, *, required=True):
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    with log.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(result.stdout + result.stderr)
    if required and result.returncode:
        raise RuntimeError(f"Validación falló ({result.returncode}); revisar {log.name}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ia-image", required=True)
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,40}", args.run_id) or not re.fullmatch(r"sha256:[a-f0-9]{64}", args.ia_image):
        raise ValueError("Identidades inválidas")
    raw = ROOT / "runtime/test-results/fase-06" / args.run_id
    raw.mkdir(parents=True, exist_ok=False)
    from validar_legacy_d import verify_previous
    assert verify_previous() == 18
    protected = [ROOT / p for p in (".env", "apps/backend/.env", "apps/frontend/.env",
        "apps/backend/app/modules/ia/artifacts/modelo_predicitas_v1.joblib",
        "artifacts/models/legacy-import/modelo_predicitas_v1.joblib")]
    protected_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.is_file()}
    sources = [ROOT / p for p in ("apps/backend/scripts/exportar_csv.py", "apps/backend/scripts/csv_preparado.py",
        "apps/backend/tests/datos_preparados.py", "apps/backend/tests/citas/test_citas.py",
        "apps/backend/tests/citas/test_m02_contrato.py", "apps/backend/tests/test_ia_predictor.py",
        "apps/backend/tests/test_migracion_d.py", "apps/backend/tests/sistema/test_archivos_fase3.py",
        "apps/frontend/tests/validar_diseno.py", "apps/ia/datasets/exportar_csv.py", "apps/ia/datasets/qa_bundle.py",
        "apps/ia/tests/test_exportar_d.py", "apps/ia/tests/test_qa_bundle_d.py")]
    sources.extend(HERE / p for p in ("validar_migraciones_d.py", "probar_paridad_fixtures_d.py",
        "probar_qa_migrado_d.py", "legacy-d.policy.json", "inventariar_legacy_d.py", "test_inventario_d.py"))
    for folder in ("apps/backend/tests/fixtures/generados-v1", "apps/frontend/tests/fixtures/generados-v1"):
        sources.extend(p for p in (ROOT / folder).iterdir() if p.is_file())
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (raw / "fuentes.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    shared = ["--mount", f"type=bind,source={HERE},target=/checks,readonly", "--mount", f"type=bind,source={raw},target=/results"]
    isolated = ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=512m",
                "--cpus", "2", "--memory", "1g", "-e", "PYTHONPATH=/app"]
    # El bundle preparado es solo entrada; cada proceso escribe su resultado propio.
    for mode, image in (("legacy", REFERENCE_IMAGE), ("canonical", args.ia_image)):
        run([*isolated, *shared, "--mount", f"type=bind,source={args.bundle.resolve()},target=/results/bundle,readonly",
             image, "python", "-B", "/checks/probar_paridad_fixtures_d.py", mode], raw / ("paridad-" + mode + ".log"))
    assert (raw / "paridad-legacy.json").read_bytes() == (raw / "paridad-canonical.json").read_bytes()
    run([*isolated, *shared, "--mount", f"type=bind,source={ROOT / 'artifacts/models/legacy-import'},target=/models,readonly",
         args.ia_image, "python", "-B", "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider",
         "--junitxml=/results/ia.xml", "--cov=app", "--cov=training", "--cov=datasets", "--cov=management",
         "--cov-report=json:/results/ia-coverage.json"], raw / "ia.log")
    lab_id = args.run_id + "-lab"
    # Runner C existente conserva esquema/rol/protecciones y detiene su laboratorio.
    run([sys.executable, "-B", str(HERE / "validar_seed_c.py"), "--run-id", lab_id,
         "--ia-image", args.ia_image], raw / "laboratorio.log")
    lab_raw = raw.parent / lab_id
    meta = json.loads((lab_raw / "laboratorio.json").read_text())
    private = Path(os.environ["LOCALAPPDATA"]) / "Temp/opencode" / ("seed-" + lab_id)
    expected = dict(line.split("=", 1) for line in (private / "postgres.env").read_text().splitlines() if "=" in line)
    info = json.loads(subprocess.check_output(["docker", "inspect", meta["db"]], text=True))[0]
    actual = dict(line.split("=", 1) for line in info["Config"]["Env"] if "=" in line)
    assert (info["Config"]["Labels"].get("predicitas.purpose") == "f6c-test"
            and actual.get("POSTGRES_PASSWORD") == expected["POSTGRES_PASSWORD"]
            and meta["network"] in info["NetworkSettings"]["Networks"] and info["State"]["Status"] == "exited")
    started = False
    try:
        subprocess.run(["docker", "start", meta["db"]], check=True, capture_output=True)
        started = True
        # pg_isready se espera dentro de un proceso de prueba con reintentos acotados.
        import time
        for _ in range(60):
            ready = subprocess.run(["docker", "exec", meta["db"], "pg_isready", "-h", "127.0.0.1",
                "-U", "predicitas_owner", "-d", meta["database"]], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Laboratorio propio no listo")
        base = ["docker", "run", "--rm", "--network", meta["network"], "--read-only", "--tmpfs", "/tmp:rw,size=256m",
                "--cpus", "2", "--memory", "1g", "-e", "PYTHONPATH=/app", "--env-file", str(private / "runtime.env"), *shared]
        run([*base, "--mount", f"type=bind,source={ROOT / 'apps/frontend/tests'},target=/qa/apps/frontend/tests,readonly",
             meta["backend_image"], "python", "-B", "/checks/probar_qa_migrado_d.py"], raw / "qa.log")
        # Restaurar la profundidad del monorepo SOLO en tmpfs desde el código
        # empaquetado, para no excluir las pruebas del exportador por geometría.
        code = "import shutil,subprocess,os; from pathlib import Path; shutil.copytree('/app','/tmp/repo/apps/backend'); q=Path('/tmp/repo/apps/frontend/tests'); q.mkdir(parents=True); [shutil.copyfile('/qa/'+n,q/n) for n in ('validar_diseno.py','rutas_validacion.py')]; shutil.copytree('/qa/fixtures/generados-v1',q/'fixtures/generados-v1'); env=dict(os.environ,PYTHONPATH='/tmp/repo/apps/backend'); raise SystemExit(subprocess.call(['python','-B','-m','pytest','tests/sistema/test_archivos_fase3.py','-k','not invariantes','--no-cov','-q','--junitxml=/results/archivos.xml'],cwd='/tmp/repo/apps/backend',env=env))"
        run([*base, "--mount", f"type=bind,source={ROOT / 'apps/frontend/tests'},target=/qa,readonly",
             meta["backend_image"], "python", "-B", "-c", code], raw / "archivos.log")
    finally:
        if started:
            run(["docker", "stop", meta["db"]], raw / "parada.log")
    gate = run([sys.executable, "-B", str(HERE / "inventariar_legacy_d.py"), "--exigir-cierre-programado"], raw / "inventario.json")
    inventory = json.loads(gate.stdout)
    assert inventory["scheduled_closure_ready"] and len(inventory["references"]) == 2 and not inventory["retirement_allowed"]
    assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    assert verify_previous() == 18
    assert protected_hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.is_file()}
    result = {"run_id": args.run_id, "ia_image": args.ia_image, "backend_image": meta["backend_image"],
        "lab_id": lab_id, "lab_stopped": True, "nine_scenarios_equal_to_legacy": True,
        "scheduled_closure_ready": True, "retirement_allowed": False, "sources_unchanged": True,
        "previous_source_checks": 18, "protected_unchanged": True,
        "scope": "Migraciones D; E/fase 7 no iniciados. Sin navegador visual ni despliegue."}
    (raw / "resumen.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Migraciones D: paridad de nueve fixtures, regresiones IA/backend, QA ASGI y cierre programado aprobados.")


if __name__ == "__main__":
    main()
