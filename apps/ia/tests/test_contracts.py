"""Validación real contra contratos congelados, no solo nombres de rutas."""
import json
from decimal import Decimal
from pathlib import Path
import uuid

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from app.main import app
from tests.test_correccion import payload

ROOT = Path("/contracts")


def validator(relative, fragment=""):
    assert {"uuid", "date", "date-time"} <= set(FormatChecker.checkers)
    registry = Registry()
    for path in ROOT.rglob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8-sig"), parse_float=Decimal)
        if not isinstance(value, dict):
            continue
        resource = Resource.from_contents(value, default_specification=DRAFT202012)
        registry = registry.with_resource("https://predicitas.invalid/contracts/" + path.relative_to(ROOT).as_posix(), resource)
        registry = registry.with_resource(path.as_uri(), resource)
        if "$id" in value:
            registry = registry.with_resource(value["$id"], resource)
    return Draft202012Validator({"$ref": (ROOT / relative).as_uri() + fragment}, registry=registry, format_checker=FormatChecker())


def test_requests_responses_against_frozen_schemas(client, auth_headers, sample_features):
    data = payload(sample_features)
    validator("ia/predict-request.v1.schema.json").validate(data)
    result = client.post("/v1/predict", json=data, headers=auth_headers)
    assert result.status_code == 200
    validator("ia/predict-response.v1.schema.json").validate(json.loads(result.text, parse_float=Decimal))
    data.pop("features")
    data["items"] = [{"id_item": "one", "features": sample_features}]
    validator("ia/batch-request.v1.schema.json").validate(data)
    result = client.post("/v1/predict-batch", json=data, headers=auth_headers)
    assert result.status_code == 200
    validator("ia/batch-response.v1.schema.json").validate(json.loads(result.text, parse_float=Decimal))
    for route, relative, fragment in [
        ("model", "ia/openapi.objetivo.v1.json", "#/components/schemas/ModelMetadata"),
        ("metrics", "backend/openapi.actual.v0.5.0.json", "#/components/schemas/MetricasModeloOut"),
        ("dataset", "data/dataset-manifest.v1.schema.json", ""),
    ]:
        response = client.get("/v1/" + route, headers=auth_headers)
        assert response.status_code == 200
        validator(relative, fragment).validate(json.loads(response.text, parse_float=Decimal))
    validator("ia/error.v1.schema.json").validate(client.get("/v1/model").json())


def test_openapi_security_inputs_outputs_and_errors():
    actual = app.openapi()
    expected = json.loads((ROOT / "ia/openapi.objetivo.v1.json").read_text(encoding="utf-8"))
    assert set(actual["paths"]) == set(expected["paths"])
    assert actual["components"]["securitySchemes"]["IAApiKey"] == expected["components"]["securitySchemes"]["IAApiKey"]
    for path, methods in expected["paths"].items():
        for method, spec in methods.items():
            live = actual["paths"][path][method]
            assert set(spec["responses"]) <= set(live["responses"])
            assert live.get("security", []) == ([] if path.startswith("/health") else [{"IAApiKey": []}])
            for status in spec["responses"]:
                assert "$ref" in live["responses"][status]["content"]["application/json"]["schema"]
    for name in ("PredictRequest", "BatchRequest"):
        schema = actual["components"]["schemas"][name]
        assert {"version_contrato", "version_features", "version_modelo", "id_solicitud"} <= set(schema["required"])
        assert schema["additionalProperties"] is False


def test_service_has_no_operational_imports():
    import ast
    for path in Path("/app/app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            names = []
            if isinstance(node, ast.Import):
                names = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any(n.startswith(("sqlalchemy", "psycopg", "alembic", "app.modules")) for n in names), path
