"""Ejecuta el seed REAL solo en un laboratorio nuevo; nunca limpia tablas."""
from collections import Counter
from contextlib import redirect_stdout
from datetime import date, datetime
import io
import json
from pathlib import Path
import secrets
import sys
from unittest.mock import patch

from sqlalchemy import event, select, text

from app.core.database import Base, SessionLocal, engine
from app.core.reloj import LIMA
from app.core.security import verify_password
from app.modules.citas import importer
from app.modules.citas.synthetic import generar_citas
from scripts import seed

PARAMS = {"historicas": 1000, "proximas": 80, "semilla": 42,
          "desde": "2026-11-06", "tasa_no_show": 0.20}
NOW = datetime(2026, 11, 6, 8, tzinfo=LIMA)


def snapshot():
    # Nueva conexión física, sin compartir la transacción que se observa.
    with engine.connect() as conn:
        return {t.name: [dict(r) for r in conn.execute(select(t).order_by(*t.primary_key.columns)).mappings()]
                for t in Base.metadata.sorted_tables}


def counts(state):
    return {name: len(rows) for name, rows in state.items()}


def run_seed(password):
    args = ["seed", "--historicas", "1000", "--proximas", "80", "--semilla", "42",
            "--desde", PARAMS["desde"], "--tasa-no-show", "0.20"]
    # El secreto no se escribe en argv, stdout ni evidencia.
    with patch.dict("os.environ", {"SEED_PASSWORD": password}), patch.object(sys, "argv", args), \
            patch.object(importer, "ahora_lima", return_value=NOW), redirect_stdout(io.StringIO()):
        seed.main()


