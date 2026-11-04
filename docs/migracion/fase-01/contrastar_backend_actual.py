"""Ejecutar en imagen baseline con codigo/contratos RO y network=none.

Contrasta OpenAPI y validadores puros actuales, sin HTTP, persistencia o inferencia.
"""
import ast
import csv
from datetime import datetime
import inspect
import json
from pathlib import Path

from app.main import app
from app.modules.citas.importer import validar_fila


def main():
    contract = Path("/contracts")
    baseline = json.loads((contract / "backend/openapi.actual.v0.5.0.json").read_text(encoding="utf-8"))
    current = app.openapi()
    if current != baseline:
        raise SystemExit("OpenAPI actual difiere de baseline; revisar antes de continuar.")
    fixtures = json.loads((contract / "examples/casos.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(fixtures["reference_now"])
    rows = []
    for case in fixtures["cases"]:
        if case["schema"] != "data/cita-import-normalizada.v1.schema.json": continue
        expected = case["schema_valid"] and case["semantic_valid"]
        try:
            row, derived = validar_fila(case["data"], now)
            valid = True
        except ValueError:
            valid = False
        if expected != valid: raise SystemExit(f"Diferencia con backend actual: {case['id']}")
        rows.append({"case": case["id"], "accepted_by_current_pure_validator": valid, "matches_contract_expectation": True})
    csv_results = []
    for name, expected in (("importacion_valida.csv", (2, 0)), ("importacion_mixta.csv", (1, 3))):
        accepted, rejected, seen = 0, 0, set()
        with (contract / "examples" / name).open(encoding="utf-8-sig", newline="") as stream:
            for raw in csv.DictReader(stream):
                raw = {key: value for key, value in raw.items() if key and value not in (None, "")}
                try:
                    row, _ = validar_fila(raw, now)
                    if row.id_cita_externa in seen: raise ValueError("duplicado dentro del fixture")
                    seen.add(row.id_cita_externa)
                    accepted += 1
                except ValueError: rejected += 1
        if (accepted, rejected) != expected: raise SystemExit(f"CSV inesperado: {name}")
        csv_results.append({"file": name, "accepted": accepted, "rejected": rejected, "scope": "validacion pura y duplicados locales; sin BD ni persistencia"})
    # El paquete reportes exporta un router; cargar modulo explicito para inspeccion.
    import importlib
    reportes = importlib.import_module("app.modules.reportes.router")
    tree = ast.parse(Path("app/modules/reportes/router.py").read_text(encoding="utf-8-sig"))
    alias_results = []
    for function in tree.body:
        if not isinstance(function, ast.FunctionDef) or not function.name.startswith("alias_reporte_"): continue
        call = next(item.value for item in function.body if isinstance(item, ast.Return))
        target = getattr(reportes, call.func.id)
        kwargs = {item.arg: object() for item in call.keywords}
        try:
            inspect.signature(target).bind(**kwargs)
            compatible, reason = True, None
        except TypeError as exc:
            compatible, reason = False, str(exc)
        alias_results.append({"alias": function.name, "target": call.func.id, "signature_compatible": compatible, "reason": reason, "endpoint_executed": False})
    result = {"openapi_matches_current_app": True, "public_operations": sum(method in {"get", "post", "put", "patch", "delete", "head", "options"} for value in baseline["paths"].values() for method in value), "normalized_import_cases": rows, "csv_fixtures": csv_results, "report_alias_signature_checks": alias_results, "network_disabled": True, "database_queries_performed": False, "runtime_modified": False, "scope": "No acredita RBAC HTTP, estado/persistencia, reportes ejecutados ni una suite funcional nueva."}
    with Path("/evidence/validacion_contra_backend_actual.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
