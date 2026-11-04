"""Inventario reproducible de fase 1: AST/OpenAPI y referencias frontend, sin importar apps.

Ejecutar desde raiz. Solo escribe contratos/evidencias nuevos; no sobrescribe.
Las referencias TS son literales candidatos, no prueba de llamadas HTTP ejecutadas.
"""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/migracion/fase-01"
ROLES = ["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"]
METHODS = {"get", "post", "patch", "put", "delete", "options", "head"}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def resolve(node, values):
    if isinstance(node, ast.Constant): return node.value
    if isinstance(node, ast.Name): return values[node.id]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        result = []
        for item in node.elts:
            if isinstance(item, ast.Starred): result.extend(resolve(item.value, values))
            else: result.append(resolve(item, values))
        return result
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "requiere_roles":
        return resolve(ast.Tuple(elts=node.args), values)
    raise ValueError(ast.unparse(node))


def role_dependencies(function, values):
    roles = None
    for default in [*function.args.defaults, *(item for item in function.args.kw_defaults if item is not None)]:
        if not isinstance(default, ast.Call) or not isinstance(default.func, ast.Name) or default.func.id != "Depends" or not default.args:
            continue
        dependency = default.args[0]
        if isinstance(dependency, ast.Name) and dependency.id == "usuario_actual": roles = ROLES
        elif isinstance(dependency, ast.Name) and dependency.id in values: roles = values[dependency.id]
        elif isinstance(dependency, ast.Call) and isinstance(dependency.func, ast.Name) and dependency.func.id == "requiere_roles": roles = resolve(dependency, values)
    return roles


