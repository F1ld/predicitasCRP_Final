"""Comprueba integridad de la entrega documental, sin modificar aplicaciones."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def load(path): return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-baseline-dir", type=Path, required=True)
    args = parser.parse_args()
    original = load(args.private_baseline_dir / "inventario_privado.json")
    checked, changed = 0, []
    for row in original:
        name = row["path"]
        if name.startswith(".git/") or name == "PLAN_REESTRUCTURACION_POR_FASES.md": continue
        checked += 1
        path = ROOT / name
        if not path.is_file() or sha(path) != row["sha256"]: changed.append(name)
    if changed: raise SystemExit(f"Archivos originales cambiados, revisar sin sobrescribir: {changed}")
    for row in load(HERE / "dependencias_y_persistencia.json")["source_hashes"]:
        if sha(ROOT / row["path"]) != row["sha256"]: raise SystemExit(f"Cambio concurrente en {row['path']}")
    schemas = list((ROOT / "contracts").rglob("*.schema.json"))
    documents = [*list((ROOT / "contracts").rglob("*.json")), *list(HERE.rglob("*.json"))]
    for path in documents: load(path)
    for path in HERE.glob("*.py"): ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    validation = load(HERE / "validacion_contratos.json")
    backend = load(HERE / "validacion_contra_backend_actual.json")
    ui = load(HERE / "frontend_rutas_menu_alcance.json")
    assert validation["all_expected_results_met"] and validation["schema_count"] == len(schemas)
    assert validation["fixture_count"] == len(load(ROOT / "contracts/examples/casos.json")["cases"])
    assert backend["openapi_matches_current_app"] and backend["public_operations"] == 55
    assert ui["production_module_routes"] == 15 and ui["test_only_routes"] == 1
    assert (ROOT / "contracts/backend/openapi.actual.v0.5.0.json").read_bytes() == (ROOT / "docs/migracion/fase-00/openapi_baseline.json").read_bytes()
    for name in ("backend-predicitas/Skills", "frontend-predicitas/Skills"):
        assert (ROOT / name).is_dir() and not list((ROOT / name).iterdir())
    secrets = []
    for name in (".env", "backend-predicitas/.env", "frontend-predicitas/.env"):
        for line in (ROOT / name).read_text(encoding="utf-8-sig").splitlines():
            if "=" not in line or line.lstrip().startswith("#"): continue
            key, value = line.split("=", 1)
            if re.search(r"PASSWORD|SECRET_KEY|IA_API_KEY", key, re.I):
                value = value.strip().strip("\"'")
                if len(value) >= 12: secrets.append(value)
    deliverables = [ROOT / "PLAN_REESTRUCTURACION_POR_FASES.md"]
    for directory in (ROOT / "contracts", ROOT / "docs/arquitectura", HERE):
        deliverables.extend(path for path in directory.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    link_count = 0
    for path in deliverables:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if any(secret in text for secret in secrets): raise SystemExit(f"Posible secreto en {path.relative_to(ROOT)}")
        if path.suffix == ".md":
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if target.startswith(("http:", "https:", "mailto:", "#")): continue
                local = target.split("#", 1)[0]
                if not (path.parent / local).exists(): raise SystemExit(f"Enlace roto {path.relative_to(ROOT)} -> {target}")
                link_count += 1
    result = {"existing_files_sha256_checked": checked, "changed_original_files_excluding_plan_git_metadata": changed, "public_snapshot_unchanged": True, "schema_count": len(schemas), "contract_cases": validation["fixture_count"], "public_operations": 55, "ui_module_routes": 15, "skills_both_empty": True, "relative_links_checked": link_count, "no_original_long_secret_values_found": True, "no_database_or_joblib_access_in_this_check": True, "new_functional_app_tests_claimed": False}
    with (HERE / "verificacion_entrega.json").open("x", encoding="utf-8") as stream: json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
