"""Comandos offline; no se ejecutan al arrancar el servicio de inferencia."""
import argparse
from datetime import date, datetime
from pathlib import Path

from jsonschema.exceptions import ValidationError

from training.pipeline import generar, validar_dataset, entrenar_candidato


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts-dir", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generar")
    generate.add_argument("--version-dataset", required=True)
    generate.add_argument("--semilla", required=True, type=int, choices=[42])
    generate.add_argument("--fecha-corte", required=True, type=date.fromisoformat)
    generate.add_argument("--generado-en", required=True, type=datetime.fromisoformat)
    generate.add_argument("--fuente", required=True, choices=["SINTETICO_GENERADO"])
    generate.add_argument("--directorio", required=True, type=Path)
    generate.add_argument("--proximas", required=True, type=int)
    validate = commands.add_parser("validar")
    validate.add_argument("--dataset", required=True, type=Path)
    train = commands.add_parser("entrenar")
    train.add_argument("--dataset", required=True, type=Path)
    train.add_argument("--version-modelo", required=True)
    train.add_argument("--fecha", required=True, type=datetime.fromisoformat)
    train.add_argument("--directorio", required=True, type=Path)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    args["contracts"] = args.pop("contracts_dir")
    try:
        if command == "generar":
            result = generar(**args)
        elif command == "entrenar":
            result = entrenar_candidato(**args)
        else:
            _, manifest, _ = validar_dataset(**args)
            result = "Dataset válido: " + manifest["version_dataset"]
    except (ValueError, OSError, RuntimeError, ValidationError) as exc:
        parser.exit(1, f"Pipeline detenido: {exc}\n")
    print(result)


if __name__ == "__main__":
    main()
