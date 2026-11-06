"""Construye y prueba el paquete de D; no monta fuentes del backend en /app."""
import argparse
import json
import os
from pathlib import Path
import re

from validar import ROOT, HERE, IMAGE, accion, escribir, fuentes, leer, protegidos, sha, salida, verificar


def runtime(meta, raw, image):
    return ["docker", "run", "--rm", "--network", meta["network"],
            "--env-file", str(Path(meta["private_env"]).with_name("runtime.env")),
            "--mount", f"type=bind,source={HERE},target=/checks,readonly",
            "--mount", f"type=bind,source={raw},target=/results", "-w", "/app",
            "-e", "PYTHONPATH=/app", "-e", "PYTHONDONTWRITEBYTECODE=1", image]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,40}", args.run_id):
        raise ValueError("run-id inválido")
    raw = ROOT / "runtime/test-results/fase-04" / args.run_id
    meta = leer(raw / "laboratorio.json")
    assert meta["scope"] == "D" and verificar(meta) == "running"
    assert salida(["git", "rev-parse", "HEAD"], cwd=ROOT) == meta["commit_tested"]
    assert not salida(["git", "status", "--porcelain"], cwd=ROOT)
    target = raw / "imagen_d.json"
    assert not target.exists()
    tag = "predicitas-fase4-backend:" + args.run_id
    if accion(raw, "docker_build_d", ["docker", "build", "-t", tag, str(ROOT / "apps/backend")]):
        raise RuntimeError("Build D fallido; conservar diagnóstico")
    image = salida(["docker", "image", "inspect", "--format", "{{.Id}}", tag])
    private_env = dict(line.split("=", 1) for line in Path(meta["private_env"]).read_text().splitlines() if "=" in line)
    env_path = Path(meta["private_env"]).with_name("runtime.env")
    with env_path.open("x", encoding="utf-8", newline="\n") as stream:
        for key in ("DATABASE_URL", "SECRET_KEY", "ENVIRONMENT"):
            stream.write(f"{key}={private_env[key]}\n")
    golden = leer(ROOT / "docs/migracion/fase-00/ia_baseline.json")["predictions"]
    # Captura app instalada, sin montaje /repo ni credenciales owner.
    code = '''import hashlib,json,os,sys,platform
from pathlib import Path
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable,CreateIndex
from app.main import app
from app.core.database import Base
from app.modules.ia.predictor import predecir_cita_dict
features=json.load(sys.stdin)
assert not Path('/repo').exists() and not Path('/app/data').exists() and not Path('/app/.env').exists()
assert not os.environ.get('DATABASE_URL_MIGRACIONES')
dialect=postgresql.dialect(); ddl=[]
for table in Base.metadata.sorted_tables:
 ddl.append(str(CreateTable(table).compile(dialect=dialect)))
 ddl.extend(sorted(str(CreateIndex(index).compile(dialect=dialect)) for index in table.indexes))
p=Path('/app/app/modules/ia/artifacts/modelo_predicitas_v1.joblib')
print(json.dumps({'uid':os.getuid(),'python':platform.python_version(),'source_mount_absent':True,'owner_env_absent':True,'legacy_data_and_env_absent':True,'model_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'openapi':app.openapi(),'ddl':ddl,'predictions':[predecir_cita_dict(x['features']) for x in features]},default=str))
'''
    command = runtime(meta, raw, image)
    command.insert(3, "-i")
    package = json.loads(salida([*command, "python", "-c", code], input=json.dumps(golden)))
    baseline = leer(raw / "baseline_captura.json")
    parity = {key: package[key] == baseline[key] for key in ("openapi", "ddl", "predictions", "model_sha256")}
    assert all(parity.values()) and package["uid"] == 1000
    freeze = salida(["docker", "run", "--rm", "--network", "none", image, "python", "-m", "pip", "freeze", "--all"])
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+", line) for line in freeze.splitlines())
    assert fuentes(ROOT) == meta["initial_sources"] and protegidos() == meta["protected_files"]
    escribir(target, {"run_id": args.run_id, "commit_tested": meta["commit_tested"], "image_tag": tag,
        "image_id": image, "baseline_dependencies_image": IMAGE, "python": package["python"],
        "pip_freeze": freeze.splitlines(), "parity": parity, "uid": package["uid"],
        "source_mount_absent": True, "owner_env_absent": True, "legacy_data_and_env_absent": True,
        "model_sha256": package["model_sha256"]})
    print("Paquete D no-root, sin fuentes montadas ni env owner, paridad exacta: PASÓ")


if __name__ == "__main__":
    main()
