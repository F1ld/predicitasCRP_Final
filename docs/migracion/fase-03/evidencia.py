"""Identidad y destinos exclusivos de una ejecución; sin efectos al importar."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
IMAGE = "predicitas-fase3-backend:validacion"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def leer(path):
    return json.loads(path.read_text(encoding="utf-8"))


def escribir(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def destinos(run_id):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", run_id):
        raise ValueError("run-id: 3 a 64 caracteres a-z, 0-9, _ o -; sin rutas")
    return ROOT / "runtime/test-results/fase-03" / run_id, HERE / "evidencia" / run_id


def salida(command):
    return subprocess.check_output(command, cwd=ROOT, text=True, encoding="utf-8").strip()


def codigo_actual():
    if salida(["git", "status", "--porcelain", "--untracked-files=normal"]):
        raise ValueError("Registrar los cambios antes de validar: se exige árbol Git limpio")
    return salida(["git", "rev-parse", "HEAD"])


def fuentes():
    # Blobs canónicos de Git: un checkout CRLF/LF no debe producir falsos positivos.
    entries = salida(["git", "ls-files", "--stage", ".gitattributes", "apps", "data/samples", "data/manifests", "docs/migracion/fase-03/*.py"]).splitlines()
    return [{"path": entry.split("\t", 1)[1], "git_blob": entry.split("\t", 1)[0].split()[1]} for entry in entries]


def cargar_run(run_id, *, comprobar_codigo=True):
    raw, public = destinos(run_id)
    meta = leer(raw / "ejecucion.json")
    if meta["run_id"] != run_id:
        raise ValueError("Identidad de ejecución incorrecta")
    if comprobar_codigo and codigo_actual() != meta["commit_tested"]:
        raise ValueError("El commit actual no coincide con el de la ejecución")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", meta["image_id"]):
        raise ValueError("Image ID inválido")
    return raw, public, meta


def verificar_laboratorio():
    """Solo el laboratorio registrado; no lee ni publica variables del contenedor."""
    lab = leer(HERE / "laboratorio.json")
    if not lab["db"].startswith("predicitas-fase3-") or lab["database"] != "predicitas_fase3_test":
        raise ValueError("Laboratorio no autorizado")
    info = json.loads(salida(["docker", "inspect", lab["db"]]))[0]
    volumes = [m for m in info["Mounts"] if m["Type"] == "volume"]
    if len(volumes) != 1 or volumes[0]["Name"] != lab["volume"] or volumes[0]["Destination"] != "/var/lib/postgresql/data":
        raise ValueError("Montajes inesperados en laboratorio")
    if info["HostConfig"].get("PortBindings") or info["HostConfig"].get("NetworkMode") == "host":
        raise ValueError("Laboratorio debe permanecer sin puertos host")
    if set(info["NetworkSettings"]["Networks"]) != {lab["network"]}:
        raise ValueError("Red inesperada en laboratorio")
    if info["Config"]["Labels"].get("predicitas.purpose") != "fase3-isolated-test":
        raise ValueError("Etiqueta de aislamiento ausente")
    network = json.loads(salida(["docker", "network", "inspect", lab["network"]]))[0]
    if not network["Internal"]:
        raise ValueError("La red de laboratorio debe ser interna")
    # Revisar el destino real del env privado, sin imprimir contraseñas ni URL.
    from urllib.parse import urlsplit
    env = dict(line.split("=", 1) for line in Path(lab["private_env"]).read_text().splitlines() if "=" in line and not line.startswith("#"))
    for key in ("DATABASE_URL", "DATABASE_URL_MIGRACIONES"):
        url = urlsplit(env[key])
        if url.hostname != lab["db"] or url.path != "/" + lab["database"]:
            raise ValueError("Destino de BD privado no corresponde al laboratorio")
    return lab, info["State"]["Status"]


def contenedor(raw, image_id, lab=None):
    command = ["docker", "run", "--rm", "--network", lab["network"] if lab else "none",
               "--mount", f"type=bind,source={ROOT},target=/repo,readonly",
               "--mount", f"type=bind,source={raw},target=/results",
               "-w", "/repo/apps/backend", "-e", "PYTHONPATH=/repo/apps/backend",
               "-e", "PYTHONDONTWRITEBYTECODE=1"]
    if lab:
        command += ["--env-file", lab["private_env"]]
    else:
        command += ["-e", "DATABASE_URL=postgresql+psycopg://test:test@invalid/predicitas_fase3_test",
                    "-e", "SECRET_KEY=fase3-unitarias-sin-base-de-datos-0123456789"]
    return [*command, image_id]
