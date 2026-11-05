"""Renderiza sin publicar secretos y construye imágenes desde rutas nuevas."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    mode = sys.argv[1]
    assert mode in ("build", "up", "up_repetido", "down_laboratorio", "stop")
    lab = json.loads((HERE / "laboratorio.json").read_text(encoding="utf-8"))
    env = {**os.environ, "PGDATA_VOLUME_NAME": lab["volume"]}
    base = ["docker", "compose", "--project-name", "predicitas-fase2-validacion", "-f", str(ROOT / "compose.yaml"), "-f", str(HERE / "compose.validacion.yaml"), "--env-file", str(ROOT / ".env")]
    # Activar perfil solo al inspeccionar: build/up nunca habilitan seed-manual.
    rendered = subprocess.run([*base, "--profile", "seed-manual", "config", "--format", "json"], cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, check=True)
    config = json.loads(rendered.stdout)
    assert config["volumes"]["pgdata"]["name"] == lab["volume"]
    assert config["volumes"]["pgdata"]["external"] is True
    assert lab["volume"].startswith("predicitas-fase2-")
    assert config["services"]["seed"]["profiles"] == ["seed-manual"]
    assert "DATABASE_URL_MIGRACIONES" not in config["services"]["backend"]["environment"]
    assert all(s["container_name"].startswith("predicitas-fase2-validacion-") for s in config["services"].values())
    output = HERE / f"compose_{mode}.json"
    if output.exists():
        raise SystemExit("No sobrescribir evidencia")
    if mode in ("up", "up_repetido"):
        # Un único proceso PostgreSQL sobre el clon. No se detienen recursos ajenos.
        subprocess.run(["docker", "stop", lab["db"]], capture_output=True, check=True)
        args = ["up", "-d", "--no-build", "--wait", "--wait-timeout", "120", "db", "migraciones", "backend", "frontend"]
    elif mode == "down_laboratorio":
        args = ["down"]  # Solo este proyecto de laboratorio, SIN -v; clon externo preservado.
    elif mode == "build":
        args = ["build", "backend", "frontend"]
    else:
        args = ["stop"]
    with (HERE / f"compose_{mode}.log").open("x", encoding="utf-8") as log:
        result = subprocess.run([*base, *args], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    data = {"mode": mode, "exit_code": result.returncode, "external_volume": lab["volume"], "production_volume_used": False, "seed_excluded": True, "backend_without_owner_dsn": True, "log": f"compose_{mode}.log"}
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
