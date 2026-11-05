"""Verifica CLI empaquetada no-root, no sobrescritura y exclusiones Docker."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from evidencia import cargar_run, escribir

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    raw, _, meta = cargar_run(args.run_id)
    target = raw / "imagen_y_mounts.json"
    if target.exists():
        raise SystemExit("No sobrescribir evidencia")
    output_dir = ROOT / "runtime/exports/fase-03" / args.run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    output = output_dir / "demo-ref-2026-11-05-seed-7.csv"
    if output.exists():
        raise SystemExit("Destino de prueba ya existe")
    image = meta["image_id"]
    cmd = ["docker", "run", "--rm", "--network", "none", "--mount", f"type=bind,source={output_dir},target=/exports", image, "python", "-m", "scripts.exportar_csv", "--salida", "/exports/demo-ref-2026-11-05-seed-7.csv", "--fecha-referencia", "2026-11-05", "--semilla", "7"]
    first = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert first.returncode == 0, first.stderr
    before = hashlib.sha256(output.read_bytes()).hexdigest()
    second = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert second.returncode == 2
    assert hashlib.sha256(output.read_bytes()).hexdigest() == before
    code = '''import hashlib,json,os
from pathlib import Path
assert not Path('/app/data').exists()
assert not Path('/app/artifacts').exists()
assert not Path('/app/.env').exists()
p=Path('/app/app/modules/ia/artifacts/modelo_predicitas_v1.joblib')
print(json.dumps({'uid':os.getuid(),'legacy_samples_excluded':True,'root_artifacts_excluded':True,'private_env_excluded':True,'active_model_packaged':p.is_file(),'active_model_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))'''
    package = subprocess.run(["docker", "run", "--rm", "--network", "none", image, "python", "-c", code], capture_output=True, text=True, encoding="utf-8", check=True)
    packaged = json.loads(package.stdout)
    assert packaged["uid"] == 1000 and packaged["active_model_packaged"]
    source = ROOT / "apps/backend/app/modules/ia/artifacts/modelo_predicitas_v1.joblib"
    assert packaged["active_model_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    data = {"image": image, "first_export_exit_code": first.returncode, "second_export_exit_code": second.returncode, "existing_export_unchanged": True, "output_sha256": before, "export_requires_no_database_credentials": True, "network": "none", "only_writable_host_mount": output_dir.relative_to(ROOT).as_posix(), "packaging": packaged}
    data.update({"run_id": args.run_id, "commit_tested": meta["commit_tested"], "image_id": image})
    escribir(target, data)
    print("Imagen: CLI no-root escribe solo destino explícito, rechaza sobrescritura, modelo activo intacto y datos/secretos excluidos.")


if __name__ == "__main__":
    main()
