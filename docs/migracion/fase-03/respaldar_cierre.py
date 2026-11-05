"""Respaldo privado de resultado y evidencia de fase3, sin publicar secretos."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    target = HERE / "respaldo_cierre.json"
    if target.exists():
        raise SystemExit("No sobrescribir respaldo de cierre")
    prep = json.loads((HERE / "preparacion.json").read_text(encoding="utf-8"))
    archive_path = Path(prep["private_archive"]).parent / "resultado_fase3_privado.zip"
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "coverage", "dist", "backups", "runtime"}
    count = 0
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED) as archive:
        for folder, directories, files in os.walk(ROOT):
            directories[:] = [name for name in directories if name not in skip]
            for name in sorted(files):
                if name.endswith((".pyc", ".tsbuildinfo")):
                    continue
                path = Path(folder) / name
                archive.write(path, path.relative_to(ROOT).as_posix())
                count += 1
        # Runtime normalmente no se respalda como código; preservar solo la evidencia de esta entrega.
        for path in sorted((ROOT / "runtime/test-results/fase-03").rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(ROOT).as_posix())
                count += 1
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
    data = {"date_utc": datetime.now(timezone.utc).isoformat(), "private_archive": str(archive_path), "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(), "bytes": archive_path.stat().st_size, "files": count, "zip_crc_verified": True, "raw_test_evidence_included": True, "contains_secrets_do_not_publish": True, "inherits_restricted_acl": True, "same_machine_not_external_copy": True, "empty_directories_not_stored": ["apps/backend/Skills", "apps/frontend/Skills", "data/raw", "data/processed", "artifacts/reports", "runtime/tmp"], "note": "Manifiesto fuera del ZIP. No incluye instalaciones ni runtime ajeno a evidencia de fase3; recrear directorios vacíos al recuperar."}
    with target.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
    print(json.dumps({"files": count, "zip_crc_verified": True, "sha256": data["sha256"]}))


if __name__ == "__main__":
    main()
