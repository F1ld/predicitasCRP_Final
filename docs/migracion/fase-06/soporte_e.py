"""Utilidades stdlib de E: paquete limpio, hashes y fuentes verificables."""
import hashlib
from pathlib import Path
import zipfile

ROOTS = ("apps/backend", "apps/ia", "contracts")
# `data` NO se excluye globalmente: contracts/data contiene esquemas de contrato.
EXCLUDED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
                  "artifacts", "runtime", "backups", "htmlcov", "coverage"}
EXCLUDED_PREFIXES = ("apps/backend/data", "apps/ia/data")
SUFFIXES = {".py", ".txt", ".ini", ".json", ".csv", ".md", ".sh", ".sql", ".toml", ".yaml", ".yml"}


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


def safe_name(name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("Ruta de paquete no segura")
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return False
    if any(name == prefix or name.startswith(prefix + "/") for prefix in EXCLUDED_PREFIXES):
        return False
    if path.name.startswith(".env") and path.name != ".env.example":
        return False
    return path.name in {"Dockerfile", ".dockerignore", ".env.example"} or path.suffix in SUFFIXES


def source_index(root):
    root = Path(root)
    index = {}
    for scope in ROOTS:
        folder = root / scope
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError("Scope ausente o enlazado: " + scope)
        # No seguir entornos, secretos o artefactos durante la enumeración.
        import os
        for directory, dirs, files in os.walk(folder, followlinks=False):
            base = Path(directory)
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_PARTS and not (base / d).is_symlink())
            for name in sorted(files):
                path = base / name
                relative = path.relative_to(root).as_posix()
                if safe_name(relative):
                    if path.is_symlink():
                        raise ValueError("Fuente enlazada")
                    index[relative] = sha(path)
    return index


def package(root, destination, index):
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, expected in sorted(index.items()):
            if not safe_name(name):
                raise ValueError("Archivo no permitido")
            data = (Path(root) / name).read_bytes()
            if sha_bytes(data) != expected:
                raise ValueError("Fuente cambió antes del empaquetado")
            archive.writestr(name, data)


def unpack(archive_path, destination, index):
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise FileExistsError("Reconstrucción debe ser nueva")
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(index):
            raise ValueError("Índice de paquete inconsistente")
        payloads = {}
        for name in names:
            if not safe_name(name):
                raise ValueError("Entrada no permitida")
            data = archive.read(name)
            if sha_bytes(data) != index[name]:
                raise ValueError("Hash del paquete incorrecto")
            payloads[name] = data
    target.mkdir(parents=True)
    for name, data in payloads.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)


def tree_hashes(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(Path(root).rglob("*")) if p.is_file()}
