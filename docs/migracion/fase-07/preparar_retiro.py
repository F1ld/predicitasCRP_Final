"""Prepara un contexto Docker de retiro en una carpeta nueva de runtime."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "apps/backend"


def replace(path, old, new, count=1):
    source = path.read_text(encoding="utf-8")
    if source.count(old) != count:
        raise RuntimeError(f"El candidato requiere revisar {path.name}: patrón inesperado")
    path.write_text(source.replace(old, new), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destino", type=Path)
    args = parser.parse_args()
    target = args.destino.resolve()
    if not target.is_relative_to((ROOT / "runtime/fase-07").resolve()):
        parser.error("El destino debe estar dentro de runtime/fase-07")
    target.mkdir(parents=True, exist_ok=False)
    for directory in ("app", "migrations", "scripts"):
        shutil.copytree(BACKEND / directory, target / directory,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.joblib", ".env*"))
    for file in ("Dockerfile", ".dockerignore", "requirements.txt", "alembic.ini"):
        shutil.copyfile(BACKEND / file, target / file)
    tests = target / "tests"
    tests.mkdir()
    for file in ("__init__.py", "conftest.py", "test_ia_endpoints.py"):
        shutil.copyfile(BACKEND / "tests" / file, tests / file)

    for file in ("ia/predictor.py", "ia/motor_integrado.py", "citas/synthetic.py"):
        (target / "app/modules" / file).unlink()
    replace(target / "app/modules/citas/public.py",
            "from app.modules.citas.synthetic import generar_citas  # contrato temporal hasta extraer datasets IA\n", "")
    replace(target / "app/core/config.py", 'Literal["integrado", "http"] = "integrado"', 'Literal["http"] = "http"')
    dependencies = target / "app/modules/ia/dependencias.py"
    replace(dependencies, "from app.modules.ia.motor_integrado import MotorIntegrado\n", "")
    replace(dependencies, '    if settings.ia_motor == "integrado":\n        return MotorIntegrado()\n', "")
    replace(dependencies, '    # Compatibilidad TestClient/consumidores sin lifespan, solo modo integrado.\n'
            '    if get_settings().ia_motor == "integrado":\n        return MotorIntegrado()\n', "")
    service = target / "app/modules/ia/service.py"
    replace(service, "from app.modules.ia.motor_integrado import MotorIntegrado\n", "")
    replace(service, "motor: MotorPredictivo | None = None", "motor: MotorPredictivo", count=4)
    replace(service, "    motor = motor or MotorIntegrado()\n", "", count=2)
    replace(service, "(motor or MotorIntegrado())", "motor", count=2)

    ml = {"cloudpickle", "joblib", "lightgbm", "narwhals", "numpy", "scikit-learn", "scipy", "threadpoolctl"}
    requirements = target / "requirements.txt"
    requirements.write_text("".join(line for line in requirements.read_text(encoding="utf-8").splitlines(keepends=True)
                                    if line.partition("==")[0] not in ml), encoding="utf-8")
    replace(target / "Dockerfile", "    libgomp1 \\\n", "")


if __name__ == "__main__":
    main()
