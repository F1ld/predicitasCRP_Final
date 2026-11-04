"""Instala requirements sin paquetes del sistema, dentro de un contenedor desechable.

No importa la aplicacion, no conecta a BD y no actualiza requirements.
Los logs detallados y el reporte pip se guardan en el directorio privado.
"""
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    output = Path("/evidence/instalacion_limpia_backend.json")
    if output.exists():
        raise SystemExit("Ya existe evidencia; no se sobrescribe.")
    python = Path("/tmp/fase0-verificacion/bin/python")
    if python.parent.parent.exists():
        raise SystemExit("El entorno debe ser nuevo.")
    started = time.monotonic()
    subprocess.run([sys.executable, "-m", "venv", str(python.parent.parent)], check=True)
    command = [str(python), "-m", "pip", "install", "--timeout", "120", "--retries", "2", "--report", "/private/instalacion_limpia_pip_report.json", "-r", "/workspace/requirements.txt"]
    with Path("/private/instalacion_limpia_backend.log").open("x", encoding="utf-8") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, text=True)
    summary = {"isolated_venv": True, "system_site_packages": False, "python": sys.version.split()[0], "install_exit_code": result.returncode, "seconds": round(time.monotonic() - started, 2), "source_read_only": True, "database_accessed": False, "requirements_modified": False}
    if result.returncode == 0:
        check = subprocess.run([str(python), "-m", "pip", "check"], capture_output=True, text=True)
        summary["pip_check_exit_code"] = check.returncode
        summary["pip_check_output"] = check.stdout.strip()
        code = "import importlib.metadata as m,json; print(json.dumps({d.metadata['Name']:d.version for d in m.distributions()}))"
        summary["installed_packages"] = json.loads(subprocess.check_output([str(python), "-c", code], text=True))
    with output.open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(result.returncode or summary.get("pip_check_exit_code", 0))


if __name__ == "__main__":
    main()
