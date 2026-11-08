"""Cableado, atomicidad y lifecycle; únicamente PostgreSQL de laboratorio."""
from decimal import Decimal
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.errores import MotorIANoDisponible
from app.main import app
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.citas.importer import importar_citas
from app.modules.citas.models import Cita
from app.modules.ia import service
from app.modules.ia.dependencias import crear_motor, obtener_motor
from app.modules.ia.models import PrediccionIA
from app.modules.ia.motor_http import MotorHTTP
from app.modules.ia.motor_integrado import MotorIntegrado
from app.modules.ia.puerto import ResultadoMotor
from tests.conftest import cabecera
from tests.test_ia_endpoints import CITAS_PRUEBA_IA


class DobleMotor:
    def __init__(self, db):
        self.db = db
        self.calls = 0
        self.error = None
        self.cambio = None

    def _fuera_transaccion(self):
        assert not self.db.in_transaction(), "HTTP no debe retener la transacción de lectura"

    def version(self):
        self._fuera_transaccion()
        return "doble-7b"

    def predecir(self, features, *, version):
        self._fuera_transaccion()
        self.calls += 1
        if self.error:
            raise self.error
        if self.cambio:
            self.cambio()
        return ResultadoMotor(version_modelo=version, probabilidad_no_show=Decimal("0.285"),
            nivel_riesgo="BAJO", umbral_aplicado=Decimal("0.450"), features_snapshot=features.snapshot(),
            explicabilidad_resumen="Doble de puerto [Simulado]")

    def predecir_lote(self, features, *, version):
        return [self.predecir(f, version=version) for f in features]

    def metricas(self):
        self._fuera_transaccion()
        return MotorIntegrado().metricas()

    def dataset(self):
        self._fuera_transaccion()
        return MotorIntegrado().dataset()

    def close(self):
        pass


@pytest.fixture
def escenario(db, usuarios, client):
    importar_citas(db, CITAS_PRUEBA_IA, id_usuario=usuarios["ADMINISTRADOR"].id_usuario,
                   ip="127.0.0.1", origen="7b-test")
    ids = list(db.scalars(select(Cita.id_cita).order_by(Cita.id_cita)))
    h = cabecera(client, usuarios["RECEPCION"])
    doble = DobleMotor(db)
    app.dependency_overrides[obtener_motor] = lambda: doble
    yield ids, h, doble
    app.dependency_overrides.pop(obtener_motor, None)


