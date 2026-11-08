"""HTTP TCP real y worker guardado; registry RO, sin BD ni artefacto legacy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
from jsonschema import Draft202012Validator, FormatChecker, validators
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from soporte_e import tree_hashes
from servidor_guardado_e import install_guard


def _multiple_of(validator, divisor, instance, schema):
    # Los contratos piden 3 decimales; JSON usa binario y 0.285/0.001 no es
    # exactamente entero. Se compara con tolerancia, sin relajar el rango.
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if divisor == 0 or not abs(instance / divisor - round(instance / divisor)) <= 1e-9:
            yield ValidationError(f"{instance!r} no es múltiplo de {divisor!r}")


TOLERANT = validators.extend(Draft202012Validator, {"multipleOf": _multiple_of})


def _strip_schema(value):
    # `$schema` dentro de cada recurso hace que `evolve` reconstruya un validador
    # estándar y pierda la tolerancia de `multipleOf`; se quita solo esa clave.
    if isinstance(value, dict):
        value.pop("$schema", None)
        for item in value.values():
            _strip_schema(item)
    elif isinstance(value, list):
        for item in value:
            _strip_schema(item)
    return value


def validator(relative, fragment=""):
    root = Path("/contracts")
    registry = Registry()
    for path in root.rglob("*.json"):
        value = _strip_schema(json.loads(path.read_text(encoding="utf-8-sig")))
        if isinstance(value, dict):
            resource = Resource.from_contents(value, default_specification=DRAFT202012)
            registry = registry.with_resource(path.as_uri(), resource)
            if "$id" in value:
                registry = registry.with_resource(value["$id"], resource)
    return TOLERANT({"$ref": (root / relative).as_uri() + fragment}, registry=registry,
                    format_checker=FormatChecker())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--no-listo", action="store_true")
    args = parser.parse_args()
    assert not any(k in os.environ for k in ("DATABASE_URL", "DATABASE_URL_MIGRACIONES", "POSTGRES_PASSWORD"))
    assert not list(Path("/app").rglob("*.joblib"))
    install_guard()
    before = tree_hashes(Path("/models"))
    base = {"especialidad": "CARDIOLOGIA", "tipo_paciente": "NUEVO", "canal_origen": "WEB",
            "franja_horaria": "MANANA", "dia_semana": "LUNES", "antelacion_dias": 1,
            "inasistencias_previas": 0, "asistencias_previas": 0, "reprogramaciones_prev": 0}
    cases = []
    for n in range(60):
        cases.append(base | {"tipo_paciente": "CONTINUADOR", "antelacion_dias": n,
            "inasistencias_previas": n % 4, "asistencias_previas": 2, "reprogramaciones_prev": n % 3})
    request = {"version_contrato": "1.0", "version_features": "pre-cita-v1", "version_modelo": args.version,
               "id_solicitud": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
    headers = {"X-IA-API-Key": os.environ["IA_API_KEY"]}
    expected = []
    if not args.no_listo:
        from app.core.model_registry import ModelRegistry
        from app.core.inference import ejecutar_inferencia_individual
        from app.schemas import FeaturesPreCita
        model = ModelRegistry()
        assert model.load_model() and model.version_modelo == args.version
        for features in cases:
            prob, level, snapshot, explanation = ejecutar_inferencia_individual(model.pipeline, FeaturesPreCita(**features))
            expected.append({"probabilidad_no_show": prob, "nivel_riesgo": level,
                "features_snapshot": snapshot.model_dump(mode="json"), "explicabilidad_resumen": explanation})
    server_log = Path("/tmp/servidor-e.log").open("w")
    process = subprocess.Popen([sys.executable, "-B", "/checks/servidor_guardado_e.py"], stdout=server_log, stderr=server_log)
    results = []
    try:
        with httpx.Client(base_url="http://127.0.0.1:8127", timeout=15) as client:
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError("Serving terminó antes de estar vivo")
                try:
                    if client.get("/health/live").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.25)
            else:
                raise RuntimeError("Serving no arrancó")
            ready = client.get("/health/ready")
            assert ready.status_code == (503 if args.no_listo else 200)
            assert client.get("/v1/model").status_code == 401
            if args.no_listo:
                response = client.post("/v1/predict", headers=headers, json=request | {"features": base})
                assert response.status_code == 503
                validator("ia/error.v1.schema.json").validate(response.json())
            else:
                for endpoint, schema, fragment in (
                    ("model", "ia/openapi.objetivo.v1.json", "#/components/schemas/ModelMetadata"),
                    ("metrics", "backend/openapi.actual.v0.5.0.json", "#/components/schemas/MetricasModeloOut"),
                    ("dataset", "data/dataset-manifest.v1.schema.json", "")):
                    response = client.get("/v1/" + endpoint, headers=headers)
                    assert response.status_code == 200
                    validator(schema, fragment).validate(response.json())
                    if endpoint == "model":
                        assert response.json()["version_modelo"] == args.version
                    if endpoint == "dataset":
                        assert response.json()["linaje_completo"] and response.json()["total_historicas"] == 1000
                for n in (0, 20, 59):
                    response = client.post("/v1/predict", headers=headers, json=request | {"features": cases[n]})
                    assert response.status_code == 200
                    value = response.json()
                    validator("ia/predict-response.v1.schema.json").validate(value)
                    assert all(value[key] == expected[n][key] for key in expected[n])
                batch = request | {"items": [{"id_item": f"e-{n}", "features": features} for n, features in enumerate(cases)]}
                response = client.post("/v1/predict-batch", headers=headers, json=batch)
                assert response.status_code == 200
                value = response.json()
                validator("ia/batch-response.v1.schema.json").validate(value)
                assert len(value["items"]) == len(cases)
                for n, item in enumerate(value["items"]):
                    assert item["id_item"] == f"e-{n}"
                    assert item["resultado"]["version_modelo"] == args.version
                    assert all(item["resultado"][key] == expected[n][key] for key in expected[n])
                    results.append({key: item["resultado"][key] for key in expected[n]})
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        server_log.close()
    assert before == tree_hashes(Path("/models"))
    summary = {"version": args.version, "ready": not args.no_listo, "http_tcp": True,
        "worker_guardado": True, "single_cases": 0 if args.no_listo else 3, "batch_cases": len(results),
        "registry_unchanged": True, "legacy_joblib_in_image": False, "no_dsn": True,
        "prediction_digest": hashlib.sha256(json.dumps(results, sort_keys=True, allow_nan=False).encode()).hexdigest()}
    with (Path("/results") / (args.nombre + ".json")).open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, sort_keys=True, indent=2)
    print("Serving E: HTTP/worker, contrato y registry RO aprobados")


if __name__ == "__main__":
    main()
