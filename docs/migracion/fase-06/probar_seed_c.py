"""Sonda de commit/rollback con observador independiente, solo laboratorio C."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from unittest.mock import patch

from sqlalchemy import create_engine, select, text
from sqlalchemy.pool import NullPool

from app.core.database import Base, engine
from app.modules.citas import importer
from scripts import seed


def main():
    if engine.url.database != "predicitas_f6c_test" or not (engine.url.host or "").startswith("predicitas-f6c-"):
        raise SystemExit("Solo laboratorio nuevo F6 C")
    output = Path("/results")
    path = Path("/inputs/seed.csv")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    rows, _ = seed.leer_csv(path, digest)
    assert len(rows) == 1080
    observer = create_engine(engine.url, poolclass=NullPool)
    os.environ["SEED_PASSWORD"] = "QA9-" + secrets.token_urlsafe(24)
    password = os.environ["SEED_PASSWORD"]

    def snapshot():
        with observer.connect() as conn:
            return {t.name: [dict(row) for row in conn.execute(select(t).order_by(*t.primary_key.columns)).mappings()]
                    for t in Base.metadata.sorted_tables}

    def execute(csv_path, extra=(), success=True):
        hash_csv = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        cmd = [sys.executable, "-B", "-m", "scripts.seed", "--csv", str(csv_path),
               "--sha256", hash_csv, "--confirmar-bd", engine.url.database, *extra]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        assert password not in result.stdout + result.stderr
        assert (result.returncode == 0) == success, (result.returncode, result.stdout, result.stderr)
        return json.loads(result.stdout if success else result.stderr)

    def save(rows, name):
        import csv
        import io
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=seed.COLUMNAS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        target = Path("/tmp") / name
        target.write_text(stream.getvalue(), encoding="utf-8")
        return target

    try:
        before = snapshot()
        assert all(not value for value in before.values())
        with observer.connect() as conn:
            assert conn.scalar(text("select current_user")) == "predicitas_app"
        reached = []
        append = importer.registrar_evento
        def fail(db, **kwargs):
            event = append(db, **kwargs)
            if kwargs["accion"] == "IMPORT":
                db.flush()
                reached.append(True)
                assert snapshot() == before
                raise RuntimeError("QA fallo tras flush de usuarios+citas+historial+auditoría")
            return event
        with patch.object(importer, "registrar_evento", fail):
            try:
                seed.ejecutar_seed(path, esperado=digest, confirmar_bd=engine.url.database)
            except RuntimeError:
                pass
            else:
                raise AssertionError("No se indujo el fallo")
        assert reached and snapshot() == before
        first = execute(path)
        assert first["insertadas"] == 1080 and first["usuarios_creados"] == 3
        loaded = snapshot()
        assert len(loaded["citas"]) == 1080 and len(loaded["historial_estados_cita"]) == 2080
        assert len(loaded["usuarios"]) == 3
        os.environ["SEED_PASSWORD"] = "OTRA9-" + secrets.token_urlsafe(24)
        repeat = execute(path)
        assert repeat["insertadas"] == repeat["usuarios_creados"] == 0
        assert snapshot() == loaded  # Incluye hashes, historial y auditoría: cero cambios.

        extras = [row | {"id_cita_externa": f"CIT-SIM-F6C-PARCIAL-{i}",
                         "paciente_anon_id": f"PAC-SIM-F6C-PARCIAL-{i}"} for i, row in enumerate(rows[:3])]
        one, all_three = save(extras[:1], "one.csv"), save(extras, "three.csv")
        assert execute(one)["insertadas"] == 1
        partial_before = snapshot()
        refused = execute(all_three, success=False)
        assert refused == {"error": "CARGA_PARCIAL_REQUIERE_RECONCILIAR", "existentes": 1, "faltantes": 2}
        assert snapshot() == partial_before
        reconciled = execute(all_three, ("--reconciliar",))
        assert reconciled["insertadas"] == 2 and reconciled["reconciliada"]
        after = snapshot()
        assert execute(all_three)["insertadas"] == 0 and snapshot() == after
        conflict = save([extras[0] | {"medico": "Otro nombre sintético"}, *extras[1:]], "conflict.csv")
        assert execute(conflict, ("--reconciliar",), success=False)["error"] == "CITAS_EXISTENTES_DIFERENTES_O_SIN_HISTORIAL"
        assert snapshot() == after

        # Otro seed no espera ni duplica mientras el primero retiene el lock.
        with observer.begin() as conn:
            assert conn.scalar(text("select pg_try_advisory_xact_lock(:key)"), {"key": seed.SEED_LOCK})
            assert execute(path, success=False)["error"] == "OTRO_SEED_EN_CURSO"
        assert snapshot() == after
        assert len(after["citas"]) == 1083
        assert len({c["id_cita_externa"] for c in after["citas"]}) == 1083
        assert sum(c["target_no_show"] is None for c in loaded["citas"]) == 80
        assert all(c["target_no_show"] == int(c["estado_actual"] == "NO_SHOW")
                   for c in loaded["citas"] if c["estado_actual"] in ("ATENDIDA", "NO_SHOW"))
        events = after["auditoria_eventos"]
        assert all(password not in json.dumps(e, default=str) and "password_hash" not in json.dumps(e, default=str) for e in events)
        result = {"primera_carga": first, "repeticion": repeat, "reconciliacion": reconciled,
            "rollback_tras_flush_observado_independientemente": True, "concurrencia_seed_rechazada": True,
            "rerun_sin_cambios_en_todas_las_tablas": True, "conflicto_sin_sobrescritura": True,
            "usuarios": len(after["usuarios"]), "citas": len(after["citas"]),
            "historiales": len(after["historial_estados_cita"]), "auditorias": len(events),
            "rol": "predicitas_app", "transporte": "CLI en subprocess + PostgreSQL TCP", "csv_sha256": digest}
        with (output / "integracion.json").open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print("Seed C: commit, repetición, reconciliación, conflictos, lock y rollback independiente: PASÓ")
    finally:
        observer.dispose()


if __name__ == "__main__":
    main()
