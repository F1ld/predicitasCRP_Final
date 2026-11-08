"""Pruebas sin BD ni conftest backend: python -B .../test_motor_7a.py."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

backend = os.environ.get("BACKEND_SOURCE_DIR")
sys.path.insert(0, backend or str(Path(__file__).resolve().parents[3] / "apps/backend"))

import httpx
from pydantic import ValidationError

from app.core.errores import Conflicto, MotorIANoDisponible
from app.modules.ia.motor_http import MotorHTTP, ROTULO
from app.modules.ia.puerto import FeaturesMotor, MotorPredictivo, ResultadoMotor
from decimal import Decimal

FEATURES = dict(especialidad="CARDIOLOGIA", tipo_paciente="NUEVO", canal_origen="WEB",
    franja_horaria="MANANA", dia_semana="LUNES", antelacion_dias=1,
    inasistencias_previas=0, asistencias_previas=0, reprogramaciones_prev=0)
F = FeaturesMotor(**FEATURES)


def prediction(payload, features=F):
    return dict(version_contrato="1.0", id_solicitud=payload["id_solicitud"],
        version_modelo=payload["version_modelo"], version_features="pre-cita-v1",
        probabilidad_no_show=0.285, nivel_riesgo="BAJO", umbrales={"medio": 0.3, "alto": 0.45},
        features_snapshot=features.snapshot(), explicabilidad_resumen="Factores clave [Simulado]",
        es_simulacion=True, rotulo_etico=ROTULO)


def metadata():
    return dict(version_contrato="1.0", version_modelo="v1", version_features="pre-cita-v1",
        version_dataset="ds1", umbrales={"medio": 0.3, "alto": 0.45},
        features_autorizadas=list(FEATURES), es_simulacion=True, rotulo_etico=ROTULO)


class MotorTests(unittest.TestCase):
    def motor(self, handler, **kwargs):
        motor = MotorHTTP("http://ia.test", "clave-solo-test", transport=httpx.MockTransport(handler), **kwargs)
        self.addCleanup(motor.close)
        return motor

    def test_version(self):
        self.assertEqual(self.motor(lambda r: httpx.Response(200, json=metadata())).version(), "v1")

    def test_individual_y_sin_jwt(self):
        def handler(request):
            self.assertEqual(request.headers["X-IA-API-Key"], "clave-solo-test")
            self.assertNotIn("authorization", request.headers)
            self.assertNotIn("cookie", request.headers)
            self.assertEqual(request.url.path, "/v1/predict")
            payload = json.loads(request.content)
            self.assertEqual(payload["features"], FEATURES)
            self.assertEqual(set(payload), {"version_contrato", "version_features", "version_modelo", "id_solicitud", "features"})
            return httpx.Response(200, json=prediction(payload))
        result = self.motor(handler).predecir(F, version="v1")
        self.assertEqual(str(result.probabilidad_no_show), "0.285")
        self.assertEqual(result.features_snapshot, F.snapshot())

    def test_lote_fragmentado_y_reordenado(self):
        sizes = []
        def handler(request):
            payload = json.loads(request.content)
            sizes.append(len(payload["items"]))
            return httpx.Response(200, json=dict(version_contrato="1.0", id_solicitud=payload["id_solicitud"],
                version_modelo="v1", items=[{"id_item": item["id_item"], "resultado": prediction(payload,
                    FeaturesMotor(**item["features"]))} for item in reversed(payload["items"])]))
        features = [FeaturesMotor(**(FEATURES | {"antelacion_dias": i})) for i in range(201)]
        results = self.motor(handler).predecir_lote(features, version="v1")
        self.assertEqual(sizes, [100, 100, 1])
        self.assertEqual([r.features_snapshot["antelacion_dias"] for r in results], list(range(201)))

    def test_lote_vacio_no_http(self):
        self.assertEqual(self.motor(lambda r: self.fail("HTTP inesperado")).predecir_lote([], version="v1"), [])

    def test_estados_remotos_sin_filtrar_secretos(self):
        for status in (301, 401, 403, 422, 500, 503):
            with self.subTest(status=status):
                motor = self.motor(lambda r: httpx.Response(status, text="secreto remoto", headers={"location": "http://otro"}))
                with self.assertRaises(MotorIANoDisponible) as raised:
                    motor.predecir(F, version="v1")
                self.assertNotIn("secreto", str(raised.exception))

    def test_caida_y_timeouts_sin_reintento(self):
        for error in (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout, httpx.PoolTimeout):
            calls = []
            def handler(request):
                calls.append(request)
                raise error("clave secreta")
            with self.subTest(error=error):
                with self.assertRaises(MotorIANoDisponible):
                    self.motor(handler).predecir(F, version="v1")
                self.assertEqual(len(calls), 1)

    def test_timeouts_explicitos(self):
        def handler(request):
            self.assertEqual(request.extensions["timeout"], dict(connect=1.0, read=3.0, write=2.0, pool=0.5))
            return httpx.Response(200, json=prediction(json.loads(request.content)))
        self.motor(handler, connect=1, read=3, write=2, pool=0.5).predecir(F, version="v1")

    def test_respuesta_malformada(self):
        for content, headers in ((b"no-json", {"content-type": "application/json"}),
                (b"{}", {"content-type": "text/html"}), (b"x" * (2 * 1024 * 1024 + 1), {"content-type": "application/json"})):
            with self.subTest(size=len(content)):
                with self.assertRaises(MotorIANoDisponible):
                    self.motor(lambda r: httpx.Response(200, content=content, headers=headers)).predecir(F, version="v1")

    def test_invariantes_respuesta(self):
        mutations = [lambda p: p.update(id_solicitud=str(uuid4())),
            lambda p: p.update(probabilidad_no_show=0.12345), lambda p: p.update(probabilidad_no_show=float("nan")),
            lambda p: p.update(probabilidad_no_show=1.1), lambda p: p.update(probabilidad_no_show="0.285"),
            lambda p: p.update(nivel_riesgo="ALTO"), lambda p: p.update(extra="no"),
            lambda p: p.pop("es_simulacion"), lambda p: p.update(es_simulacion=False),
            lambda p: p.update(es_simulacion=1),
            lambda p: p["features_snapshot"].update(asistencias_previas=8),
            lambda p: p["features_snapshot"].update(asistencias_previas=False),
            lambda p: p["features_snapshot"].update(extra=1),
            lambda p: p["umbrales"].update(alto=0.5), lambda p: p.update(version_features="otra")]
        for index, mutate in enumerate(mutations):
            def handler(request):
                payload = prediction(json.loads(request.content))
                mutate(payload)
                return httpx.Response(200, content=json.dumps(payload).encode(), headers={"content-type": "application/json"})
            with self.subTest(mutation=index):
                with self.assertRaises(MotorIANoDisponible):
                    self.motor(handler).predecir(F, version="v1")

    def test_limites_riesgo(self):
        for prob, level in ((0.0, "BAJO"), (0.299, "BAJO"), (0.3, "MEDIO"), (0.45, "MEDIO"), (0.451, "ALTO"), (1.0, "ALTO")):
            def handler(request):
                p = prediction(json.loads(request.content)) | {"probabilidad_no_show": prob, "nivel_riesgo": level}
                return httpx.Response(200, json=p)
            with self.subTest(prob=prob):
                self.assertEqual(self.motor(handler).predecir(F, version="v1").nivel_riesgo, level)

    def test_metadata_incompatible(self):
        for mutation in (lambda p: p["features_autorizadas"].__setitem__(0, "id_cita"),
                lambda p: p.update(es_simulacion=1), lambda p: p.update(version_contrato="2.0"),
                lambda p: p.update(umbrales={"medio": 0.2, "alto": 0.5})):
            def handler(request):
                p = metadata()
                mutation(p)
                return httpx.Response(200, json=p)
            with self.subTest(mutation=mutation), self.assertRaises(MotorIANoDisponible):
                self.motor(handler).version()

    def test_version_distinta_y_409(self):
        for status in (200, 409):
            def handler(request):
                return httpx.Response(status, json=prediction(json.loads(request.content)) | {"version_modelo": "v2"})
            with self.subTest(status=status):
                with self.assertRaises(Conflicto):
                    self.motor(handler).predecir(F, version="v1")

    def test_cambio_version_segundo_fragmento_sin_parcial(self):
        calls = []
        def handler(request):
            p = json.loads(request.content)
            calls.append(p)
            if len(calls) == 2:
                return httpx.Response(409)
            return httpx.Response(200, json=dict(version_contrato="1.0", id_solicitud=p["id_solicitud"],
                version_modelo="v1", items=[{"id_item": i["id_item"], "resultado": prediction(p)} for i in p["items"]]))
        with self.assertRaises(Conflicto):
            self.motor(handler).predecir_lote([F] * 201, version="v1")
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(p["version_modelo"] == "v1" for p in calls))

    def test_identidades_lote(self):
        for kind in ("duplicate", "missing", "extra", "request", "version", "nested-version"):
            def handler(request):
                p = json.loads(request.content)
                items = [{"id_item": str(i), "resultado": prediction(p)} for i in range(2)]
                value = dict(version_contrato="1.0", id_solicitud=p["id_solicitud"], version_modelo="v1", items=items)
                if kind == "duplicate": items[1]["id_item"] = "0"
                if kind == "missing": items.pop()
                if kind == "extra": items.append({"id_item": "2", "resultado": prediction(p)})
                if kind == "request": value["id_solicitud"] = str(uuid4())
                if kind == "version": value["version_modelo"] = "v2"
                if kind == "nested-version": items[1]["resultado"]["version_modelo"] = "v2"
                return httpx.Response(200, json=value)
            with self.subTest(kind=kind):
                with self.assertRaises((MotorIANoDisponible, Conflicto)):
                    self.motor(handler).predecir_lote([F, F], version="v1")

    def test_presupuesto_lote(self):
        with patch("app.modules.ia.motor_http.time.monotonic", side_effect=[0, 61]):
            with self.assertRaises(MotorIANoDisponible):
                self.motor(lambda r: self.fail("HTTP fuera del plazo")).predecir_lote([F], version="v1")

    def test_close(self):
        motor = self.motor(lambda r: self.fail("Cliente cerrado"))
        with motor:
            pass
        motor.close()
        with self.assertRaises(MotorIANoDisponible):
            motor.version()

    def test_configuracion_rechazada(self):
        for url in ("ftp://ia", "http://u:p@ia", "http://ia/predict", "http://ia?x=1", "http://ia#f", "/relative"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                MotorHTTP(url, "clave")
        for value in (0, -1, True, float("nan"), float("inf"), "1"):
            with self.subTest(timeout=value), self.assertRaises(ValueError):
                MotorHTTP("http://ia", "clave", read=value)
        for key in ("", " ", "clave\n", "clave con espacio"):
            with self.subTest(key=repr(key)), self.assertRaises(ValueError):
                MotorHTTP("http://ia", key)

    def test_features_estrictas(self):
        for update in ({"extra": "id-personal"}, {"antelacion_dias": True}, {"antelacion_dias": -1}, {"especialidad": "OTRA"}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                FeaturesMotor(**(FEATURES | update))

    def test_doble_puerto(self):
        class Doble:
            def version(self): return "doble"
            def predecir(self, features, *, version):
                return ResultadoMotor(version_modelo=version, probabilidad_no_show=Decimal("0.285"),
                    nivel_riesgo="BAJO", umbral_aplicado=Decimal("0.450"),
                    features_snapshot=features.snapshot(), explicabilidad_resumen="Doble [Simulado]")
            def predecir_lote(self, features, *, version): return [self.predecir(f, version=version) for f in features]
            def close(self): pass
        def consumidor(motor: MotorPredictivo):
            return motor.predecir_lote([F], version=motor.version())
        self.assertEqual(consumidor(Doble())[0].features_snapshot, F.snapshot())


if __name__ == "__main__":
    unittest.main(verbosity=2)
