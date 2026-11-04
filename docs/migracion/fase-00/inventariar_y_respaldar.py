"""Inventario y respaldos de fase 0; no modifica archivos funcionales.

Ejecutar desde la raiz, indicando un directorio privado existente FUERA del
proyecto. Los archivos privados (incluidos .env) nunca se escriben en docs.
Usa exclusivamente la biblioteca estandar de Python.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile


EXCLUDED = {"node_modules", ".venv", "__pycache__", ".pytest_cache", "coverage", "htmlcov", "runtime", "backups"}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    private = args.private_dir.resolve(strict=True)
    evidence = args.evidence_dir.resolve(strict=True)
    if private.is_relative_to(root):
        raise SystemExit("El respaldo privado debe estar fuera del proyecto.")
    if not evidence.is_relative_to(root):
        raise SystemExit("Las evidencias publicas deben estar dentro del proyecto.")
    archive = private / "proyecto_completo_privado.zip"
    public_archive = root / "backups" / private.name / "proyecto_sin_secretos.zip"
    public_archive.parent.mkdir(parents=True, exist_ok=True)
    files = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in EXCLUDED)
        for name in sorted(names):
            path = Path(base) / name
            relative = path.relative_to(root)
            # La evidencia de esta ejecucion se genera despues del snapshot.
            if path.is_relative_to(evidence):
                continue
            if path.is_symlink():
                raise SystemExit(f"Revisar enlace antes de respaldar: {relative}")
            files.append((path, relative.as_posix()))
    inventory = []
    private_inventory = []
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as full, zipfile.ZipFile(public_archive, "x", compression=zipfile.ZIP_DEFLATED) as public:
        for path, name in files:
            digest = sha256(path)
            row = {"path": name, "bytes": path.stat().st_size, "sha256": digest}
            private_inventory.append(row)
            full.write(path, name)
            secret = path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example")
            if not secret and ".git" not in Path(name).parts:
                public.write(path, name)
            if ".git" not in Path(name).parts:
                inventory.append({"path": name, "private": True} if secret else row)
    # Verificar cada entrada contra sus bytes, no solo CRC del contenedor ZIP.
    with zipfile.ZipFile(archive) as full:
        for row in private_inventory:
            if hashlib.sha256(full.read(row["path"])).hexdigest() != row["sha256"]:
                raise SystemExit(f"Fallo de verificacion: {row['path']}")
    with zipfile.ZipFile(public_archive) as public:
        if public.testzip() is not None:
            raise SystemExit("Fallo CRC en copia sin secretos.")
    write_json(private / "inventario_privado.json", private_inventory)
    write_json(evidence / "inventario_archivos.json", inventory)
    summary = {
        "git_snapshot": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "private_backup_directory": str(private),
        "private_archive": {"filename": archive.name, "bytes": archive.stat().st_size, "sha256": sha256(archive), "all_entries_sha256_verified": True},
        "secondary_archive": {"path": public_archive.relative_to(root).as_posix(), "bytes": public_archive.stat().st_size, "sha256": sha256(public_archive), "contains_env_or_git": False},
        "source_files": len(files),
        "excluded_regenerable_directories": sorted(EXCLUDED),
        "warning": "La copia privada incluye .env e historial Git. El directorio Temp es transitorio: trasladar a almacenamiento privado duradero antes de dar por cerrada la fase 0.",
    }
    write_json(evidence / "respaldo_archivos.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
