"""Materializa fixtures sintéticos explícitos para QA, nunca al servir peticiones."""
import argparse
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path

from datasets.synthetic import generar_citas
from datasets.operational_csv import COLUMNAS

# Fechas históricas congeladas, no citas futuras respecto al reloj del usuario.
SCENARIOS = {
    "citas": dict(historicas=30, proximas=10, semilla=7, prefijo="TST", con_invalidas=True),
    "rendimiento": dict(historicas=5000, proximas=0, semilla=11, prefijo="PRF", con_invalidas=False),
    "predictor": dict(historicas=1000, proximas=80, semilla=42, prefijo="SIM", con_invalidas=False),
    "ux45": dict(historicas=0, proximas=45, semilla=42, prefijo="UX", con_invalidas=True),
    "uxapi20": dict(historicas=0, proximas=20, semilla=42, prefijo="UXAPI", con_invalidas=True),
    "uxweb20": dict(historicas=0, proximas=20, semilla=42, prefijo="UXWEB", con_invalidas=True),
    "muestra3": dict(historicas=0, proximas=3, semilla=7, prefijo="DEMO", con_invalidas=True),
    "muestra3-dia2": dict(historicas=0, proximas=3, semilla=7, prefijo="DEMO", con_invalidas=True),
    "muestra2": dict(historicas=0, proximas=2, semilla=7, prefijo="DEMO", con_invalidas=True),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True, help="Directorio absoluto NUEVO")
    args = parser.parse_args()
    output = args.salida
    if not output.is_absolute() or output.exists() or output.is_symlink():
        parser.error("Directorio absoluto nuevo requerido")
    if output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error("No escribir dentro del código IA")
    output.mkdir()
    manifest = {"version": 1, "es_simulacion": True, "origen": "apps/ia/datasets/synthetic.py", "files": {}}
    for name, scenario in SCENARIOS.items():
        reference = date(2026, 11, 6 if name == "muestra3-dia2" else 5) if name.startswith("muestra") else date(2026, 10, 29)
        params = scenario | {"desde": reference.isoformat()}
        rows = generar_citas(**scenario, desde=reference)
        text = io.StringIO(newline="")
        writer = csv.DictWriter(text, fieldnames=COLUMNAS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        content = text.getvalue().encode("utf-8")
        with (output / (name + ".csv")).open("xb") as stream:
            stream.write(content)
        manifest["files"][name] = {"sha256": hashlib.sha256(content).hexdigest(), "rows": len(rows), "params": params}
    with (output / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, sort_keys=True, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
