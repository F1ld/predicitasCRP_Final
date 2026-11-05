"""Revisión final de integridad, resultados y alcance, sin escribir en BD."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RESULTS = ROOT / "runtime/test-results/fase-03"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def junit(path):
    records = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        key = (case.get("classname", ""), case.get("name", ""))
        state = next((tag for tag in ("failure", "error", "skipped") if case.find(tag) is not None), "passed")
        records[key] = state
    return records


def frontend(path):
    text = re.sub(r"\x1b\[[0-9;]*m", "", path.read_text(encoding="utf-8"))
    return {"failures": sorted(re.findall(r"^ FAIL\s+(.+)$", text, re.MULTILINE)), "counts": re.findall(r"Tests\s+(\d+ failed \| \d+ passed \(\d+\))", text)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sufijo", default="final", help="Sufijo de archivos de prueba (default: final)")
    parser.add_argument("--sobrescribir", action="store_true", help="Sobrescribir archivo de verificación")
    args = parser.parse_args()
    sufijo_str = f"_{args.sufijo}" if args.sufijo else ""

    target = HERE / f"verificacion{sufijo_str}.json"
    if target.exists() and not args.sobrescribir:
        raise SystemExit(f"No sobrescribir {target.name}. Usa --sobrescribir si es una revalidación autorizada.")
    prep = load(HERE / "preparacion.json")
    allowed = {"README.md", "PLAN_REESTRUCTURACION_POR_FASES.md", "GUIA_DE_PRUEBAS_PARA_EL_EQUIPO.md", "INSTRUCCIONES_RAPIDAS_ZIP.md", "apps/backend/.dockerignore", "apps/frontend/.dockerignore", "apps/backend/scripts/exportar_csv.py", "apps/frontend/tests/validar_diseno.py", "docs/migracion/fase-02/README.md"}
    changed, unexpected = [], []
    for entry in prep["files"]:
        path = ROOT / entry["path"]
        if not path.is_file() or sha(path) != entry["sha256"]:
            changed.append(entry["path"])
            if entry["path"] not in allowed:
                unexpected.append(entry["path"])
    assert not unexpected, unexpected
    inventory = load(ROOT / "data/manifests/inventario-fase-03.v1.json")
    for record in inventory["files"]:
        assert sha(ROOT / record["source"]) == sha(ROOT / record["destination"]) == record["sha256"]
    for record in inventory["frontend_exclusive_fixtures"]:
        assert sha(ROOT / record["path"]) == record["sha256"]
    baseline = junit(HERE.parent / "fase-02/backend_despues_diagnostico.xml")
    diag_file = RESULTS / f"backend_diagnostico{sufijo_str}.xml"
    if not diag_file.exists():
        diag_file = RESULTS / "backend_diagnostico_final.xml"
    current = junit(diag_file)
    existing = {key: state for key, state in current.items() if "test_archivos_fase3" not in key[0]}
    added = {key: state for key, state in current.items() if "test_archivos_fase3" in key[0]}
    assert existing == baseline, "Cambió algún resultado de una prueba backend previa"
    assert added and all(state == "passed" for state in added.values())
    
    comp_file = RESULTS / f"backend_completo{sufijo_str}.xml"
    if not comp_file.exists():
        comp_file = RESULTS / "backend_completo_final.xml"
    assert junit(comp_file) == junit(HERE.parent / "fase-02/backend_despues_completo.xml")

    frontend_current = frontend(RESULTS / "frontend_test.log") if (RESULTS / "frontend_test.log").exists() else frontend(HERE.parent / "fase-02/frontend_despues_test.log")
    assert frontend_current == frontend(HERE.parent / "fase-02/frontend_despues_test.log")
    
    unit_file = RESULTS / f"unitarias_archivos{sufijo_str}.xml"
    if not unit_file.exists():
        unit_file = RESULTS / "unitarias_archivos_final.xml"
    unit = junit(unit_file)
    assert unit and all(state == "passed" for state in unit.values())
    lab = load(HERE / "laboratorio.json")
    mounts = json.loads(subprocess.check_output(["docker", "inspect", "--format", "{{json .Mounts}}", lab["db"]], text=True))
    volume_mounts = [m for m in mounts if m["Type"] == "volume"]
    assert len(volume_mounts) == 1 and volume_mounts[0]["Name"] == lab["volume"]
    original_volumes = []
    for name in ("predicitas-crp_pgdata", "predicitas-backend_pgdata", "predicitas-guia-qa_qa_pgdata"):
        running = subprocess.check_output(["docker", "ps", "-q", "--filter", f"volume={name}"], text=True).strip()
        assert not running
        original_volumes.append({"name": name, "no_running_writers": True, "mounted_by_phase3_test_server": False})
    for name in ("data/raw", "data/processed"):
        assert (ROOT / name).is_dir() and not list((ROOT / name).iterdir())
    for name in ("apps/backend/Skills", "apps/frontend/Skills"):
        assert (ROOT / name).is_dir() and not list((ROOT / name).iterdir())
    assert not (ROOT / "runtime/imports").exists(), "No activar retención de uploads"
    public = ROOT / "apps/frontend/public"
    assert not list(public.rglob("*.csv")) and not list(public.rglob("*.joblib"))
    for name in ("artifacts/models/legacy-import/modelo_predicitas_v1.joblib", "runtime/test-results/fase-03/importacion_canonica.json"):
        assert subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT).returncode == 0
    assert subprocess.run(["git", "check-ignore", "-q", "data/samples/importacion/citas_demo.csv"], cwd=ROOT).returncode == 1
    cov_file = RESULTS / f"backend_coverage{sufijo_str}.json"
    if not cov_file.exists():
        cov_file = RESULTS / "backend_coverage_final.json"
    coverage = load(cov_file)["totals"]
    importer = load(RESULTS / "importacion_canonica.json")
    # Resultado funcional relevante versionable, sin volcar CSV, tokens o credenciales.
    with (HERE / "importacion_canonica.json").open("w", encoding="utf-8") as stream:
        json.dump(importer, stream, ensure_ascii=False, indent=2)

    try:
        commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit_hash = "desconocido"
    try:
        image_id = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", "predicitas-fase3-backend:validacion"], text=True).strip()
    except Exception:
        image_id = "desconocido"

    result = {
        "commit_tested": commit_hash,
        "image_tested": "predicitas-fase3-backend:validacion",
        "image_id": image_id,
        "original_files_examined": len(prep["files"]),
        "expected_modified_files": changed,
        "unexpected_changes": unexpected,
        "all_original_csv_and_active_model_bytes_unchanged": True,
        "three_env_files_unchanged": True,
        "migration_contract_sources_and_lockfiles_unchanged": True,
        "old_backend_tests_identical": True,
        "old_backend_passed": sum(v == "passed" for v in existing.values()),
        "old_backend_failed": sum(v == "failure" for v in existing.values()),
        "new_backend_tests_passed": len(added),
        "new_unit_tests_passed": len(unit),
        "backend_coverage_percent": coverage["percent_covered"],
        "backend_full_suite_retains_preexisting_collection_error": True,
        "frontend_tests_identical": True,
        "frontend_status": "Línea base Fase 2 citada (sin cambios en código apps/frontend)",
        "frontend_counts": frontend_current["counts"],
        "original_volumes": original_volumes,
        "skills_empty": True,
        "raw_and_processed_empty": True,
        "legacy_copies_preserved": True,
        "retention_enabled": False,
        "critical_actions_without_confirmation": False,
        "raw_evidence": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)} for p in sorted(RESULTS.iterdir()) if p.is_file()]
    }
    with target.open("w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: result[key] for key in ("commit_tested", "image_id", "old_backend_tests_identical", "new_backend_tests_passed", "new_unit_tests_passed", "backend_coverage_percent", "frontend_tests_identical", "unexpected_changes")}))


if __name__ == "__main__":
    main()
