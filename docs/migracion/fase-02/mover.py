"""Mudanza mecánica con verificación byte a byte. No usar git reset/checkout."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    output = HERE / "movimientos.json"
    if output.exists():
        raise SystemExit("Ya hay una mudanza registrada")
    for check in ("frontend_antes_repetido.json", "backend_antes.json"):
        if not (HERE / check).is_file():
            raise SystemExit(f"Falta baseline completa: {check}")
    prep = json.loads((HERE / "preparacion.json").read_text(encoding="utf-8"))
    for entry in prep["files"]:
        path = ROOT / entry["path"]
        if path.suffix == ".tsbuildinfo":
            continue  # Salida regenerable de tsc, no fuente ni lockfile.
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise SystemExit(f"Archivo cambió desde respaldo: {entry['path']}")
    for source, dest in (("backend-predicitas", "apps/backend"), ("frontend-predicitas", "apps/frontend")):
        if not (ROOT / source).is_dir() or (ROOT / dest).exists():
            raise SystemExit(f"Origen/destino inesperado: {source}, {dest}")
    private = Path(prep["private_archive"]).parent
    old_node = ROOT / "frontend-predicitas/node_modules"
    if old_node.exists():
        shutil.move(str(old_node), str(private / "node_modules_previo"))
    (ROOT / "apps").mkdir(exist_ok=True)
    moves = []
    for source, dest in (("backend-predicitas", "apps/backend"), ("frontend-predicitas", "apps/frontend")):
        (ROOT / source).rename(ROOT / dest)
        skills = ROOT / dest / "Skills"
        assert skills.is_dir() and not list(skills.iterdir())
        moves.append({"source": source, "destination": dest, "skills_empty": True})
    verified = []
    for entry in prep["files"]:
        if Path(entry["path"]).suffix == ".tsbuildinfo":
            continue
        new = entry["path"].replace("backend-predicitas/", "apps/backend/", 1).replace("frontend-predicitas/", "apps/frontend/", 1)
        assert hashlib.sha256((ROOT / new).read_bytes()).hexdigest() == entry["sha256"], new
        verified.append({"source": entry["path"], "destination": new, "sha256": entry["sha256"], "identical": True})
    output.write_text(json.dumps({"moves": moves, "node_modules": "Conservado fuera del proyecto en respaldo privado; recrear con npm ci", "venvs": "No existían venvs dentro de las aplicaciones", "generated_exclusions": ["*.tsbuildinfo", "dist/", "coverage/", "caches"], "files": verified}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Movidos y verificados {len(verified)} archivos byte a byte; Skills vacías.")


if __name__ == "__main__":
    main()
