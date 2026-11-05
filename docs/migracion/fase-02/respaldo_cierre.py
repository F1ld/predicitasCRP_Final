"""Copia privada del resultado; excluye instalaciones y nunca publica secretos."""
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
        raise SystemExit("No sobrescribir evidencia")
    preparation = json.loads((HERE / "preparacion.json").read_text(encoding="utf-8"))
    destination = Path(preparation["private_archive"]).parent / "resultado_fase2_privado.zip"
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "coverage", "dist", "backups", "runtime"}
    count = 0
    with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
        for folder, directories, files in os.walk(ROOT):
            directories[:] = [name for name in directories if name not in skip]
            for name in sorted(files):
                if name.endswith((".pyc", ".tsbuildinfo")):
                    continue
                path = Path(folder) / name
                archive.write(path, path.relative_to(ROOT).as_posix())
                count += 1
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
    result = {"date": datetime.now(timezone.utc).isoformat(), "private_archive": str(destination), "files": count, "bytes": destination.stat().st_size, "sha256": digest, "zip_crc_verified": True, "contains_secrets_do_not_publish": True, "same_machine_not_external_backup": True, "empty_skills_directories": ["apps/backend/Skills/", "apps/frontend/Skills/"], "note": "ZIP no contiene carpetas vacías; recrear Skills vacías al recuperar. Hereda ACL restringida del respaldo previo. El manifiesto de este ZIP se guarda fuera de él."}
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"files": count, "zip_crc_verified": True, "sha256": digest}))


if __name__ == "__main__":
    main()
