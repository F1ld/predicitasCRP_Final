"""Conserva evidencia de paridad sin declarar aprobados defectos previos."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def junit(name):
    root = ET.parse(HERE / name).getroot()
    cases = []
    for item in root.iter("testcase"):
        state = next((tag for tag in ("failure", "error", "skipped") if item.find(tag) is not None), "passed")
        cases.append({"class": item.get("classname"), "name": item.get("name"), "state": state})
    return sorted(cases, key=lambda x: (x["class"] or "", x["name"] or ""))


def frontend(name):
    text = (HERE / name).read_text(encoding="utf-8")
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return {"failures": sorted(re.findall(r"^ FAIL\s+(.+)$", text, re.MULTILINE)), "counts": re.findall(r"Tests\s+(\d+ failed \| \d+ passed \(\d+\))", text)}


def main():
    output = HERE / "comparacion.json"
    if output.exists():
        raise SystemExit("No sobrescribir evidencia")
    before = load("smoke_antes.json")
    after = load("smoke_despues.json")
    frontend_before = frontend("frontend_antes_repetido_test.log")
    frontend_after = frontend("frontend_despues_test.log")
    manifest = load("movimientos.json")
    changed = []
    for entry in manifest["files"]:
        path = ROOT / entry["destination"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            changed.append(entry["destination"])
    allowed = {
        "apps/backend/.dockerignore", "apps/frontend/.dockerignore",
        "apps/backend/.env.example", "apps/backend/README.md",
        "apps/frontend/README.md", "apps/backend/docker-compose.yml",
    }
    unexpected = sorted(set(changed) - allowed)
    result = {
        "openapi_identical": before["openapi"] == after["openapi"],
        "smoke_roles_statuses_identical": before["results"] == after["results"],
        "predictions_identical": before["predictions"] == after["predictions"],
        "model_hash_identical": before["model_sha256"] == after["model_sha256"],
        "backend_complete_same_results": junit("backend_antes_completo.xml") == junit("backend_despues_completo.xml"),
        "backend_diagnostic_same_results": junit("backend_antes_diagnostico.xml") == junit("backend_despues_diagnostico.xml"),
        "frontend_same_failures_and_counts": frontend_before == frontend_after,
        "frontend_before": frontend_before,
        "frontend_after": frontend_after,
        "files_changed_after_mechanical_move": changed,
        "source_and_lockfiles_unchanged": not unexpected,
        "unexpected_changes": unexpected,
        "note": "Paridad no significa suite verde. Cambios permitidos posteriores: comentarios README/.env.example/.dockerignore y archivo Compose histórico archivado; revisar lista explícita."
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if isinstance(v, bool)}, indent=2))
    assert all(v for v in result.values() if isinstance(v, bool)), "Revisar diferencias antes de aceptar la mudanza"


if __name__ == "__main__":
    main()
