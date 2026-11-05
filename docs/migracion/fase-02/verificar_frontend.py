"""Ejecuta los mismos checks antes/después; conserva logs y no oculta fallos previos."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    stage = sys.argv[1]
    if stage not in ("antes", "antes_repetido", "despues"):
        raise SystemExit("Usar antes o despues")
    output = HERE / f"frontend_{stage}.json"
    if output.exists():
        raise SystemExit("No sobrescribir evidencia")
    cwd = ROOT / ("frontend-predicitas" if stage.startswith("antes") else "apps/frontend")
    results = []
    for script in ("typecheck", "lint", "build", "test"):
        log = HERE / f"frontend_{stage}_{script}.log"
        start = time.monotonic()
        with log.open("x", encoding="utf-8") as stream:
            result = subprocess.run(["npm.cmd", "run", script], cwd=cwd, stdout=stream, stderr=subprocess.STDOUT)
        results.append({"command": f"npm run {script}", "cwd": cwd.relative_to(ROOT).as_posix(), "exit_code": result.returncode, "seconds": round(time.monotonic() - start, 2), "log": log.name})
        print(f"{stage}: {script}: {result.returncode}", flush=True)
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
