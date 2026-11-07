"""Corrección fase 5: ejecución exclusiva, imagen inmutable y resultados medidos.

No sobrescribe evidencia histórica. verificar solo comprueba integridad del paquete.
No requiere ni arranca PostgreSQL. Los secretos efímeros quedan fuera del repo.
"""
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASELINE = "af13b3b"
A_BASELINE = "3e561b2"
B_BASELINE = "bfcad63"
BACKEND_IMAGE = "sha256:b1225267a59311a2fadce32ea139cabaa948b0b6ff2d344eb083a48e6421666d"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def output(command, **kwargs):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=600, **kwargs)
    if result.returncode:
        raise RuntimeError(f"Falló acción {command[0]} ({result.returncode}); no publicar aceptación")
    return result.stdout.strip()


def tracked(*folders):
    names = output(["git", "ls-files", "--", *folders]).splitlines()
    return {p: sha(ROOT / p) for p in names if (ROOT / p).is_file()}


def sources():
    result = tracked("apps/ia", "contracts")
    result.update(tracked("docs/migracion/fase-00/ia_baseline.json"))
    result.update({p.relative_to(ROOT).as_posix(): sha(p) for p in HERE.glob("*.py")})
    return result


def protected():
    result = tracked("apps/backend", "apps/frontend", "contracts")
    for name in (".env", "apps/backend/.env", "apps/frontend/.env", "artifacts/models/legacy-import/modelo_predicitas_v1.joblib",
                 "apps/backend/app/modules/ia/artifacts/modelo_predicitas_v1.joblib"):
        path = ROOT / name
        if path.is_file():
            result[name] = sha(path)
    for path in (ROOT / "data/samples").rglob("*.csv"):
        result[path.relative_to(ROOT).as_posix()] = sha(path)
    return result


def action(raw, name, command):
    with (raw / f"{name}.log").open("x", encoding="utf-8", newline="\n") as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    write(raw / f"{name}.action.json", {"exit_code": result.returncode, "log_sha256": sha(raw / f"{name}.log")})
    if result.returncode:
        raise RuntimeError(f"Falló {name}; conservar logs privados y usar otro run-id")
    print(f"{name}: aprobado", flush=True)


def junit(path):
    cases = list(ET.parse(path).iter("testcase"))
    assert cases and len({(c.get("classname"), c.get("name")) for c in cases}) == len(cases)
    return Counter(next((k for k in ("failure", "error", "skipped") if c.find(k) is not None), "passed") for c in cases)


def verify(target, run_id):
    manifest = read(target / "manifest.json")
    assert manifest["run_id"] == run_id
    for item in manifest["files"]:
        assert Path(item["name"]).name == item["name"]
        assert sha(target / item["name"]) == item["sha256"]
    print("Integridad comprobada; no es una nueva ejecución de pruebas")


