"""Verifica imagen empaquetada y conexión operativa real sin escribir en BD."""
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def main():
    target = HERE / "contenedor_runtime.json"
    if target.exists():
        raise SystemExit("No sobrescribir evidencia")
    code = '''
import hashlib, importlib.metadata, json, os
from pathlib import Path
from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import engine
s = get_settings()
assert "@db:5432/predicitas" in s.database_url
with engine.connect() as conn:
    conn.execute(text("SET TRANSACTION READ ONLY"))
    role = conn.execute(text("SELECT current_user")).scalar_one()
    count = conn.execute(text("SELECT count(*) FROM citas")).scalar_one()
pins = []
for line in Path("requirements.txt").read_text(encoding="utf-8-sig").splitlines():
    if "==" in line:
        package, wanted = line.strip().split("==")
        pins.append({"package":package, "wanted":wanted, "installed":importlib.metadata.version(package)})
print(json.dumps({"uid":os.getuid(), "database_role":role, "citas":count, "owner_dsn_absent":s.database_url_migraciones is None, "model_sha256":hashlib.sha256(Path("app/modules/ia/artifacts/modelo_predicitas_v1.joblib").read_bytes()).hexdigest(), "pins":pins, "all_pins_match":all(p["wanted"] == p["installed"] for p in pins)}))
'''
    result = subprocess.run(["docker", "exec", "predicitas-fase2-validacion-backend", "python", "-c", code], text=True, encoding="utf-8", capture_output=True, check=True)
    data = json.loads(result.stdout)
    expected = json.loads((HERE / "smoke_antes.json").read_text(encoding="utf-8"))
    data["packaged_model_matches_before"] = data["model_sha256"] == expected["model_sha256"]
    data["node_container_version"] = subprocess.check_output(["docker", "exec", "predicitas-fase2-validacion-frontend", "node", "--version"], text=True).strip()
    with (HERE / "frontend_node22_build.log").open("x", encoding="utf-8") as log:
        build = subprocess.run(["docker", "run", "--rm", "--network", "none", "predicitas-fase2-frontend:validacion", "npm", "run", "build"], stdout=log, stderr=subprocess.STDOUT)
    data["node22_build_exit_code"] = build.returncode
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert data["uid"] == 1000 and data["database_role"] == "predicitas_app"
    assert data["owner_dsn_absent"] and data["citas"] == 1122 and data["all_pins_match"] and data["packaged_model_matches_before"]
    assert data["node22_build_exit_code"] == 0
    print("Backend empaquetado: no-root, rol app, 1.122 citas, sin DSN owner; modelo y requirements fijados coinciden.")


if __name__ == "__main__":
    main()
