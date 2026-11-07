"""CSV nuevo -> HTTP/backend empaquetado -> PostgreSQL NUEVO, rol app."""
import csv
from datetime import datetime
import io
import json
from pathlib import Path
import secrets
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.database import Base, engine
from app.core.reloj import LIMA, reloj
from app.core.security import hash_password
from app.main import app
from app.modules.citas import importer
from app.modules.citas.models import Cita, HistorialEstadoCita
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.usuarios.models import Usuario

NOW = datetime(2026, 11, 6, 8, tzinfo=LIMA)


def main():
    if engine.url.database != "predicitas_fase4_test" or not (engine.url.host or "").startswith("predicitas-fase4-csv-"):
        raise SystemExit("Solo laboratorio CSV B exclusivo")
    folder = Path("/results")
    target = folder / "csv_http_b.json"
    assert not target.exists()
    observer = create_engine(engine.url, poolclass=NullPool)

    def snapshot():
        with observer.connect() as conn:
            return {t.name: [dict(r) for r in conn.execute(select(t).order_by(*t.primary_key.columns)).mappings()]
                    for t in Base.metadata.sorted_tables}

    def decode(data):
        return [{k: v for k, v in r.items() if k and v not in (None, "")} for r in csv.DictReader(io.StringIO(data.decode("utf-8-sig")))]

    try:
        initial = snapshot()
        assert all(not r for r in initial.values())
        password, email = secrets.token_urlsafe(24), f"csv-b-{secrets.token_hex(8)}@example.invalid"
        with Session(engine) as db:
            assert db.scalar(text("select current_user")) == "predicitas_app"
            actor = Usuario(nombre_completo="QA CSV B sintético", correo_institucional=email,
                password_hash=hash_password(password), rol="RECEPCION", activo=True)
            db.add(actor)
            db.commit()
            actor_id = actor.id_usuario
        app.dependency_overrides[reloj] = lambda: NOW
        with TestClient(app, raise_server_exceptions=False) as client:
            login = client.post("/auth/login", data={"username": email, "password": password})
            assert login.status_code == 200
            headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            def upload(data, name):
                return client.post("/citas/importar", headers=headers, files={"archivo": (name, data, "text/csv")})
            data = (folder / "seed_operacional.csv").read_bytes()
            source = json.loads((folder / "seed_source.json").read_text())
            assert len(source) == 1080
            response = upload(data, "seed_qa_b.csv")
            assert response.status_code == 200, response.status_code
            result = response.json()
            assert (result["aceptadas"], result["rechazadas"]) == (1080, 0)
            stored = snapshot()
            by_id = {r["id_cita_externa"]: r for r in stored["citas"]}
            assert len(by_id) == 1080 and len(stored["historial_estados_cita"]) == 2080
            histories = {}
            for h in stored["historial_estados_cita"]:
                assert h["id_usuario_actor"] == actor_id
                histories.setdefault(h["id_cita"], []).append((h["estado_anterior"], h["estado_nuevo"]))
            for raw in source:
                row = by_id[raw["id_cita_externa"]]
                for key, value in raw.items():
                    if key in ("fecha_hora_cita", "fecha_registro_cita"):
                        value = datetime.fromisoformat(value)
                    assert row[key] == value, (raw["id_cita_externa"], key)
                wanted = [(None, "RECIBIDA")]
                if raw["estado_actual"] != "RECIBIDA":
                    wanted.append(("RECIBIDA", raw["estado_actual"]))
                assert histories.pop(row["id_cita"]) == wanted
            assert not histories
            repeat = upload(data, "repeat_qa_b.csv")
            assert repeat.status_code == 200
            assert (repeat.json()["aceptadas"], repeat.json()["rechazadas"]) == (0, 1080)
            after_repeat = snapshot()
            assert after_repeat["citas"] == stored["citas"] and after_repeat["historial_estados_cita"] == stored["historial_estados_cita"]

            extra_data = b"\xef\xbb\xbf" + (folder / "nulls_operacional.csv").read_bytes()
            extra = upload(extra_data, "nulls_bom_qa_b.csv")
            assert extra.status_code == 200 and (extra.json()["aceptadas"], extra.json()["rechazadas"]) == (4, 0)
            with Session(observer) as db:
                for raw in decode(extra_data):
                    row = db.scalar(select(Cita).where(Cita.id_cita_externa == raw["id_cita_externa"]))
                    normalized, derived = importer.validar_fila(raw, NOW)
                    for key in ("id_cita_externa", "paciente_anon_id", "sede", "especialidad", "medico", "fecha_hora_cita", "fecha_registro_cita", "tipo_paciente", "canal_origen", "estado_actual", "reprogramaciones_prev"):
                        assert getattr(row, key) == getattr(normalized, key), key
                    assert all(getattr(row, k) == v for k, v in derived.items())
                    if "-F" in row.id_cita_externa:
                        assert row.inasistencias_previas == row.asistencias_previas == 1
                        assert row.estado_actual == "RECIBIDA" and row.target_no_show is None
                    else:
                        assert row.target_no_show == int(row.estado_actual == "NO_SHOW")
            before_failure = snapshot()
            reached = []
            append = importer.registrar_evento
            def fail(db, **kwargs):
                event = append(db, **kwargs)
                if kwargs["accion"] == "IMPORT":
                    db.flush()
                    reached.append(True)
                    assert snapshot() == before_failure
                    raise RuntimeError("QA CSV B fallo inducido tras flush")
                return event
            rows = decode(extra_data)
            row = dict(rows[-1], id_cita_externa="CIT-QA-B-ROLLBACK")
            text_csv = io.StringIO(newline="")
            writer = csv.DictWriter(text_csv, fieldnames=list(row), lineterminator="\n")
            writer.writeheader()
            writer.writerow(row)
            with patch.object(importer, "registrar_evento", fail):
                failed = upload(text_csv.getvalue().encode("utf-8"), "rollback_qa_b.csv")
            assert failed.status_code == 500 and reached and snapshot() == before_failure
        final = snapshot()
        assert len(final["citas"]) == 1084 and len(final["historial_estados_cita"]) == 2086
        assert len({r["id_cita_externa"] for r in final["citas"]}) == 1084
        imports = [e for e in final["auditoria_eventos"] if e["accion"] == "IMPORT"]
        assert len(imports) == 3
        assert all(e["id_usuario"] == actor_id for e in imports)
        assert [(e["datos_after"]["aceptadas"], e["datos_after"]["rechazadas"]) for e in imports] == [(1080, 0), (0, 1080), (4, 0)]
        result = {"full_csv": {"accepted": 1080, "rejected": 0, "all_generated_fields_match_database": True},
            "repeat": {"accepted": 0, "rejected": 1080, "appointments_and_histories_unchanged": True},
            "nulls_bom_unicode_offsets": {"accepted": 4, "defaults_and_prior_counters_correct": True,
                "target_derived_from_state": True},
            "rollback": {"failure_after_flush": True, "independent_connection_unchanged": True},
            "final_counts": {"appointments": 1084, "histories": 2086, "import_events": 3},
            "runtime_role": "predicitas_app", "backend_source_mount": False,
            "transport": "ASGI/TestClient con sesiones de producción; PostgreSQL TCP independiente",
            "scope": "Solo laboratorio nuevo; actor/filas QA conservados, sin seed ni consumo productivo del CSV"}
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print("CSV B: HTTP/PostgreSQL, 1080 + 4 aceptadas, repetición sin duplicados, rollback independiente: PASÓ")
    finally:
        app.dependency_overrides.clear()
        observer.dispose()


if __name__ == "__main__":
    main()
