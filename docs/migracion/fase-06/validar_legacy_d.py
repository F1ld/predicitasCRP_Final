"""Valida D sin borrar generadores ni conectar a BD; salidas nuevas exclusivas."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BACKEND_IMAGE = "sha256:421227ed06dabde3f18c67692a97aa573283731aa51204ecd74a80b795871bd8"
IA_IMAGE = "sha256:41ca225ddcb1a930e5232e747d6e5e2527f605f3f8154c1611e201dff03ead73"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_previous():
    count = 0
    for name in ("bloque-a-20261107-01", "bloque-b-20261107-03", "bloque-c-20261107-03"):
        summary = json.loads((HERE / "evidencia" / name / "resumen.json").read_text())
        for path, expected in summary.get("fuentes_sha256", summary.get("sources_sha256", {})).items():
            if sha(ROOT / path) != expected:
                raise ValueError("Fuente A/B/C alterada: " + path)
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,48}", args.run_id):
        raise ValueError("ID inválido")
    raw = ROOT / "runtime/test-results/fase-06" / args.run_id
    raw.mkdir(parents=True, exist_ok=False)
    previous_count = verify_previous()
    protected = [ROOT / p for p in (".env", "apps/backend/.env", "apps/frontend/.env",
        "artifacts/models/legacy-import/modelo_predicitas_v1.joblib",
        "apps/backend/app/modules/ia/artifacts/modelo_predicitas_v1.joblib")]
    before = {str(p): sha(p) for p in protected if p.is_file()}
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_inventario_d.py")
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (raw / "tests.log").write_text(log.getvalue(), encoding="utf-8")
    assert result.wasSuccessful(), "Autopruebas del gate fallaron"
    commands = [sys.executable, "-B", str(HERE / "inventariar_legacy_d.py")]
    normal = subprocess.run(commands, capture_output=True, text=True, encoding="utf-8")
    strict = subprocess.run([*commands, "--exigir-retiro"], capture_output=True, text=True, encoding="utf-8")
    scheduled = subprocess.run([*commands, "--exigir-cierre-programado"], capture_output=True, text=True, encoding="utf-8")
    assert normal.returncode == 0 and strict.returncode == 2
    inventory = json.loads(normal.stdout)
    assert inventory == json.loads(strict.stdout) and inventory["inventory_valid"] and not inventory["retirement_allowed"]
    assert inventory == json.loads(scheduled.stdout) and inventory["scheduled_retirement_approved"]
    assert scheduled.returncode == (0 if inventory["scheduled_closure_ready"] else 2)
    (raw / "inventario.json").write_text(normal.stdout, encoding="utf-8")
    # Sondas independientes: mismas filas del exportador preservado y canónico IA.
    common = "import csv,hashlib,io,json; from datetime import date; "
    finish = "print(json.dumps(dict(rows=len(list(csv.DictReader(io.StringIO(data.decode('utf-8'))))),columns=len(next(csv.reader(io.StringIO(data.decode('utf-8'))))),sha256_lf=hashlib.sha256(data.replace(bytes([13,10]),bytes([10]))).hexdigest())))"
    backend = common + "from pathlib import Path; from scripts.exportar_csv import exportar_csv; p=exportar_csv(Path('/tmp/demo.csv'),filas=3,semilla=7,fecha_referencia=date(2026,11,5)); data=p.read_bytes(); " + finish
    ia = common + "from datasets.synthetic import generar_citas; from datasets.operational_csv import construir_csv_operacional; data=construir_csv_operacional(generar_citas(historicas=0,proximas=3,semilla=7,prefijo='DEMO',desde=date(2026,11,5))); " + finish
    probes = {}
    for name, image, code in (("backend", BACKEND_IMAGE, backend), ("ia", IA_IMAGE, ia)):
        probe = subprocess.run(["docker", "run", "--rm", "--network", "none", "--read-only",
            "--tmpfs", "/tmp:rw,size=64m", "--cpus", "2", "--memory", "1g", image, "python", "-B", "-c", code],
            capture_output=True, text=True, encoding="utf-8")
        (raw / (name + ".log")).write_text(probe.stdout + probe.stderr, encoding="utf-8")
        assert probe.returncode == 0, "Sonda fallida; consultar log local"
        probes[name] = json.loads(probe.stdout)
    assert probes["backend"] == probes["ia"] and probes["backend"]["rows"] == 7 and probes["backend"]["columns"] == 13
    assert before == {str(p): sha(p) for p in protected if p.is_file()}
    assert verify_previous() == previous_count
    sources = [HERE / name for name in ("inventariar_legacy_d.py", "legacy-d.policy.json", "test_inventario_d.py", "validar_legacy_d.py")]
    summary = {"run_id": args.run_id, "block_status": "GUARDA_PROGRAMADA_VALIDADA",
        "tests": {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors)},
        "inventory_exit": normal.returncode, "retirement_exit": strict.returncode,
        "scheduled_closure_exit": scheduled.returncode,
        "scheduled_retirement_approved": inventory["scheduled_retirement_approved"],
        "scheduled_closure_ready": inventory["scheduled_closure_ready"],
        "remaining_migrations": inventory["remaining_migrations"],
        "legacy_dependencies": len(inventory["references"]), "namespaces_informational": len(inventory["namespace_references_informational"]),
        "inventory_valid": inventory["inventory_valid"], "retirement_allowed": inventory["retirement_allowed"],
        "smoke_exporter": probes, "backend_image": BACKEND_IMAGE, "ia_image": IA_IMAGE,
        "smoke_scope": "Imágenes de referencia preservadas, no regresión del exportador migrado actual",
        "previous_source_checks": previous_count, "protected_unchanged": True,
        "sources_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}}
    (raw / "resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"D: {len(inventory['remaining_migrations'])} migraciones restantes; retiro físico no autorizado. "
          "Esta comprobación no sustituye la regresión de validar_migraciones_d.py.")


if __name__ == "__main__":
    main()
