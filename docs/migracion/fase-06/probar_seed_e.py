"""Seed E: carga del CSV generado por el pipeline y repetición idempotente.

Solo laboratorio E; no genera datos ni reinicializa. Verifica conteos con una
conexión independiente y comprueba que la contraseña no aparece en la salida.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.database import engine


def main():
    if engine.url.database != "predicitas_f6e_test" or not (engine.url.host or "").startswith("predicitas-f6e-"):
        raise SystemExit("Solo laboratorio nuevo F6 E")
    path = Path("/inputs/seed.csv")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    password = os.environ["SEED_PASSWORD"]
    observer = create_engine(engine.url, poolclass=NullPool)

    def counts():
        with observer.connect() as conn:
            return {name: conn.scalar(text(f"select count(*) from {name}"))
                    for name in ("citas", "usuarios", "historial_estados_cita", "auditoria_eventos")}

    def execute():
        cmd = [sys.executable, "-B", "-m", "scripts.seed", "--csv", str(path),
               "--sha256", digest, "--confirmar-bd", engine.url.database]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        assert password not in result.stdout + result.stderr, "La contraseña no debe aparecer en la salida"
        assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
        return json.loads(result.stdout)

    try:
        with observer.connect() as conn:
            assert conn.scalar(text("select current_user")) == "predicitas_app"
            assert all(value == 0 for value in counts().values())

        first = execute()
        assert (first["recibidas"], first["existentes"], first["insertadas"], first["usuarios_creados"]) \
            == (1080, 0, 1080, 3), first
        loaded = counts()
        assert (loaded["citas"], loaded["usuarios"], loaded["historial_estados_cita"]) == (1080, 3, 2080), loaded

        repeat = execute()
        assert (repeat["recibidas"], repeat["existentes"], repeat["insertadas"], repeat["usuarios_creados"]) \
            == (1080, 1080, 0, 0), repeat
        assert counts() == loaded, "La repetición no debe alterar ninguna tabla"

        result = {
            "primera_carga": first,
            "repeticion": repeat,
            "citas": loaded["citas"],
            "usuarios": loaded["usuarios"],
            "historiales": loaded["historial_estados_cita"],
            "auditorias": loaded["auditoria_eventos"],
            "rerun_sin_cambios_en_todas_las_tablas": True,
            "rol": "predicitas_app",
            "csv_sha256": digest,
            "transporte": "CLI en subprocess + PostgreSQL TCP",
        }
        with (Path("/results") / "seed-e.json").open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
        print("Seed E: carga de 1080 filas y repetición idempotente aprobadas")
    finally:
        observer.dispose()


if __name__ == "__main__":
    main()