def execute(raw, run_id, scope="correccion"):
    assert not output(["git", "status", "--porcelain"]), "Registrar implementación antes de validar"
    assert not output(["git", "diff", BASELINE, "--", "apps/backend", "apps/frontend", "contracts"]), "Baseline operativo alterado"
    if scope == "A":
        assert not output(["git", "diff", A_BASELINE, "--", "apps/ia/app", "apps/ia/manifests",
            "apps/ia/Dockerfile", "apps/ia/requirements.txt"]), "Bloque A no autoriza alterar serving, modelo aprobado o dependencias"
    if scope == "B":
        assert not output(["git", "diff", B_BASELINE, "--", "apps/ia/app", "apps/ia/manifests", "apps/ia/training",
            "apps/ia/Dockerfile", "apps/ia/requirements.txt"]), "Bloque B no autoriza alterar serving, entrenamiento, modelo aprobado o dependencias"
    commit = output(["git", "rev-parse", "HEAD"])
    before, preserved = sources(), protected()
    raw.mkdir(parents=True, exist_ok=False)
    write(raw / "initial.json", {"commit_tested": commit, "sources": before, "protected": preserved})
    action(raw, "runner_tests", [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(HERE), "-p", "test_runner.py"])
    tag = "predicitas-ia:" + run_id
    if subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode == 0:
        raise ValueError("No adoptar ni sobrescribir imagen preexistente")
    contract_context = raw / "contracts-context"
    contract_context.mkdir()
    for name in tracked("contracts"):
        destination = contract_context / Path(name).relative_to("contracts")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    action(raw, "build", ["docker", "build", "--build-context", f"contracts={contract_context}", "-f",
        str(ROOT / "apps/ia/Dockerfile"), "-t", tag, str(ROOT / "apps/ia")])
    image = output(["docker", "image", "inspect", "--format", "{{.Id}}", tag])
    assert re.fullmatch(r"sha256:[a-f0-9]{64}", image)
    write(raw / "image.json", {"image_id": image, "tag": tag})
    private = Path(os.environ["LOCALAPPDATA"]) / "Temp/opencode" / run_id
    private.mkdir(exist_ok=False)
    user = output(["whoami"])
    output(["icacls", str(private), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"])
    env = private / "ia.env"
    with env.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("IA_API_KEY=" + secrets.token_urlsafe(32) + "\nMODEL_REGISTRY_DIR=/models\n")
    base = ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,nosuid,size=256m",
        "--cpus", "2", "--memory", "1g", "--env-file", str(env), "-e", "PYTHONPATH=/app",
        "--mount", f"type=bind,source={ROOT / 'artifacts/models/legacy-import'},target=/models,readonly",
        "--mount", f"type=bind,source={raw},target=/results",
        "--mount", f"type=bind,source={HERE},target=/checks,readonly", image]
    # Comprobar fuentes del paquete, incluyendo contratos, sin montar el backend.
    code = """import hashlib,json; from pathlib import Path
paths=[p for folder in ('/app/app','/app/tests','/app/manifests','/app/training','/app/datasets','/contracts') for p in Path(folder).rglob('*') if p.is_file() and '__pycache__' not in str(p)]
paths += [Path('/app/requirements.txt'),Path('/app/Dockerfile'),Path('/app/.dockerignore')]
print(json.dumps({str(p):hashlib.sha256(p.read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest() for p in paths}))"""
    packaged = json.loads(output([*base, "python", "-c", code]))
    expected = {}
    for name in before:
        if name.startswith("apps/ia/"):
            key = "/app/" + name.removeprefix("apps/ia/")
        elif name.startswith("contracts/"):
            key = "/" + name
        else:
            continue
        expected[key] = hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert packaged == expected, "El paquete no coincide con las fuentes registradas"
    coverage_args = ["--cov=app", *(["--cov=training"] if scope in ("A", "B") else []), *(["--cov=datasets"] if scope == "B" else [])]
    action(raw, "pytest", [*base, "python", "-m", "pytest", "tests", "-q", "--junitxml=/results/pytest.xml",
        *coverage_args, "--cov-fail-under=80", "--cov-report=json:/results/coverage.json"])
    action(raw, "runtime", [*base, "python", "/checks/probar_runtime.py", "/results/runtime.json"])
    # Paridad diferencial contra el backend preservado, sin red ni conexión real a BD.
    golden = read(ROOT / "docs/migracion/fase-00/ia_baseline.json")["predictions"]
    cases = [x["features"] for x in golden]
    # Incluir también los cinco casos congelados de la primera suite IA, sin
    # importar código backend/IA en el host ni perder sus expectativas exactas.
    tree = ast.parse((ROOT / "apps/ia/tests/test_parity.py").read_text(encoding="utf-8-sig"))
    frozen_suite = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "CASOS_CONGELADOS" for t in n.targets))
    for item in frozen_suite:
        if item["caso"] not in cases:
            cases.append(item["caso"])
    frozen_count = len(cases)
    rng = random.Random(42)
    for _ in range(200):
        cases.append({"especialidad": rng.choice(["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"]),
            "tipo_paciente": rng.choice(["NUEVO", "CONTINUADOR"]), "canal_origen": rng.choice(["WEB", "CALL_CENTER", "PRESENCIAL"]),
            "franja_horaria": rng.choice(["MANANA", "TARDE"]), "dia_semana": rng.choice(["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO"]),
            "antelacion_dias": rng.choice([0, 1, 3, 14, 15, 16, 30, 60]), "inasistencias_previas": rng.randrange(6),
            "asistencias_previas": rng.randrange(10), "reprogramaciones_prev": rng.randrange(5)})
    code_old = """import json,sys; from app.modules.ia.predictor import predecir_cita_dict
out=[]
for f in json.load(sys.stdin):
 p=predecir_cita_dict(f); p['probabilidad_no_show']=float(p['probabilidad_no_show']); p['umbral_aplicado']=float(p['umbral_aplicado']); out.append(p)
print(json.dumps(out))"""
    old = json.loads(output(["docker", "run", "--rm", "-i", "--network", "none", "-e", "OMP_NUM_THREADS=1",
        "-e", "DATABASE_URL=postgresql+psycopg://unused:unused@invalid/unused", "-e", "SECRET_KEY=offline-no-auth-no-connection",
        BACKEND_IMAGE, "python", "-c", code_old], input=json.dumps(cases)))
    code_new = """import json,sys; from app.core.model_registry import registry; from app.core.inference import ejecutar_inferencia_individual; from app.schemas import FeaturesPreCita
assert registry.load_model(); out=[]
for f in json.load(sys.stdin):
 p,n,s,e=ejecutar_inferencia_individual(registry.pipeline,FeaturesPreCita(**f)); out.append({'version_modelo':registry.version_modelo,'probabilidad_no_show':p,'nivel_riesgo':n,'features_snapshot':s.model_dump(),'explicabilidad_resumen':e,'umbral_aplicado':registry.get_metadata().umbrales.alto})
print(json.dumps(out))"""
    interactive = base.copy()
    interactive.insert(3, "-i")
    new = json.loads(output([*interactive, "python", "-c", code_new], input=json.dumps(cases)))
    assert old == new
    for i, frozen in enumerate(golden):
        expected_prediction = dict(frozen["prediction"])
        for key in ("probabilidad_no_show", "umbral_aplicado"):
            expected_prediction[key] = float(expected_prediction[key])
        assert new[i] == expected_prediction, "Paridad congelada modificada"
    for item in frozen_suite:
        prediction = new[cases.index(item["caso"])]
        for key, value in item["esperado"].items():
            actual = prediction["features_snapshot"][key] if key in ("tasa_no_show_previa", "es_reserva_lejana") else prediction[key]
            assert actual == value, "Expectativa congelada de suite modificada"
    write(raw / "parity.json", {"cases": len(cases), "frozen_cases": frozen_count,
        "phase0_cases": len(golden), "original_suite_cases": len(frozen_suite), "generated_seed": 42,
        "all_fields_equal": True, "levels_observed": sorted({p["nivel_riesgo"] for p in new}),
        "cases_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(), "backend_image": BACKEND_IMAGE})
    training = None
    if scope in ("A", "B"):
        from entrenamiento_a import validate
        training = validate(raw, base)
    datasets = None
    if scope == "B":
        from datasets_b import validate
        datasets = validate(raw, base, run_id)
    assert sources() == before and protected() == preserved
    assert not output(["git", "status", "--porcelain"])
    tests = junit(raw / "pytest.xml")
    assert set(tests) == {"passed"}
    coverage = read(raw / "coverage.json")["totals"]["percent_covered"]
    assert coverage >= 80
    training_coverage = None
    if scope in ("A", "B"):
        summaries = [value["summary"] for name, value in read(raw / "coverage.json")["files"].items()
            if name.replace("\\", "/").startswith("training/")]
        assert summaries
        training_coverage = 100 * sum(s["covered_lines"] for s in summaries) / sum(s["num_statements"] for s in summaries)
        assert training_coverage >= 80
    datasets_coverage = None
    if scope == "B":
        summaries = [value["summary"] for name, value in read(raw / "coverage.json")["files"].items()
            if name.replace("\\", "/").startswith("datasets/")]
        assert summaries
        datasets_coverage = 100 * sum(s["covered_lines"] for s in summaries) / sum(s["num_statements"] for s in summaries)
        assert datasets_coverage >= 80
    runtime = read(raw / "runtime.json")
    openapi = runtime.pop("openapi")
    write(raw / "openapi.json", openapi)
    freeze = output([*base, "python", "-m", "pip", "freeze", "--all"]).splitlines()
    write(raw / "resumen.json", {"run_id": run_id, "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit_tested": commit, "baseline": BASELINE, "image_id": image, "block": scope,
        "tests": dict(tests), "coverage_percent": coverage, "parity": read(raw / "parity.json"),
        "runtime": runtime, "packaged_sources_match": True, "source_files": before,
        "backend_frontend_contracts_unchanged": True, "protected_unchanged": True,
        "pip_freeze": freeze, "training_a": training, "training_coverage_percent": training_coverage,
        "serving_baseline_unchanged": A_BASELINE if scope == "A" else B_BASELINE if scope == "B" else None,
        "datasets_b": datasets, "datasets_coverage_percent": datasets_coverage,
        "phase_status": "EN CURSO; validacion de bloque no equivale a cerrar checklist original"})
    print(f"Corrección validada: {tests['passed']} pruebas, cobertura {coverage:.2f}%, {len(cases)} casos diferenciales")


def publish(raw, target, run_id):
    summary = read(raw / "resumen.json")
    assert summary["run_id"] == run_id and summary["source_files"] == sources()
    assert read(raw / "initial.json")["protected"] == protected()
    assert set(summary["tests"]) == {"passed"} and summary["coverage_percent"] >= 80
    assert summary["parity"]["all_fields_equal"] and summary["runtime"]["real_http"]
    for name in ("runner_tests", "build", "pytest", "runtime"):
        assert read(raw / f"{name}.action.json")["exit_code"] == 0
    if summary.get("block") in ("A", "B"):
        assert summary["training_coverage_percent"] >= 80 and summary["training_a"]["same_raw_probabilities_all_1000_both_models"]
        for name in ("training_reference", "training_candidate"):
            assert read(raw / f"{name}.action.json")["exit_code"] == 0
    if summary.get("block") == "B":
        assert summary["datasets_coverage_percent"] >= 80 and summary["datasets_b"]["laboratory_state"] == "exited"
        assert summary["datasets_b"]["generator"]["all_fields_and_row_order_equal"]
        for name in ("datasets_reference", "datasets_candidate", "csv_http_postgres"):
            assert read(raw / f"{name}.action.json")["exit_code"] == 0
    target.mkdir(parents=True, exist_ok=False)
    with (target / ".gitattributes").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("*.json text eol=lf\n*.xml text eol=lf\n")
    write(target / "resumen.json", summary)
    write(target / "openapi.json", read(raw / "openapi.json"))
    clean = ET.Element("testsuite")
    for case in ET.parse(raw / "pytest.xml").iter("testcase"):
        assert all(case.find(k) is None for k in ("error", "failure", "skipped"))
        ET.SubElement(clean, "testcase", {k: case.attrib[k] for k in ("classname", "name")})
    with (target / "pytest.xml").open("xb") as stream:
        stream.write(ET.tostring(clean, encoding="utf-8", xml_declaration=True))
    write(target / "manifest.json", {"run_id": run_id, "files": [
        {"name": p.name, "sha256": sha(p)} for p in sorted(target.iterdir()) if p.name != ".gitattributes"]})
    print("Evidencia correctiva sanitizada publicada; históricos intactos")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("ejecutar", "publicar", "verificar"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scope", choices=("correccion", "A", "B"), default="correccion")
    args = parser.parse_args()
    if not re.fullmatch(r"ia-[a-z0-9-]{3,36}", args.run_id):
        raise ValueError("run-id inválido")
    raw = ROOT / "runtime/test-results/fase-05" / args.run_id
    target = HERE / "evidencia" / args.run_id
    if args.action == "verificar":
        verify(target, args.run_id)
    elif args.action == "ejecutar":
        execute(raw, args.run_id, args.scope)
    else:
        publish(raw, target, args.run_id)


if __name__ == "__main__":
    main()
