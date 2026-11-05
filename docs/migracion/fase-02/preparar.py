"""Respaldo privado e inventario previo; no modifica aplicaciones ni BD."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "preparacion.json"
    if output.exists():
        raise SystemExit("La evidencia ya existe; no sobrescribir.")
    previous = json.loads((ROOT / "docs/migracion/fase-00/respaldo_duradero.json").read_text(encoding="utf-8-sig"))
    checked = []
    for item in previous["Copies"]:
        path = Path(previous["Directory"]) / item["File"]
        valid = path.exists() and sha(path).upper() == item["Sha256"]
        checked.append({"file": item["File"], "verified": valid})
        if not valid:
            raise SystemExit(f"Respaldo previo no verificable: {item['File']}")
    private = Path(os.environ["LOCALAPPDATA"]) / "PrediCitasBackups" / ("fase2-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    private.mkdir(parents=True, exist_ok=False)
    principal = f"{os.environ['USERDOMAIN']}\\{os.environ['USERNAME']}:(OI)(CI)F"
    subprocess.run(["icacls", str(private), "/inheritance:r", "/grant:r", principal], check=True, capture_output=True)
    ignored = {"node_modules", "dist", ".venv", "venv", "__pycache__", ".pytest_cache", "coverage"}
    files = []
    archive = private / "antes_mudanza_privado.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for folder in ("backend-predicitas", "frontend-predicitas"):
            for path in sorted((ROOT / folder).rglob("*")):
                if not path.is_file() or ignored.intersection(path.relative_to(ROOT / folder).parts):
                    continue
                rel = path.relative_to(ROOT).as_posix()
                z.write(path, rel)
                files.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha(path)})
        for name in (".env", ".env.example", "docker-compose.yml", ".gitignore", ".gitattributes", "PLAN_REESTRUCTURACION_POR_FASES.md"):
            z.write(ROOT / name, name)
    data = {"date": datetime.now(timezone.utc).isoformat(), "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "previous_backups": checked, "private_archive": str(archive), "archive_sha256": sha(archive), "files": files, "note": "Backup contiene secretos, ACL restringida; no publicar. Excluye instalaciones y outputs regenerables."}
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"files": len(files), "previous_backups_verified": len(checked), "private_archive": str(archive)}))


if __name__ == "__main__":
    main()
