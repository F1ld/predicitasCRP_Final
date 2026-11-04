"""Validacion offline de schemas, fixtures e invariantes de fase 1.

Requiere jsonschema[format]==4.25.1 en entorno de herramientas, no en apps.
No abre sockets, importa aplicaciones, consulta BD ni carga modelos Joblib.
"""
import argparse
from datetime import datetime
from decimal import Decimal
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
from urllib.parse import unquote, urldefrag
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "contracts"
LIMA = ZoneInfo("America/Lima")
FORBIDDEN = {"estado_actual", "fecha_hora_cita", "fecha_registro_cita", "id_cita", "id_cita_externa", "medico", "paciente_anon_id", "target_no_show"}


def load(path):
    def invalid_constant(value):
        raise ValueError(f"Constante no permitida en JSON estricto: {value}")
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_float=Decimal, parse_constant=invalid_constant)


def require(condition, reason):
    if not condition: raise ValueError(reason)


def as_lima(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LIMA)


def semantic(schema, data, context, now):
    if schema.endswith("cita-import-normalizada.v1.schema.json"):
        cita, registro = as_lima(data["fecha_hora_cita"]), as_lima(data["fecha_registro_cita"])
        # Compatibilidad actual: codigo compara fechas calendario, no hora intradia.
        require(registro.date() <= cita.date(), "registro posterior a fecha de cita")
        require(cita.weekday() != 6, "domingo fuera del piloto")
        if data.get("estado_actual", "RECIBIDA") in ("ATENDIDA", "NO_SHOW"):
            require(cita.date() <= now.date(), "desenlace futuro")
    if schema.endswith("training-row.v1.schema.json"):
        cita, registro = as_lima(data["fecha_hora_cita"]), as_lima(data["fecha_registro_cita"])
        require(registro <= cita <= now, "orden temporal entrenamiento")
        require(cita.weekday() != 6, "domingo entrenamiento")
        f = data["features"]
        require(f["antelacion_dias"] == (cita.date() - registro.date()).days, "antelacion no corresponde a fechas")
        require(f["franja_horaria"] == ("MANANA" if cita.hour < 13 else "TARDE"), "franja no corresponde")
        require(f["dia_semana"] == ("LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO")[cita.weekday()], "dia no corresponde")
        if f["tipo_paciente"] == "NUEVO": require(f["inasistencias_previas"] == f["asistencias_previas"] == 0, "historico sintetico NUEVO incoherente")
    if schema.endswith("predict-response.v1.schema.json"):
        f = data["features_snapshot"]
        require(f["tasa_no_show_previa"] == Decimal(str(round(f["inasistencias_previas"] / (f["asistencias_previas"] + f["inasistencias_previas"] + 1.0), 4))), "formula de tasa previa no coincide")
        require(f["es_reserva_lejana"] == int(f["antelacion_dias"] >= 15), "reserva lejana no coincide")
        if context:
            for key in ("version_contrato", "id_solicitud", "version_modelo", "version_features"):
                require(data[key] == context[key], f"respuesta no corresponde: {key}")
            for key, value in context["features"].items(): require(f[key] == value, f"snapshot modificado: {key}")
    if schema.endswith("batch-request.v1.schema.json"):
        ids = [item["id_item"] for item in data["items"]]
        require(len(ids) == len(set(ids)), "IDs repetidos en lote")
    if schema.endswith("batch-response.v1.schema.json"):
        ids = [item["id_item"] for item in data["items"]]
        require(len(ids) == len(set(ids)), "IDs repetidos en resultado")
        if context:
            require(data["id_solicitud"] == context["id_solicitud"] and data["version_modelo"] == context["version_modelo"], "lote de otra solicitud/version")
            by_id = {item["id_item"]: item for item in context["items"]}
            require(set(ids) == set(by_id), "lote incompleto o con IDs extra")
            for item in data["items"]:
                single = {key: value for key, value in context.items() if key != "items"}
                single["features"] = by_id[item["id_item"]]["features"]
                semantic("predict-response.v1.schema.json", item["resultado"], single, now)
    if schema.endswith("dataset-manifest.v1.schema.json"):
        total = data["total_historicas"]
        require(sum(data["distribucion"].values()) == total, "clases no suman total")
        splits = data["particiones"]
        require(sum(split["filas"] for split in splits.values()) == total, "particiones no suman total")
        temp = math.ceil(total * 0.3)
        expected = {"train": total - temp, "val": temp // 2, "test": temp - temp // 2}
        require(all(splits[name]["filas"] == count for name, count in expected.items()), "split no reproduce 70/15/15 de sklearn")
        require(all(split["no_show"] <= split["filas"] for split in splits.values()), "clase de split excede filas")
        require(sum(split["no_show"] for split in splits.values()) == data["distribucion"]["no_show"], "no-show de splits incoherente")
        require(set(data["control_leakage"]["columnas_prohibidas_excluidas"]) == FORBIDDEN, "lista anti-leakage incompleta")


def validate_refs(path, document):
    count = 0
    def walk(value):
        nonlocal count
        if isinstance(value, dict):
            if "$ref" in value:
                ref = value["$ref"]
                location, fragment = urldefrag(ref)
                require("://" not in location, "referencia remota no permitida en contratos offline")
                target_path = (path.parent / location).resolve() if location else path
                require(target_path.is_relative_to(CONTRACTS), "referencia fuera de contracts")
                target = load(target_path) if location else document
                if fragment:
                    require(fragment.startswith("/"), "solo JSON Pointer en refs de estos contratos")
                    for part in fragment[1:].split("/"):
                        target = target[unquote(part).replace("~1", "/").replace("~0", "~")]
                count += 1
            for item in value.values(): walk(item)
        elif isinstance(value, list):
            for item in value: walk(item)
    walk(document)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/migracion/fase-01/validacion_contratos.json")
    args = parser.parse_args()
    registry = Registry()
    schemas = {}
    refs = 0
    for path in sorted(CONTRACTS.rglob("*.schema.json")):
        document = load(path)
        Draft202012Validator.check_schema(document)
        refs += validate_refs(path, document)
        registry = registry.with_resource(document["$id"], Resource.from_contents(document))
        schemas[path.relative_to(CONTRACTS).as_posix()] = document
    fixture = load(CONTRACTS / "examples/casos.json")
    now = as_lima(fixture["reference_now"])
    results = []
    for case in fixture["cases"]:
        validator = Draft202012Validator(schemas[case["schema"]], registry=registry, format_checker=FormatChecker())
        errors = list(validator.iter_errors(case["data"]))
        valid = not errors
        require(valid == case["schema_valid"], f"fixture {case['id']} tiene resultado estructural inesperado: {[e.message for e in errors]}")
        semantic_ok, reason = None, None
        if valid:
            try:
                semantic(case["schema"], case["data"], case.get("context"), now)
                semantic_ok = True
            except ValueError as exc:
                semantic_ok, reason = False, str(exc)
            require(semantic_ok == case["semantic_valid"], f"fixture {case['id']} tiene resultado semantico inesperado: {reason}")
        results.append({"id": case["id"], "schema_valid": valid, "semantic_valid": semantic_ok, "expected_result_met": True, "semantic_reason": reason})
    apis = []
    for path in (CONTRACTS / "backend/openapi.actual.v0.5.0.json", CONTRACTS / "ia/openapi.objetivo.v1.json"):
        document = load(path)
        refs += validate_refs(path, document)
        operations = [operation for value in document["paths"].values() for method, operation in value.items() if method in {"get", "post", "put", "patch", "delete", "head", "options"}]
        ids = [operation["operationId"] for operation in operations]
        require(len(ids) == len(set(ids)), "operationId duplicado")
        require(all(operation.get("responses") for operation in operations), "operacion sin respuestas")
        apis.append({"path": path.relative_to(CONTRACTS).as_posix(), "operations": len(operations), "references_resolved_locally": True, "scope": "integridad de estructura/refs/operationId, no validacion formal completa de OpenAPI ni prueba HTTP"})
    original = ROOT / "docs/migracion/fase-00/openapi_baseline.json"
    copied = CONTRACTS / "backend/openapi.actual.v0.5.0.json"
    require(original.read_bytes() == copied.read_bytes(), "snapshot publico cambiado")
    summary = {"validator": f"jsonschema {importlib.metadata.version('jsonschema')}", "schema_count": len(schemas), "local_references_checked": refs, "fixture_count": len(results), "all_expected_results_met": True, "openapi_public_snapshot_sha256": hashlib.sha256(copied.read_bytes()).hexdigest(), "openapi_documents": apis, "results": results, "limits": "Fixtures de contrato; no prueba servicios no implementados, hashes de archivos ficticios, dataset real, rendimiento, RBAC ni toda la suite funcional."}
    with args.output.open("x", encoding="utf-8") as stream: json.dump(summary, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: summary[key] for key in ("schema_count", "local_references_checked", "fixture_count", "all_expected_results_met")}, ensure_ascii=False))


if __name__ == "__main__": main()
