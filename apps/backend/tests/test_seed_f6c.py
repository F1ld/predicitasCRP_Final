"""Seed explícito: sin generador, sin cambios destructivos ni rotación implícita."""
import csv
from datetime import datetime
import hashlib
import io
from pathlib import Path
import uuid

import pytest
from sqlalchemy import func, select, text

from app.modules.citas.models import Cita, HistorialEstadoCita
from app.modules.usuarios.models import Usuario
from scripts import seed

NOW = datetime.fromisoformat("2026-11-07T12:00:00-05:00")
PASSWORD = "SoloPruebas123!"


def rows():
    key = uuid.uuid4().hex[:12]
    base = dict(id_cita_externa=f"CIT-SIM-{key}-1", paciente_anon_id=f"PAC-SIM-{key}",
        sede="SAN_ISIDRO", especialidad="CARDIOLOGIA", medico="Dra. Prueba Álvarez",
        fecha_hora_cita="2026-10-26T09:00:00-05:00", fecha_registro_cita="2026-10-20T09:00:00-05:00",
        tipo_paciente="CONTINUADOR", canal_origen="WEB", inasistencias_previas="0",
        reprogramaciones_prev="0", asistencias_previas="0", estado_actual="ATENDIDA")
    return [base, base | dict(id_cita_externa=f"CIT-SIM-{key}-2", fecha_hora_cita="2026-10-27T09:00:00-05:00", estado_actual="NO_SHOW")]


def encode(data):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=seed.COLUMNAS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(data)
    return stream.getvalue().encode("utf-8")


def apply(db, data, **changes):
    options = dict(digest=hashlib.sha256(encode(data)).hexdigest(), confirmar_bd=db.scalar(text("select current_database()")),
                   ahora=NOW, obtener_password=lambda: PASSWORD)
    return seed.aplicar_seed(db, data, **(options | changes))


def test_csv_bom_unicode_nulls(tmp_path):
    data = rows()
    data[0]["inasistencias_previas"] = ""
    raw = b"\xef\xbb\xbf" + encode(data)
    path = tmp_path / "seed.csv"
    path.write_bytes(raw)
    parsed, digest = seed.leer_csv(path, hashlib.sha256(raw).hexdigest())
    assert "inasistencias_previas" not in parsed[0]
    assert parsed[0]["medico"] == "Dra. Prueba Álvarez"
    assert digest == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("bad", [b"", b"x,y\n1,2\n", b"\xff", b"a" * (seed.MAX_BYTES + 1)])
def test_bad_csv_is_rejected(tmp_path, bad):
    path = tmp_path / "seed.csv"
    path.write_bytes(bad)
    with pytest.raises(seed.SeedError):
        seed.leer_csv(path, hashlib.sha256(bad).hexdigest())