def main():
    if engine.url.database != "predicitas_fase4_test" or not (engine.url.host or "").startswith("predicitas-fase4-seed-"):
        raise SystemExit("Destino no autorizado para seed")
    target = Path(sys.argv[1])
    if target.exists():
        raise SystemExit("No sobrescribir evidencia")
    with engine.connect() as conn:
        assert conn.scalar(text("select current_user")) == "predicitas_app"
    initial = snapshot()
    assert all(not rows for rows in initial.values()), "Se exige BD nueva vacía; no se permite borrar datos"
    password = secrets.token_urlsafe(32)
    commit_calls, flushed = [], []

    def tracked_session():
        db = SessionLocal()
        event.listen(db, "before_commit", lambda session: commit_calls.append(True))
        return db

    class FalloSeed(RuntimeError):
        pass

    original_append = importer.registrar_evento
    def fail_after_flush(db, **kwargs):
        result = original_append(db, **kwargs)
        if kwargs["accion"] == "IMPORT":
            db.flush()
            local_counts = {t.name: len(list(db.execute(select(t)))) for t in Base.metadata.sorted_tables}
            assert local_counts["usuarios"] == 3 and local_counts["citas"] == 1080
            assert local_counts["historial_estados_cita"] == 2080 and local_counts["auditoria_eventos"] == 1
            assert snapshot() == initial, "Una conexión externa vio cambios sin commit"
            flushed.append(local_counts)
            raise FalloSeed("QA seed: fallo inducido tras flush")
        return result

    with patch.object(seed, "SessionLocal", tracked_session):
        with patch.object(importer, "registrar_evento", fail_after_flush):
            try:
                run_seed(password)
            except FalloSeed:
                pass
            else:
                raise AssertionError("No se indujo fallo")
        assert flushed and not commit_calls and snapshot() == initial

        run_seed(password)
        assert len(commit_calls) == 1
        loaded = snapshot()
        totals = counts(loaded)
        assert totals["usuarios"] == 3 and totals["citas"] == 1080
        assert totals["historial_estados_cita"] == 2080 and totals["auditoria_eventos"] == 1
        assert all(n == 0 for name, n in totals.items() if name not in {
            "usuarios", "citas", "historial_estados_cita", "auditoria_eventos"})
        users = loaded["usuarios"]
        assert {(u["correo_institucional"], u["rol"]) for u in users} == {(c, r) for _, c, r in seed.USUARIOS_DEMO}
        assert all(u["activo"] and verify_password(password, u["password_hash"]) for u in users)
        actor = next(u["id_usuario"] for u in users if u["rol"] == "ADMINISTRADOR")
        rows = loaded["citas"]
        assert len({c["id_cita_externa"] for c in rows}) == 1080
        assert len({u["correo_institucional"] for u in users}) == 3
        source = generar_citas(historicas=1000, proximas=80, semilla=42, desde=date(2026, 11, 6),
                               tasa_no_show=0.20, con_invalidas=False)
        expected = {r["id_cita_externa"]: r for r in source}
        assert len(expected) == len(rows)
        histories = loaded["historial_estados_cita"]
        per_cita = {}
        for h in histories:
            assert h["id_usuario_actor"] == actor
            per_cita.setdefault(h["id_cita"], []).append((h["estado_anterior"], h["estado_nuevo"]))
        for c in rows:
            raw = expected[c["id_cita_externa"]]
            reg, derived = importer.validar_fila(raw, NOW)
            for field in ("paciente_anon_id", "sede", "especialidad", "medico", "tipo_paciente", "canal_origen",
                          "fecha_hora_cita", "fecha_registro_cita", "estado_actual", "inasistencias_previas",
                          "asistencias_previas", "reprogramaciones_prev"):
                assert c[field] == getattr(reg, field), (c["id_cita_externa"], field)
            assert all(c[k] == v for k, v in derived.items())
            assert c["target_no_show"] == raw["target_no_show"]
            wanted = [(None, "RECIBIDA")]
            if c["estado_actual"] != "RECIBIDA":
                wanted.append(("RECIBIDA", c["estado_actual"]))
            assert per_cita.pop(c["id_cita"]) == wanted
        assert not per_cita
        states = Counter(c["estado_actual"] for c in rows)
        assert states["RECIBIDA"] == 80 and states["ATENDIDA"] + states["NO_SHOW"] == 1000
        audit = loaded["auditoria_eventos"][0]
        assert audit["accion"] == "IMPORT" and audit["id_usuario"] == actor
        assert {k: audit["datos_after"][k] for k in ("recibidas", "aceptadas", "rechazadas")} == {
            "recibidas": 1080, "aceptadas": 1080, "rechazadas": 0}

        other_password = secrets.token_urlsafe(32)
        run_seed(other_password)
        assert len(commit_calls) == 2
        rerun = snapshot()
        assert loaded == rerun, "La reejecución cambió datos persistidos"
        assert all(verify_password(password, u["password_hash"]) and
                   not verify_password(other_password, u["password_hash"]) for u in rerun["usuarios"])

    evidence = {"parameters": PARAMS, "clock_lima": NOW.isoformat(), "runtime_role": "predicitas_app",
        "rollback": {"failure_after_flush": True, "uncommitted_rows_invisible": True,
                     "after_close_empty": True, "commit_attempts": 0, "flushed_counts": flushed[0]},
        "full_seed": {"counts": totals, "states": dict(states), "commit_attempts": 1,
                      "all_business_fields_and_histories_match": True, "audit_matches": True},
        "rerun": {"all_persisted_rows_identical": True, "passwords_preserved": True,
                  "duplicates": 0, "commit_attempts": 1},
        "limitations": ["No prueba recuperación de carga parcial: se conserva retorno legacy si existe alguna CIT-SIM-*",
                        "Las secuencias PostgreSQL pueden avanzar tras rollback; no se exige continuidad de IDs",
                        "Solo datos sintéticos en laboratorio nuevo; no se publica contraseña ni hash de contraseña"]}
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print("Seed real: rollback tras flush, carga 1080 y reejecución inalterada: PASÓ")


if __name__ == "__main__":
    main()