@pytest.mark.parametrize("route", ["/ia/predecir/{id}", "/citas/{id}/prediccion"])
def test_ambas_rutas_inyectan_puerto_y_auditan(client, db, escenario, route):
    ids, h, motor = escenario
    r = client.post(route.format(id=ids[0]), headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["version_modelo"] == "doble-7b"
    assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == 1
    assert db.scalar(select(func.count(AuditoriaEvento.id_log)).where(AuditoriaEvento.modulo == "IA")) == 1
    assert motor.calls == 1


def test_lote_forzar_y_sin_duplicados(client, db, escenario):
    ids, h, motor = escenario
    for path, expected in (("/ia/predecir-lote", 2), ("/ia/predecir-lote", 0), ("/ia/predecir-lote?forzar=true", 2)):
        r = client.post(path, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["evaluadas"] == expected
    assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == 2


@pytest.mark.skipif(not os.getenv("IA_ARRANQUE_LAB"), reason="Requiere laboratorio de arranque")
def test_arranque_recuperacion_y_retorno(escenario, monkeypatch):
    from pathlib import Path
    from time import monotonic, sleep

    from app.core.config import get_settings

    ids, headers, _ = escenario
    app.dependency_overrides.pop(obtener_motor)
    settings = get_settings()
    monkeypatch.setattr(settings, "ia_motor", "http")
    monkeypatch.setattr(settings, "ia_url", os.environ["IA_HTTP_TEST_URL"])
    route = f"/ia/predecir/{ids[0]}"
    with TestClient(app) as active:
        assert active.get("/health").status_code == 200
        unavailable = active.post(route, headers=headers)
        assert unavailable.status_code == 503, unavailable.text
        assert unavailable.json()["error"]["codigo"] == "MOTOR_IA_NO_DISPONIBLE"
        Path("/results/backend-sin-ia.ok").touch()
        deadline = monotonic() + 90
        while not Path("/results/ia-lista.ok").exists():
            assert monotonic() < deadline, "IA no se inicio dentro del plazo"
            sleep(0.25)
        recovered = active.post(route, headers=headers)
        assert recovered.status_code == 200, recovered.text

    monkeypatch.setattr(settings, "ia_motor", "integrado")
    with TestClient(app) as rollback:
        assert isinstance(app.state.motor_ia, MotorIntegrado)
        response = rollback.post(f"/citas/{ids[1]}/prediccion", headers=headers)
        assert response.status_code == 200, response.text


@pytest.mark.parametrize("path", ["/ia/predecir/{id}", "/citas/{id}/prediccion", "/ia/predecir-lote?forzar=true"])
def test_fallo_no_borra_predicciones_previas(client, db, escenario, path):
    ids, h, motor = escenario
    assert client.post("/ia/predecir-lote", headers=h).status_code == 200
    before = [(p.id_prediccion, p.probabilidad_no_show) for p in db.scalars(select(PrediccionIA))]
    events = db.scalar(select(func.count(AuditoriaEvento.id_log)))
    motor.error = MotorIANoDisponible("Fallo simulado")
    r = client.post(path.format(id=ids[0]), headers=h)
    assert r.status_code == 503, r.text
    assert before == [(p.id_prediccion, p.probabilidad_no_show) for p in db.scalars(select(PrediccionIA))]
    assert events == db.scalar(select(func.count(AuditoriaEvento.id_log)))


def test_lote_incompleto_no_persiste(client, db, escenario, monkeypatch):
    _, h, motor = escenario
    monkeypatch.setattr(motor, "predecir_lote", lambda *a, **k: [])
    assert client.post("/ia/predecir-lote", headers=h).status_code == 503
    assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == 0


def test_lote_version_incompatible_no_persiste(client, db, escenario, monkeypatch):
    _, h, motor = escenario
    original = motor.predecir_lote
    def changed(*a, **k):
        results = original(*a, **k)
        results[-1] = results[-1].model_copy(update={"version_modelo": "otra"})
        return results
    monkeypatch.setattr(motor, "predecir_lote", changed)
    assert client.post("/ia/predecir-lote", headers=h).status_code == 409
    assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == 0


def test_cita_cambiada_durante_inferencia_no_persiste(client, db, escenario):
    ids, h, motor = escenario
    def cambiar():
        cita = db.get(Cita, ids[0])
        cita.reprogramaciones_prev += 1
        db.flush()
    motor.cambio = cambiar
    r = client.post(f"/ia/predecir/{ids[0]}", headers=h)
    assert r.status_code == 409, r.text
    assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == 0


def test_auditoria_fallida_revierte_lote_tras_flush(client, db, escenario, monkeypatch):
    _, h, _ = escenario
    def fail(*a, **k):
        assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == 2
        raise RuntimeError("Auditoría interrumpida")
    monkeypatch.setattr(service, "registrar_evento", fail)
    with pytest.raises(RuntimeError):
        client.post("/ia/predecir-lote", headers=h)
    assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == 0


def test_metadata_fuera_transaccion(client, escenario):
    _, h, _ = escenario
    assert client.get("/ia/metricas", headers=h).status_code == 200
    response = client.get("/ia/dataset-resumen", headers=h)
    assert response.status_code == 200, response.text
    assert len(response.json()["features_autorizadas"]) == 11


def test_sin_autenticar_no_llama_motor(client, escenario):
    ids, _, motor = escenario
    assert client.post(f"/ia/predecir/{ids[0]}").status_code == 401
    assert motor.calls == 0


def test_lifecycle_no_contacta_ia_y_cierra(monkeypatch):
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "ia_motor", "http")
    monkeypatch.setattr(settings, "ia_url", "http://127.0.0.1:1")
    monkeypatch.setattr(settings, "ia_api_key", "clave-solo-laboratorio")
    with TestClient(app) as client:
        motor = app.state.motor_ia
        assert isinstance(motor, MotorHTTP)
        assert client.get("/health").status_code == 200
    assert motor._client.is_closed
    assert not hasattr(app.state, "motor_ia")


def test_factory_default_y_configuracion_invalida():
    from app.core.config import get_settings
    settings = get_settings()
    assert isinstance(crear_motor(settings), MotorIntegrado)
    invalid = settings.model_copy(update={"ia_motor": "http", "ia_api_key": None})
    with pytest.raises(ValueError):
        crear_motor(invalid)


def test_http_real_con_persistencia_y_metadata(client, db, escenario):
    url = os.environ.get("IA_HTTP_TEST_URL")
    assert url, "Este test requiere IA real del laboratorio 7B"
    ids, h, _ = escenario
    with MotorHTTP(url, os.environ["IA_API_KEY"]) as motor:
        app.dependency_overrides[obtener_motor] = lambda: motor
        assert motor.metricas() == MotorIntegrado().metricas()
        assert motor.dataset() == MotorIntegrado().dataset()
        solicitudes = []
        motor._client.event_hooks["request"].append(solicitudes.append)
        for route in (f"/ia/predecir/{ids[0]}", f"/citas/{ids[1]}/prediccion"):
            solicitudes.clear()
            r = client.post(route, headers=h)
            assert r.status_code == 200, r.text
            assert solicitudes
            assert len(r.headers["X-Request-ID"]) == 32
            assert all(p.headers["X-Request-ID"] == r.headers["X-Request-ID"] for p in solicitudes)
            assert all("authorization" not in p.headers for p in solicitudes)
        r = client.post("/ia/predecir-lote?forzar=true", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["evaluadas"] == 2
        assert client.get("/ia/metricas", headers=h).status_code == 200
        assert client.get("/ia/dataset-resumen", headers=h).status_code == 200
    assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == 2


@pytest.mark.skipif(not os.getenv("IA_LOTE_LAB"), reason="Requiere laboratorio de carga")
def test_medir_lote_publico(client, db, usuarios):
    import json
    from pathlib import Path
    from time import monotonic

    headers = cabecera(client, usuarios["RECEPCION"])
    previous = 0
    measurements = []
    with MotorHTTP(os.environ["IA_HTTP_TEST_URL"], os.environ["IA_API_KEY"]) as motor:
        app.dependency_overrides[obtener_motor] = lambda: motor
        for size in (100, 250, 500, 500, 500):
            rows = []
            for index in range(previous, size):
                sample = CITAS_PRUEBA_IA[index % len(CITAS_PRUEBA_IA)]
                rows.append(sample | {"id_cita_externa": f"LOTE-7-{index}", "paciente_anon_id": f"PAC-L7-{index}"})
            importar_citas(db, rows, id_usuario=usuarios["ADMINISTRADOR"].id_usuario,
                           ip="127.0.0.1", origen="7-lote")
            start = monotonic()
            response = client.post("/ia/predecir-lote?forzar=true", headers=headers)
            elapsed = monotonic() - start
            assert response.status_code == 200, response.text
            assert response.json()["evaluadas"] == size
            assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == size
            measurements.append({"citas": size, "segundos": round(elapsed, 3)})
            previous = size
        importar_citas(db, [CITAS_PRUEBA_IA[0] | {"id_cita_externa": "LOTE-7-500", "paciente_anon_id": "PAC-L7-500"}],
                       id_usuario=usuarios["ADMINISTRADOR"].id_usuario, ip="127.0.0.1", origen="7-lote")
        paths = []
        motor._client.event_hooks["request"].append(lambda request: paths.append(request.url.path))
        response = client.post("/ia/predecir-lote?forzar=true", headers=headers)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["codigo"] == "LOTE_IA_DEMASIADO_GRANDE"
        assert paths == ["/v1/model"]
        assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == 500
    Path("/results/lote.json").write_text(json.dumps(measurements), encoding="utf-8")


def test_paridad_rutas_y_auditoria_entre_motores():
    from sqlalchemy.orm import Session

    from app.core.database import engine, get_db
    from app.core.security import hash_password
    from app.modules.ia.schemas import PrediccionIAOut
    from app.modules.usuarios.models import Usuario

    def normalizar(prediccion):
        normalized = {key: value for key, value in prediccion.items()
                      if key not in {"id_cita", "id_prediccion", "fecha_hora_inferencia"}}
        for key in ("probabilidad_no_show", "umbral_aplicado"):
            normalized[key] = Decimal(normalized[key])
        return normalized

    def ejecutar(motor):
        with engine.connect() as connection, connection.begin() as outer:
            with Session(bind=connection, join_transaction_mode="create_savepoint",
                         autoflush=False, expire_on_commit=False) as db:
                user = Usuario(nombre_completo="Paridad", correo_institucional="paridad@predicitas.crp",
                               password_hash=hash_password("ClaveDePrueba123"), rol="ADMINISTRADOR", activo=True)
                db.add(user)
                db.flush()
                rows = CITAS_PRUEBA_IA + [CITAS_PRUEBA_IA[0] | {"id_cita_externa": "PARIDAD-LOTE-003"}]
                importar_citas(db, rows, id_usuario=user.id_usuario, ip="127.0.0.1", origen="paridad")
                ids = list(db.scalars(select(Cita.id_cita).order_by(Cita.id_cita)))
                app.dependency_overrides.update({get_db: lambda: db, obtener_motor: lambda: motor})
                try:
                    client = TestClient(app)
                    headers = cabecera(client, user)

                    def call(method, path):
                        response = client.request(method, path, headers=headers)
                        assert response.status_code == 200, response.text
                        return response.json()

                    single = normalizar(call("POST", f"/ia/predecir/{ids[0]}"))
                    alias = normalizar(call("POST", f"/citas/{ids[1]}/prediccion"))
                    batches = []
                    for suffix, count in (("", 1), ("", 0), ("?forzar=true", 3)):
                        result = call("POST", "/ia/predecir-lote" + suffix)
                        assert result["evaluadas"] == count
                        result["predicciones"] = [normalizar(row) for row in result["predicciones"]]
                        batches.append(result)
                    persisted = [normalizar(PrediccionIAOut.model_validate(row).model_dump(mode="json"))
                                 for row in db.scalars(select(PrediccionIA).order_by(PrediccionIA.id_cita))]
                    assert len(persisted) == 3
                    audits = []
                    for event in db.scalars(select(AuditoriaEvento).where(
                            AuditoriaEvento.modulo == "IA").order_by(AuditoriaEvento.id_log)):
                        after = dict(event.datos_after)
                        after.pop("id_cita", None)
                        audits.append((event.accion, event.entidad_afectada, event.datos_before, after))
                    assert len(audits) == 5
                    return (single, alias, batches, persisted, audits,
                            call("GET", "/ia/metricas"), call("GET", "/ia/dataset-resumen"))
                finally:
                    app.dependency_overrides.pop(get_db, None)
                    app.dependency_overrides.pop(obtener_motor, None)
                    db.close()
                    outer.rollback()

    with MotorHTTP(os.environ["IA_HTTP_TEST_URL"], os.environ["IA_API_KEY"]) as remote:
        assert ejecutar(MotorIntegrado()) == ejecutar(remote)


def test_fallo_segundo_fragmento_no_persiste(client, db, usuarios):
    import httpx

    rows = [CITAS_PRUEBA_IA[0] | {"id_cita_externa": f"FALLO-L7-{i}", "paciente_anon_id": f"PAC-F7-{i}"}
            for i in range(101)]
    importar_citas(db, rows, id_usuario=usuarios["ADMINISTRADOR"].id_usuario,
                   ip="127.0.0.1", origen="lote-fallo")
    headers = cabecera(client, usuarios["RECEPCION"])
    audit_before = db.scalar(select(func.count(AuditoriaEvento.id_log)))
    fragments = []

    def fail_second(request):
        if request.url.path == "/v1/predict-batch":
            fragments.append(request)
            if len(fragments) == 2:
                raise httpx.ReadTimeout("Fallo simulado")

    with MotorHTTP(os.environ["IA_HTTP_TEST_URL"], os.environ["IA_API_KEY"]) as motor:
        motor._client.event_hooks["request"].append(fail_second)
        app.dependency_overrides[obtener_motor] = lambda: motor
        response = client.post("/ia/predecir-lote", headers=headers)
    assert len(fragments) == 2
    assert response.status_code == 503, response.text
    assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == 0
    assert db.scalar(select(func.count(AuditoriaEvento.id_log))) == audit_before
