"""Probe dentro del laboratorio Docker: HTTP TCP, IA real y predictor RO.

Montajes: /backend, /ia, /models RO; /evidence escribible; sin red externa/BD.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

sys.path.insert(0, "/backend")
from app.core.errores import Conflicto, MotorIANoDisponible
from app.modules.ia.motor_http import MotorHTTP
from app.modules.ia.motor_integrado import MotorIntegrado
from app.modules.ia.puerto import FeaturesMotor

import httpx

KEY = os.environ["IA_API_KEY"]
BASE = dict(especialidad="CARDIOLOGIA", tipo_paciente="CONTINUADOR", canal_origen="WEB",
    franja_horaria="MANANA", dia_semana="LUNES", antelacion_dias=1,
    inasistencias_previas=0, asistencias_previas=2, reprogramaciones_prev=0)


def expect_error(error, call):
    try:
        call()
    except error:
        return
    raise AssertionError(f"Faltó excepción {error.__name__}")


def start(port, *, missing=False):
    env = os.environ.copy()
    for key in ("DATABASE_URL", "DATABASE_URL_MIGRACIONES", "SECRET_KEY", "IA_RELEASE_VERSION", "IA_APPROVAL_SHA256"):
        env.pop(key, None)
    env.update(PYTHONPATH="/ia", MODEL_REGISTRY_DIR="/tmp/modelo-ausente" if missing else "/models")
    log = Path(f"/evidence/ia-{port}.log").open("w")
    process = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", str(port)], cwd="/ia", env=env, stdout=log, stderr=log)
    try:
        with httpx.Client(timeout=1, trust_env=False) as client:
            for _ in range(180):
                if process.poll() is not None:
                    raise AssertionError("IA terminó; revisar log privado del laboratorio")
                try:
                    if client.get(f"http://127.0.0.1:{port}/health/live").status_code == 200:
                        return process, log
                except httpx.HTTPError:
                    pass
                time.sleep(0.2)
        raise AssertionError("IA no arrancó")
    except BaseException:
        process.terminate()
        process.wait(timeout=10)
        log.close()
        raise


class FailingServer(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/v1/predict":
            time.sleep(0.3)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"respuesta":"malformada"}')
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


def main():
    assert not any(k in os.environ for k in ("DATABASE_URL", "DATABASE_URL_MIGRACIONES"))
    model = Path("/models/modelo_predicitas_v1.joblib")
    legacy = Path("/backend/app/modules/ia/artifacts/modelo_predicitas_v1.joblib")
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (model, legacy)}
    processes = []
    server = None
    results = {}
    try:
        processes.append(start(8137))
        processes.append(start(8138, missing=True))
        features = [FeaturesMotor(**(BASE | {"antelacion_dias": i, "inasistencias_previas": i % 4})) for i in range(105)]
        with MotorHTTP("http://127.0.0.1:8137", KEY) as motor:
            version = motor.version()
            results["version"] = version
            first = motor.predecir(features[0], version=version)
            try:
                batch = motor.predecir_lote(features, version=version)
            except MotorIANoDisponible:
                # Diagnóstico de contrato sin publicar clave/headers ni filas.
                with httpx.Client(timeout=20, trust_env=False) as diagnostic:
                    from uuid import uuid4
                    response = diagnostic.post("http://127.0.0.1:8137/v1/predict-batch",
                        headers={"X-IA-API-Key": KEY}, json={"version_contrato": "1.0",
                        "id_solicitud": str(uuid4()), "version_modelo": version,
                        "version_features": "pre-cita-v1", "items": [{"id_item": str(i),
                            "features": f.model_dump()} for i, f in enumerate(features[:100])]})
                    if response.status_code != 200:
                        Path("/evidence/diagnostico.json").write_text(json.dumps(response.json()), encoding="utf-8")
                raise
            # El import legacy exige Settings y crea un Engine sin conectarse.
            # URL inalcanzable + guarda dura: ninguna conexión está permitida.
            from sqlalchemy.engine import Engine
            from unittest.mock import patch
            os.environ["DATABASE_URL"] = "postgresql+psycopg://offline@127.0.0.1:1/7a_no_conectar"
            os.environ["SECRET_KEY"] = "solo-laboratorio-7a-sin-autenticacion-0123456789"
            try:
                with patch.object(Engine, "connect", side_effect=AssertionError("Conexión BD prohibida en 7A")):
                    integrated = MotorIntegrado()
                    assert integrated.version() == version
                    assert first == integrated.predecir(features[0], version=version)
                    assert batch == integrated.predecir_lote(features, version=version)
            finally:
                os.environ.pop("DATABASE_URL", None)
                os.environ.pop("SECRET_KEY", None)
            results.update(individual=1, lote=105, fragmentos=[100, 5], paridad_integrado=True)
            expect_error(Conflicto, lambda: motor.predecir(features[0], version="incompatible"))
        with MotorHTTP("http://127.0.0.1:8137", "clave-invalida-prueba") as motor:
            expect_error(MotorIANoDisponible, motor.version)
        results["clave_invalida"] = True
        with MotorHTTP("http://127.0.0.1:8138", KEY) as motor:
            expect_error(MotorIANoDisponible, motor.version)
            expect_error(MotorIANoDisponible, lambda: motor.predecir(features[0], version=version))
        results["modelo_ausente"] = True
        with MotorHTTP("http://127.0.0.1:8139", KEY, connect=0.1) as motor:
            expect_error(MotorIANoDisponible, motor.version)
        results["ia_caida"] = True
        server = ThreadingHTTPServer(("127.0.0.1", 8140), FailingServer)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with MotorHTTP("http://127.0.0.1:8140", KEY, read=0.05) as motor:
            start_time = time.monotonic()
            expect_error(MotorIANoDisponible, lambda: motor.predecir(features[0], version=version))
            assert time.monotonic() - start_time < 1
            expect_error(MotorIANoDisponible, lambda: motor.predecir_lote(features[:1], version=version))
        results.update(timeout_tcp=True, respuesta_malformada_tcp=True, version_incompatible=True)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        for process, log in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            log.close()
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (model, legacy)}
    results.update(modelos_sin_cambios=True, modelo_sha256=before[str(model)],
                   bd_utilizada=False, transporte="HTTP TCP y uvicorn reales, sin red externa")
    Path("/evidence/http-7a.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()
