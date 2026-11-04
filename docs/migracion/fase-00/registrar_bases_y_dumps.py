"""Evidencia publica sin filas/passwords; dumps privados de clones, nunca originales."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


TABLES = {
    "usuarios": "id_usuario", "citas": "id_cita",
    "historial_estados_cita": "id_historial", "predicciones_ia": "id_prediccion",
    "intervenciones": "id_intervencion", "lista_espera": "id_candidato",
    "cupos_liberados": "id_cupo_liberado", "reasignaciones": "id_reasignacion",
    "auditoria_eventos": "id_log",
}


def run(*args, input=None):
    result = subprocess.run(args, input=input, text=True, encoding="utf-8", capture_output=True)
    if result.returncode:
        # No imprimir argumentos de comandos que pudieran contener secretos.
        raise RuntimeError(f"Comando fallo ({args[0]}): {result.stderr}")
    return result.stdout


def query(container, sql):
    return run("docker", "exec", "-i", container, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "predicitas_owner", "-d", "predicitas", "-At", input=sql)


def capture(container):
    sql = Path(__file__).with_name("catalogo.sql").read_text(encoding="utf-8")
    catalog = json.loads(query(container, sql))
    rows = []
    for table, primary_key in TABLES.items():
        result = query(container, f"SELECT count(*), md5(coalesce(string_agg(row_to_json(t)::text, E'\\n' ORDER BY {primary_key}), '')) FROM public.{table} t;")
        count, fingerprint = result.strip().split("|")
        rows.append({"table": table, "count": int(count), "data_fingerprint_md5": fingerprint})
    catalog["counts_and_fingerprints"] = rows
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id.startswith("predicitas-fase0-"):
        raise SystemExit("Solo clones fase0.")
    private = args.private_dir.resolve(strict=True)
    evidence = Path(__file__).resolve().parent
    backups = []
    for alias in ("crp", "backend", "qa"):
        container = f"{args.run_id}-db-{alias}"
        catalog = capture(container)
        path = evidence / f"bd_{alias}_baseline.json"
        with path.open("x", encoding="utf-8") as stream:
            json.dump(catalog, stream, ensure_ascii=False, indent=2)
        for filename, program, options in (
            (f"{alias}.dump", "pg_dump", ["-Fc", "-d", "predicitas"]),
            (f"{alias}_globals_privado.sql", "pg_dumpall", ["--globals-only"]),
        ):
            target = private / filename
            if target.exists():
                raise SystemExit(f"No se sobrescribe {filename}")
            run("docker", "exec", container, program, "-U", "predicitas_owner", *options, "-f", f"/tmp/{filename}")
            run("docker", "cp", f"{container}:/tmp/{filename}", str(target))
            backups.append({"alias": alias, "filename": filename, "bytes": target.stat().st_size, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "location": "private_backup_directory"})
        print(f"{alias}: " + ", ".join(f"{row['table']}={row['count']}" for row in catalog["counts_and_fingerprints"]))
    with (evidence / "dumps_privados.json").open("x", encoding="utf-8") as stream:
        json.dump(backups, stream, indent=2)


if __name__ == "__main__":
    main()