def main():
    baseline_path = ROOT / "docs/migracion/fase-00/openapi_baseline.json"
    raw = baseline_path.read_bytes()
    spec = json.loads(raw)
    contract_path = ROOT / "contracts/backend/openapi.actual.v0.5.0.json"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    with contract_path.open("xb") as stream: stream.write(raw)
    endpoints = []
    files = [ROOT / "backend-predicitas/app/main.py", *sorted((ROOT / "backend-predicitas/app/modules").glob("*/router.py"))]
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        values = {}
        prefix = ""
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        try: values[target.id] = resolve(node.value, values)
                        except (ValueError, KeyError): pass
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "APIRouter":
                    prefix = next((ast.literal_eval(item.value) for item in node.value.keywords if item.arg == "prefix"), "")
        for function in (n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            for deco in function.decorator_list:
                if not isinstance(deco, ast.Call) or not isinstance(deco.func, ast.Attribute) or deco.func.attr not in METHODS:
                    continue
                if not isinstance(deco.func.value, ast.Name) or deco.func.value.id not in ("router", "app"): continue
                route = prefix + ast.literal_eval(deco.args[0])
                method = deco.func.attr
                operation = spec["paths"][route][method]
                roles = role_dependencies(function, values)
                secured = bool(operation.get("security"))
                if secured != (roles is not None): raise ValueError(f"Revisar roles/security: {method} {route}")
                endpoints.append({"method": method.upper(), "path": route, "module": path.parent.name if path.name == "router.py" else "sistema", "function": function.name, "source": path.relative_to(ROOT).as_posix(), "line": function.lineno, "authorization": "bearer + rol" if roles else "publico", "roles": roles or [], "request_media_types": list(operation.get("requestBody", {}).get("content", {})), "request_body": operation.get("requestBody"), "parameters": operation.get("parameters", []), "responses": operation["responses"], "operation_id": operation["operationId"]})
    expected = {(method.upper(), route) for route, methods in spec["paths"].items() for method in methods if method in METHODS}
    actual = {(row["method"], row["path"]) for row in endpoints}
    assert expected == actual and len(endpoints) == len(actual), "OpenAPI y AST no coinciden"
    endpoints.sort(key=lambda row: (row["module"], row["path"], row["method"]))
    write_json(EVIDENCE / "endpoints_actuales.json", {"source_openapi_sha256": hashlib.sha256(raw).hexdigest(), "endpoint_count": len(endpoints), "security_is_static_analysis_not_runtime_rbac_test": True, "endpoints": endpoints})
    table = ["# Endpoints y permisos actuales", "", "Generado de AST y contrastado contra OpenAPI de fase 0. A=Administrador, R=Recepción, T=Técnico IA. Los roles reflejan dependencias declaradas, no una nueva certificación RBAC. Docs/Redoc/OpenAPI son rutas técnicas públicas adicionales fuera de este conteo.", "", "| Método | Ruta | Roles | Entrada | Respuesta declarada | Fuente |", "|---|---|---|---|---|---|"]
    for row in endpoints:
        roles = ",".join({"ADMINISTRADOR":"A", "RECEPCION":"R", "TECNICO_IA":"T"}[r] for r in row["roles"]) or "Público"
        response = row["responses"].get("200", row["responses"].get("201", row["responses"].get("204", {})))
        schemas = [entry.get("schema", {}).get("$ref", entry.get("schema", {}).get("type", "objeto" )).split("/")[-1] for entry in response.get("content", {}).values()]
        table.append(f"| {row['method']} | `{row['path']}` | {roles} | {', '.join(row['request_media_types']) or 'query/path o sin body'} | {', '.join(schemas) or 'sin contenido'} | `{row['source']}:{row['line']}` |")
    with (EVIDENCE / "ENDPOINTS_ACTUALES.md").open("x", encoding="utf-8") as stream: stream.write("\n".join(table) + "\n")
    imports, persistence, source_hashes = [], [], []
    for path in sorted((ROOT / "backend-predicitas/app").rglob("*.py")):
        text = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(text)
        relative = path.relative_to(ROOT).as_posix()
        source_hashes.append({"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        source_module = path.parts[path.parts.index("modules") + 1] if "modules" in path.parts else "core/composicion"
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        def context(node):
            enclosing = [fn for fn in functions if fn.lineno <= node.lineno <= fn.end_lineno]
            return min(enclosing, key=lambda fn: fn.end_lineno-fn.lineno).name if enclosing else "<module>"
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.modules."):
                target = node.module.split(".")[2]
                if target != source_module:
                    imports.append({"source_module": source_module, "target_module": target, "import_from": node.module, "symbols": [item.name for item in node.names], "source": relative, "line": node.lineno, "function": context(node)})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "db" and node.func.attr in ("commit", "flush", "add", "add_all", "execute", "get"):
                persistence.append({"source": relative, "line": node.lineno, "function": context(node), "call": ast.unparse(node), "note": "execute/get pueden ser lectura; no interpretar todo como escritura"})
    write_json(EVIDENCE / "dependencias_y_persistencia.json", {"cross_module_imports": imports, "persistence_sites": persistence, "source_hashes": source_hashes, "scope": "Imports AST completos app.modules.*; sitios db.* son candidatos tecnicos, no analisis exhaustivo de flujo de datos/SQL dinamico."})
    references = []
    for path in sorted((ROOT / "frontend-predicitas/src").rglob("*")):
        if not path.is_file() or path.suffix not in (".ts", ".tsx", ".js", ".jsx") or ".test." in path.name: continue
        text = path.read_text(encoding="utf-8-sig")
        for match in re.finditer(r"([\"'`])(/[^\n\"'`]*?)\1", text):
            references.append({"source": path.relative_to(ROOT).as_posix(), "line": text[:match.start()].count("\n")+1, "literal": match.group(2), "category": "legacy_no_retirar_sin_revisar" if any(p in path.parts for p in ("pages", "lib", "auth", "components")) else "modular_o_nucleo", "not_automatically_classified_as_api_call": True})
    write_json(EVIDENCE / "referencias_frontend.json", references)
    write_json(ROOT / "contracts/backend/procedencia.json", {"status": "snapshot_actual_no_redisenado", "copied_from": "docs/migracion/fase-00/openapi_baseline.json", "sha256": hashlib.sha256(raw).hexdigest(), "source_git_baseline": "69c686f21fd1938dc76d679f4c6b33270f10a6d7", "endpoints": len(endpoints), "modules": dict(sorted(Counter(row["module"] for row in endpoints).items())), "note": "OpenAPI declara JSON para algunas descargas que retornan Response; limitaciones y diferencias se documentan aparte."})
    print(json.dumps({"endpoints": len(endpoints), "cross_module_imports": len(imports), "persistence_sites": len(persistence), "frontend_literal_references": len(references)}, ensure_ascii=False))


if __name__ == "__main__": main()
