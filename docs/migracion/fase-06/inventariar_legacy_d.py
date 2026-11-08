"""Inventario estático y gate de retirada; nunca importa ni elimina aplicaciones."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEGACY = "app.modules.citas.synthetic"
PUBLIC = "app.modules.citas.public"
SYMBOL = "generar_citas"
SCOPES = ("apps/backend/app", "apps/backend/scripts", "apps/backend/tests",
          "apps/ia/app", "apps/ia/datasets", "apps/ia/training", "apps/ia/management",
          "apps/ia/tests", "apps/frontend/tests")
PRODUCERS = ("apps/backend/app/modules/citas/synthetic.py", "apps/ia/datasets/synthetic.py")


def relative_module(path, node):
    if not node.level:
        return node.module or ""
    parts = Path(path).with_suffix("").parts
    package = list(parts[2:-1])  # apps/<aplicación>/<paquete>/archivo.py
    if node.level > len(package):
        raise ValueError("Import relativo no resoluble")
    return ".".join(package[:len(package) - node.level + 1] + (node.module or "").split(".")).rstrip(".")


def references(source, path):
    result = []
    tree = ast.parse(source, filename=path)
    public_aliases = {PUBLIC}
    def add(node, module, symbol, kind):
        result.append({"path": path, "line": node.lineno, "module": module,
                       "symbol": symbol, "kind": kind})
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = relative_module(path, node)
            for alias in node.names:
                if module == LEGACY:
                    add(node, module, alias.name, "from")
                elif module == PUBLIC and alias.name in (SYMBOL, "*"):
                    add(node, module, alias.name, "from")
                elif module == "app.modules.citas" and alias.name == "synthetic":
                    add(node, LEGACY, "*", "module")
                elif module == "app.modules.citas" and alias.name == "public":
                    public_aliases.add(alias.asname or alias.name)
                    add(node, PUBLIC, "*", "namespace")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in (LEGACY, PUBLIC):
                    kind = "namespace" if alias.name == PUBLIC else "module"
                    if alias.name == PUBLIC and alias.asname:
                        public_aliases.add(alias.asname)
                    add(node, alias.name, "*", kind)
        elif isinstance(node, ast.Call):
            func = node.func
            literal_import = (isinstance(func, ast.Name) and func.id == "__import__"
                or isinstance(func, ast.Attribute) and func.attr == "import_module")
            if literal_import and node.args and isinstance(node.args[0], ast.Constant):
                if node.args[0].value in (LEGACY, PUBLIC):
                    add(node, node.args[0].value, "*", "dynamic-literal")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == SYMBOL and ast.unparse(node.value) in public_aliases:
            add(node, PUBLIC, SYMBOL, "attribute")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr":
            if (len(node.args) >= 2 and ast.unparse(node.args[0]) in public_aliases
                    and isinstance(node.args[1], ast.Constant) and node.args[1].value == SYMBOL):
                add(node, PUBLIC, SYMBOL, "getattr-literal")
    return sorted(result, key=lambda item: (item["path"], item["line"], item["module"], item["symbol"]))


def fingerprint(path):
    # Reproducible también en Windows con checkout autocrlf.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def inventory(root, retired_producers=()):
    root = Path(root)
    result, errors, namespaces = [], [], []
    for scope in SCOPES:
        folder = root / scope
        if not folder.is_dir() or folder.is_symlink():
            errors.append({"path": scope, "error": "SCOPE_MISSING"})
            continue
        for path in sorted(folder.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(root).as_posix()
            try:
                if path.is_symlink():
                    raise ValueError("Archivo enlazado no permitido")
                for item in references(path.read_text(encoding="utf-8-sig"), relative):
                    (namespaces if item["kind"] == "namespace" else result).append(item)
            except (OSError, SyntaxError, ValueError, UnicodeError):
                errors.append({"path": relative, "error": "SOURCE_UNREADABLE"})
    producers = {}
    for name in PRODUCERS:
        path = root / name
        if name in retired_producers:
            if path.exists() or path.is_symlink():
                errors.append({"path": name, "error": "RETIRED_PRODUCER_PRESENT"})
            continue
        if path.is_file() and not path.is_symlink():
            producers[name] = fingerprint(path)
        else:
            errors.append({"path": name, "error": "PRODUCER_MISSING_OR_LINKED"})
    return {"references": result, "namespace_references_informational": namespaces,
            "errors": errors, "producer_sha256_lf": producers}


def identity(item):
    return tuple(item[key] for key in ("path", "module", "symbol", "kind"))


def evaluate(actual, policy):
    expected = {identity(item) for item in policy["allowed_references"]}
    observed = {identity(item) for item in actual["references"]}
    unexpected = [item for item in actual["references"] if identity(item) not in expected]
    producer_changed = actual["producer_sha256_lf"] != policy["producer_sha256_lf"]
    pending_review = sorted(expected - observed)
    valid = not actual["errors"] and not unexpected and not producer_changed and not pending_review
    scheduled_exceptions = {identity(item) for item in policy.get("scheduled_exceptions", [])}
    migrations = [item for item in actual["references"] if identity(item) not in scheduled_exceptions]
    scheduled_approved = policy.get("scheduled_retirement_approved") is True
    return actual | {"unexpected_references": unexpected,
        "removed_references_requiring_policy_review": [list(item) for item in pending_review],
        "producer_changed": producer_changed,
        "inventory_valid": valid,
        "scheduled_retirement_approved": scheduled_approved,
        "remaining_migrations": migrations,
        "scheduled_closure_ready": valid and scheduled_approved and not migrations,
        "retirement_review_approved": policy.get("retirement_review_approved") is True,
        "retirement_allowed": valid and not actual["references"] and policy.get("retirement_review_approved") is True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--policy", type=Path, default=Path(__file__).with_name("legacy-d.policy.json"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--exigir-retiro", action="store_true")
    mode.add_argument("--exigir-cierre-programado", action="store_true")
    args = parser.parse_args(argv)
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    retired_producers = policy.get("retired_producers", ())
    if any(name != PRODUCERS[0] for name in retired_producers):
        parser.error("Solo puede retirarse el productor legacy del backend")
    result = evaluate(inventory(args.root, retired_producers), policy)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    if not result["inventory_valid"]:
        return 3
    if args.exigir_cierre_programado and not result["scheduled_closure_ready"]:
        return 2
    if args.exigir_retiro and not result["retirement_allowed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
