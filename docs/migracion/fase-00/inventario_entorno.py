"""Inventario publico de configuracion sin leer valores secretos a la salida."""
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
from urllib.parse import urlsplit


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    return {"exit_code": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def main():
    root = Path.cwd()
    result = {"host_python": platform.python_version(), "git": {}, "docker": {}, "env_files": [], "skills": [], "hashes": [], "legacy_references": []}
    for name, args in {
        "head": ["git", "rev-parse", "HEAD"], "worktrees": ["git", "worktree", "list", "--porcelain"],
        "version": ["git", "--version"],
    }.items():
        result["git"][name] = command(args)
    for name, args in {
        "version": ["docker", "version", "--format", "{{json .}}"],
        "compose_version": ["docker", "compose", "version"],
        "compose_projects": ["docker", "compose", "ls", "--format", "json"],
        "images": ["docker", "image", "ls", "--format", "{{json .}}"],
    }.items():
        result["docker"][name] = command(args)
    # Solo estructura y claves, no contenido de .env ni passwords de URLs.
    for relative in (".env", "backend-predicitas/.env", "frontend-predicitas/.env"):
        path = root / relative
        values = {}
        if path.is_file():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip("\"'")
        urls = {}
        for key in ("DATABASE_URL", "DATABASE_URL_MIGRACIONES", "IA_URL", "VITE_API_URL"):
            if key in values:
                url = urlsplit(values[key])
                urls[key] = {"scheme": url.scheme, "host": url.hostname, "port": url.port, "database_or_path": url.path, "username": url.username, "password": "[REDACTED]" if url.password else None}
        result["env_files"].append({"path": relative, "exists": path.is_file(), "keys_only": sorted(values), "redacted_connections": urls})
    for relative in ("backend-predicitas/Skills", "frontend-predicitas/Skills"):
        path = root / relative
        result["skills"].append({"path": relative, "exists": path.is_dir(), "items": len(list(path.iterdir())) if path.is_dir() else None})
    for relative in ("backend-predicitas/requirements.txt", "frontend-predicitas/package-lock.json", "frontend-predicitas/package.json", "docker-compose.yml", "backend-predicitas/docker-compose.yml", "backend-predicitas/app/modules/ia/artifacts/modelo_predicitas_v1.joblib", "citas_para_importar_variado.csv", "backend-predicitas/data/citas_para_importar_variado.csv"):
        path = root / relative
        result["hashes"].append({"path": relative, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    for app in ("backend-predicitas", "frontend-predicitas"):
        for path in (root / app).rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".ts", ".tsx", ".jsx", ".js", ".ini"}:
                continue
            for index, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
                kinds = []
                if re.search(r"[A-Z]:[\\/](?:Users|home)", line, re.I): kinds.append("absolute_host_path")
                if "contratos/" in line or "contratos\\" in line: kinds.append("legacy_contract_reference")
                if ' / "backend"' in line or ' / "frontend"' in line: kinds.append("legacy_app_directory")
                if kinds: result["legacy_references"].append({"path": path.relative_to(root).as_posix(), "line": index, "kinds": kinds})
    output = Path(__file__).with_name("inventario_entorno.json")
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print("Inventario guardado sin valores secretos.")


if __name__ == "__main__":
    main()