def test_hash_and_columns_are_required(tmp_path):
    path = tmp_path / "seed.csv"
    raw = encode(rows())
    path.write_bytes(raw)
    with pytest.raises(seed.SeedError, match="HASH"):
        seed.leer_csv(path, "0" * 64)
    path.write_bytes(raw + b"extra,columns\n")
    with pytest.raises(seed.SeedError):
        seed.leer_csv(path, hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(seed.SeedError):
        seed.leer_csv(Path("relative.csv"), "0" * 64)


def test_fully_repeatable_without_password_rotation(db, monkeypatch):
    data = rows()
    first = apply(db, data)
    assert first.insertadas == 2 and first.usuarios_creados == 3
    users = list(db.scalars(select(Usuario).order_by(Usuario.id_usuario)))
    hashes = {u.id_usuario: u.password_hash for u in users}
    history = db.scalar(select(func.count()).select_from(HistorialEstadoCita))
    def forbidden():
        pytest.fail("No debe solicitar contraseña en un rerun")
    monkeypatch.setattr(seed, "hash_password", lambda _: pytest.fail("No debe recalcular claves existentes"))
    second = apply(db, data, obtener_password=forbidden)
    assert (second.insertadas, second.existentes, second.usuarios_creados) == (0, 2, 0)
    assert history == db.scalar(select(func.count()).select_from(HistorialEstadoCita))
    assert hashes == {u.id_usuario: u.password_hash for u in db.scalars(select(Usuario))}


def test_partial_requires_explicit_reconciliation(db):
    data = rows()
    apply(db, data[:1])
    with pytest.raises(seed.SeedError, match="CARGA_PARCIAL") as error:
        apply(db, data)
    assert error.value.conteos == {"existentes": 1, "faltantes": 1}
    result = apply(db, data, reconciliar=True)
    assert (result.insertadas, result.existentes, result.reconciliada) == (1, 1, True)
    assert apply(db, data).insertadas == 0


def test_conflict_never_overwrites_existing(db):
    data = rows()
    apply(db, data)
    modified = [data[0] | {"medico": "Otra persona"}, data[1]]
    with pytest.raises(seed.SeedError, match="DIFERENTES"):
        apply(db, modified, reconciliar=True)
    stored = db.scalar(select(Cita).where(Cita.id_cita_externa == data[0]["id_cita_externa"]))
    assert stored.medico == data[0]["medico"]


def test_null_counters_follow_importer_and_targets(db):
    data = rows()
    data[1] = data[1] | {"estado_actual": "RECIBIDA", "fecha_registro_cita": "2026-10-27T08:00:00-05:00"}
    data[1].pop("inasistencias_previas")
    data[1].pop("asistencias_previas")
    apply(db, data)
    row = db.scalar(select(Cita).where(Cita.id_cita_externa == data[1]["id_cita_externa"]))
    assert row.asistencias_previas == 1 and row.inasistencias_previas == 0
    assert row.target_no_show is None
    assert apply(db, data).insertadas == 0


def test_partial_with_stale_inferred_counter_is_not_silently_reconciled(db):
    data = rows()
    data[1] = data[1] | {"estado_actual": "RECIBIDA", "fecha_registro_cita": "2026-10-27T08:00:00-05:00"}
    data[1].pop("inasistencias_previas")
    data[1].pop("asistencias_previas")
    apply(db, data[1:])  # El histórico aún no existe: infiere 0.
    with pytest.raises(seed.SeedError, match="DIFERENTES"):
        apply(db, data, reconciliar=True)
    assert db.scalar(select(func.count()).select_from(Cita)) == 1


@pytest.mark.parametrize("kind", ["duplicate", "invalid", "future", "real-id", "password", "database"])
def test_preflight_failure_creates_no_users_or_appointments(db, kind):
    data = rows()
    options = {}
    if kind == "duplicate":
        data[1] = data[0]
    elif kind == "invalid":
        data[1]["especialidad"] = "INVALIDA"
    elif kind == "future":
        data[1]["fecha_hora_cita"] = "2030-10-26T09:00:00-05:00"
    elif kind == "real-id":
        data[1]["paciente_anon_id"] = "Paciente123"
    elif kind == "password":
        options["obtener_password"] = lambda: "weak"
    else:
        options["confirmar_bd"] = "otra_bd"
    with pytest.raises(seed.SeedError):
        apply(db, data, **options)
    assert db.scalar(select(func.count()).select_from(Usuario)) == 0
    assert db.scalar(select(func.count()).select_from(Cita)) == 0


@pytest.mark.parametrize("change", ["rol", "activo"])
def test_existing_user_conflict_is_not_silently_fixed(db, change):
    data = rows()
    apply(db, data)
    admin = db.scalar(select(Usuario).where(Usuario.correo_institucional == "admin@predicitas.crp"))
    setattr(admin, change, "RECEPCION" if change == "rol" else False)
    db.flush()
    with pytest.raises(seed.SeedError, match="USUARIO_DEMO_INCOMPATIBLE"):
        apply(db, data)


def test_password_is_local_and_not_cli_argument(monkeypatch):
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)
    assert seed._obtener_password() == PASSWORD
    with pytest.raises(SystemExit) as error:
        seed.main(["--password", "DO_NOT_ACCEPT"])
    assert error.value.code == 2


def test_seed_has_no_generator_or_destructive_recipe():
    import ast
    source = Path(seed.__file__).read_text(encoding="utf-8")
    modules = [node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]
    assert not any("synthetic" in m or m.startswith(("datasets", "training")) for m in modules)
    assert "downgrade" not in source and "generar_citas" not in source
