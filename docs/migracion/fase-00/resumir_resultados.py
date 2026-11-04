"""Publica resultados de pruebas sin logs completos privados ni secretos."""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def read_log(path):
    data = path.read_bytes()
    text = data.decode("utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", errors="replace")
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    private = args.private_dir.resolve(strict=True)
    evidence = Path(__file__).resolve().parent
    frontend = read_log(private / "frontend_test.log")
    check = read_log(private / "frontend_typecheck.log")
    pip_log = read_log(private / "backend_resolucion_limpia.log")
    junit = ET.parse(evidence / "backend_diagnostico_junit.xml")
    cases = list(junit.iter("testcase"))
    failures = [case for case in cases if case.find("failure") is not None]
    coverage = json.loads((evidence / "backend_diagnostico_coverage.json").read_text())
    result = {
        "frontend": {
            "npm_ci_exit_code": 0,
            "tests_summary": [line.strip() for line in frontend.splitlines() if re.search(r"^\s*(Test Files|Tests|Duration)\s", line)],
            "failing_test_files": sorted(set(re.findall(r"\bFAIL\s+(src/\S+)", frontend))),
            "typecheck_diagnostics": [line.strip() for line in check.splitlines() if re.search(r"error TS\d+:", line)],
            "coverage": "No se genero reporte de cobertura al fallar la ejecucion de Vitest; no se declara aprobado el umbral.",
            "npm_audit": "9 vulnerabilidades moderadas; 0 altas/criticas. Sin aplicar npm audit fix.",
        },
        "backend": {
            "full_suite_exit_code": 2,
            "full_suite_blocker": "tests/ia/conftest.py:15 importa app.modules.ia.cliente, inexistente; tambien referencia reloj_ia y un simulador ausentes del codigo actual.",
            "diagnostic_only_excluded_directory": "tests/ia",
            "diagnostic_tests": len(cases), "diagnostic_passed": len(cases) - len(failures), "diagnostic_failed": len(failures),
            "failed_cases": [{"file": case.get("classname"), "name": case.get("name"), "message": case.find("failure").get("message")} for case in failures],
            "diagnostic_coverage_percent": coverage["totals"]["percent_covered"],
            "threshold_changed": False,
            "fresh_requirement_resolution": "BLOCKED_NETWORK_TIMEOUT" if "ReadTimeoutError" in pip_log else "REVIEW_PRIVATE_LOG",
            "installed_image_requirements": "Todas las versiones fijadas coinciden; ver ia_baseline.json. No sustituye validacion de instalacion limpia.",
        },
        "browser": {
            "isolated_frontend": "http://127.0.0.1:5174",
            "isolated_api": "http://127.0.0.1:8001",
            "login_recepcion": "OK con usuario desechable creado solo en servidor restaurado",
            "appointments_page": "OK: /citas, Citas encontradas 1122 y tabla cargada",
            "screenshot": "PENDIENTE: herramienta requiere pestana/ventana visible; no se obtuvo captura ni se declara validacion visual completa.",
            "temporary_infrastructure_issue": "Red Docker internal impedia publicar API; se agrego bridge solo a API aislada. Sin cambios en CORS/config original.",
        },
        "scope": "Linea base del codigo original. No se corrigieron fallos ni se cambiaron dependencias.",
    }
    with (evidence / "resultados_baseline.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
