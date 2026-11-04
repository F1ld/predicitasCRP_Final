"""Compara restauracion logica y prepara una BD de pruebas NUEVA en el servidor aislado."""
import argparse
import json
from pathlib import Path
import re
import secrets

from registrar_bases_y_dumps import capture, run


def normalize_array_cast(definition):
    # pg_dump/restore puede expandir el cast varchar[] -> text[] a cada literal.
    # Normalizar SOLO ese caso, conservando operadores, valores y parentesis.
    def expand(match):
        elements = match.group(1).split(", ")
        if not all(re.fullmatch(r"'[A-Z_]+'::character varying", item) for item in elements):
            return match.group(0)
        return "ARRAY[" + ", ".join(f"({item})::text" for item in elements) + "]"
    return re.sub(r"\(ARRAY\[(.*?)\]\)::text\[\]", expand, definition)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    private = args.private_dir.resolve(strict=True)
    evidence = Path(__file__).resolve().parent
    container = "predicitas-fase0-20261103-2200-restore"
    original = json.loads((evidence / "bd_crp_baseline.json").read_text(encoding="utf-8"))
    restored = capture(container)
    restored["roles_without_passwords"] = [role for role in restored["roles_without_passwords"] if role["name"] != "fase0_restore_admin"]
    raw_constraints = []
    for before, after in zip(original["constraints"], restored["constraints"], strict=True):
        if before != after:
            raw_constraints.append({"before": before, "after": after, "same_after_literal_array_cast_normalization": normalize_array_cast(before["definition"]) == normalize_array_cast(after["definition"])})
    comparable_original = {**original, "constraints": [{**row, "definition": normalize_array_cast(row["definition"])} for row in original["constraints"]]}
    comparable_restored = {**restored, "constraints": [{**row, "definition": normalize_array_cast(row["definition"])} for row in restored["constraints"]]}
    differences = [key for key in comparable_original if comparable_original[key] != comparable_restored.get(key)]
    with (evidence / "restore_verificado.json").open("x", encoding="utf-8") as stream:
        json.dump({"source_volume": "predicitas-crp_pgdata", "destination_container": container, "custom_dump_restored": True, "globals_restored": True, "matching_catalog_sections": [key for key in original if key not in differences], "differences": differences, "constraint_text_differences_reviewed": raw_constraints, "all_nine_table_counts_and_fingerprints_match": original["counts_and_fingerprints"] == restored["counts_and_fingerprints"], "note": "El rol bootstrap fase0_restore_admin se excluye de la comparacion. Solo se normaliza expansion equivalente de casts de arrays de literales varchar a text; diferencias originales se conservan."}, stream, ensure_ascii=False, indent=2)
    if differences:
        raise SystemExit(f"Diferencias de restauracion: {differences}")
    print("Restore verificado: catalogo, datos, secuencias, constraints, indices, triggers, permisos y RLS coinciden.")
    # Solo ahora preparar otra BD, vacia y separada, para pruebas destructivas.
    password = secrets.token_hex(32)
    owner_password = secrets.token_hex(32)
    sql = f"ALTER ROLE predicitas_app PASSWORD '{password}'; ALTER ROLE predicitas_owner PASSWORD '{owner_password}'; CREATE DATABASE predicitas_fase0_test OWNER predicitas_owner;"
    run("docker", "exec", "-i", container, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "fase0_restore_admin", "-d", "postgres", input=sql)
    with (private / "tests-runtime.env").open("x", encoding="ascii") as stream:
        stream.write(f"DATABASE_URL=postgresql+psycopg://predicitas_app:{password}@{container}:5432/predicitas_fase0_test\n")
        stream.write(f"DATABASE_URL_MIGRACIONES=postgresql+psycopg://predicitas_owner:{owner_password}@{container}:5432/predicitas_fase0_test\n")
        stream.write(f"SECRET_KEY={secrets.token_hex(32)}\nENVIRONMENT=fase0_test\nPYTHONPATH=/workspace\nPYTHONDONTWRITEBYTECODE=1\nIA_URL=http://127.0.0.1:8191\n")
    print("BD predicitas_fase0_test creada; passwords aleatorios SOLO en servidor restore aislado y archivo privado.")


if __name__ == "__main__":
    main()
