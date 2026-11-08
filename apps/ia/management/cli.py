"""Administración manual de releases; sin endpoints ni recarga automática."""
import argparse
import json
from pathlib import Path

from management.releases import promote, rollback, import_legacy, read_state, root_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("promover", "rollback", "importar-legacy", "estado"):
        sub = commands.add_parser(name)
        sub.add_argument("--registry", required=True, type=Path)
        if name != "estado":
            sub.add_argument("--esperado", required=True, dest="expected")
        if name == "promover":
            sub.add_argument("--candidato", required=True, type=Path, dest="candidate")
            sub.add_argument("--manifest-sha256", required=True)
            sub.add_argument("--aprobar-version", required=True, dest="approved_version")
            sub.add_argument("--contracts-dir", required=True, type=Path, dest="contracts")
        if name == "importar-legacy":
            sub.add_argument("--modelo", required=True, type=Path, dest="model")
        if name == "rollback":
            sub.add_argument("--a-version", dest="target_release")
            sub.add_argument("--approval-sha256")
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        if command == "promover":
            result = promote(**args)
        elif command == "rollback":
            result = rollback(**args)
        elif command == "importar-legacy":
            result = import_legacy(**args)
        else:
            result = read_state(root_path(args["registry"]))
    except Exception as exc:
        # Errores locales sanitizados: no volcar contenido pickle/datasets/rutas.
        parser.exit(1, f"Operación cancelada ({type(exc).__name__}); consulte estado antes de reintentar.\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
