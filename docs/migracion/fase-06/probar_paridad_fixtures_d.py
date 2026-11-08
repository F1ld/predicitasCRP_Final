"""Referencia preservada/canónico nuevo; solo CSV QA, sin BD ni modelos."""
import argparse
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["legacy", "canonical"])
    args = parser.parse_args()
    if args.mode == "legacy":
        from app.modules.citas.synthetic import generar_citas
    else:
        from datasets.synthetic import generar_citas
    folder = Path("/results/bundle")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    output = {}
    for name, entry in manifest["files"].items():
        params = dict(entry["params"])
        params["desde"] = date.fromisoformat(params["desde"])
        rows = generar_citas(**params)
        actual = (folder / (name + ".csv")).read_bytes()
        fields = next(csv.reader(io.StringIO(actual.decode("utf-8"))))
        content = io.StringIO(newline="")
        writer = csv.DictWriter(content, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        assert content.getvalue().encode("utf-8") == actual, name
        assert hashlib.sha256(actual).hexdigest() == entry["sha256"]
        output[name] = {"rows": len(rows), "columns": len(fields), "sha256": entry["sha256"]}
    with Path("/results/paridad-" + args.mode + ".json").open("x", encoding="utf-8") as stream:
        json.dump(output, stream, sort_keys=True, indent=2)
    print(args.mode + ": nueve escenarios idénticos byte por byte")


if __name__ == "__main__":
    main()
