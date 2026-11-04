"""Revalida archivos de aplicaciones y tar de volumenes originales en solo lectura."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--output-name", default="originales_verificados.json")
    args = parser.parse_args()
    if Path(args.output_name).name != args.output_name or not args.output_name.endswith(".json"):
        raise SystemExit("El nombre de evidencia debe ser un archivo JSON local.")
    evidence = Path(__file__).resolve().parent
    private = args.private_dir.resolve(strict=True)
    inventory = json.loads((private / "inventario_privado.json").read_text(encoding="utf-8"))
    changes = []
    checked = 0
    for row in inventory:
        relative = row["path"]
        # El plan/bitacora es lo unico preexistente que se actualiza en fase0.
        if relative.startswith(".git/") or relative == "PLAN_REESTRUCTURACION_POR_FASES.md":
            continue
        path = Path(relative)
        checked += 1
        if not path.is_file() or digest_file(path) != row["sha256"]:
            # No publicar hashes ni contenidos de .env.
            changes.append(relative)
    volumes = json.loads((evidence / "volumenes_respaldados.json").read_text(encoding="utf-8-sig"))
    checks = []
    for row in volumes:
        volume = row["Source"]
        active = subprocess.check_output(["docker", "ps", "-q", "--filter", f"volume={volume}"], text=True).strip()
        if active:
            raise SystemExit(f"Hay escritores sobre volumen original {volume}; detener auditoria.")
        process = subprocess.Popen(["docker", "run", "--rm", "--network", "none", "--mount", f"type=volume,source={volume},target=/source,readonly", "--entrypoint", "tar", "postgres:16", "-cpf", "-", "-C", "/source", "."], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        digest = hashlib.sha256()
        for block in iter(lambda: process.stdout.read(1024 * 1024), b""):
            digest.update(block)
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        if process.wait() != 0:
            raise SystemExit(f"No se pudo revalidar {volume}: {stderr}")
        actual = digest.hexdigest()
        checks.append({"volume": volume, "same_tar_sha256_as_initial_snapshot": actual.lower() == row["Sha256"].lower(), "sha256": actual})
    result = {"existing_files_checked": checked, "changed_existing_files_excluding_plan_and_git_metadata": changes, "original_volumes": checks, "note": "Se comparan todos los bytes serializados por tar, no solo conteos. Solo montajes RO y sin escritores originales."}
    with (evidence / args.output_name).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))
    if changes or not all(row["same_tar_sha256_as_initial_snapshot"] for row in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
