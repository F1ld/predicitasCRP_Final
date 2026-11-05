"""Cierre estricto de una ejecución y verificación portable sin Docker ni secretos."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from evidencia import (ROOT, HERE, cargar_run, destinos, escribir, leer, sha,
                       salida, verificar_laboratorio)


def junit(path):
    records = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        key = (case.get("classname", ""), case.get("name", ""))
        if key in records:
            raise ValueError(f"Caso JUnit duplicado: {key}")
        records[key] = next((tag for tag in ("failure", "error", "skipped") if case.find(tag) is not None), "passed")
    return records


def exigir(condition, message):
    if not condition:
        raise ValueError(message)


def junit_publico(source, target):
    """Solo identidad y estado; nunca tracebacks, stdout, propiedades o variables."""
    records = junit(source)
    suite = ET.Element("testsuite", tests=str(len(records)),
                       failures=str(sum(v == "failure" for v in records.values())),
                       errors=str(sum(v == "error" for v in records.values())),
                       skipped=str(sum(v == "skipped" for v in records.values())))
    for (classname, name), state in sorted(records.items()):
        case = ET.SubElement(suite, "testcase", classname=classname, name=name)
        if state != "passed":
            ET.SubElement(case, state)
    with target.open("xb") as stream:
        ET.ElementTree(suite).write(stream, encoding="utf-8", xml_declaration=True)


def comparar(public):
    baseline = junit(public / "baseline_diagnostico.xml")
    current = junit(public / "backend_diagnostico.xml")
    nuevos = {"test_archivos_fase3", "test_evidencia_fase3"}
    added = {k: v for k, v in current.items() if k[0].split(".")[-1] in nuevos}
    existing = {k: v for k, v in current.items() if k not in added}
    exigir(existing == baseline, "Cambió algún caso/estado backend previo")
    exigir(bool(added) and all(v == "passed" for v in added.values()), "Pruebas nuevas no aprobadas")
    unit = junit(public / "unitarias.xml")
    exigir(unit == added, "Unitarias y diagnóstico no contienen los mismos casos nuevos aprobados")
    exigir(junit(public / "backend_completo.xml") == junit(public / "baseline_completo.xml"),
           "Cambió la colección de suite completa; no ocultar errores con filtros")
    coverage = leer(public / "cobertura.json")
    exigir(coverage["percent_covered"] >= 75, "Cobertura menor a 75 %")
    importer = leer(public / "importacion_canonica.json")
    exigir(set(importer["database_initial_counts"]) == {"citas", "historial_estados_cita", "auditoria_eventos", "usuarios"}
           and not any(importer["database_initial_counts"].values()), "Laboratorio no vacío al iniciar integración")
    exigir(all(importer[k] for k in ("model_hash_unchanged", "prediction_parity", "openapi_unchanged", "database_isolated")),
           "Integración sin paridad o sin aislamiento")
    expected = [("citas_para_importar_variado.csv", 40, 0), ("citas_demo.csv", 20, 4)]
    exigir([(s["archivo"], s["aceptables_sin_duplicados_bd"], s["rechazadas"]) for s in importer["samples"]] == expected,
           "Resultados de muestras incorrectos")
    uploads = importer["uploads"]
    exigir(len(uploads) == 4 and all(u["rollback_verified"] for u in uploads), "Rollback/BOM incompleto")
    for filename, accepted, rejected in expected:
        cases = [u for u in uploads if u["archivo"] == filename]
        exigir({u["bom"] for u in cases} == {True, False}, "Falta caso BOM")
        for u in cases:
            exigir((u["primera_carga"]["aceptadas"], u["primera_carga"]["rechazadas"]) == (accepted, rejected)
                   and u["segunda_carga"]["aceptadas"] == 0
                   and u["segunda_carga"]["rechazadas"] == accepted + rejected, "Duplicados/cargas incorrectos")
    image = leer(public / "imagen_y_mounts.json")
    exigir(image["first_export_exit_code"] == 0 and image["second_export_exit_code"] == 2
           and image["existing_export_unchanged"] and image["packaging"]["uid"] == 1000
           and all(image["packaging"][k] for k in ("legacy_samples_excluded", "root_artifacts_excluded", "private_env_excluded", "active_model_packaged")),
           "Verificación de empaquetado incompleta")
    return {"old_backend_passed": sum(v == "passed" for v in existing.values()),
            "old_backend_failed": sum(v == "failure" for v in existing.values()),
            "new_unit_tests_passed": len(unit), "backend_diagnostic_passed": sum(v == "passed" for v in current.values()),
            "backend_coverage_percent": coverage["percent_covered"],
            "backend_full_suite": "Error de colección previo conservado; no es suite verde",
            "frontend_status": "Baseline citado: 451 aprobadas / 56 fallidas; no reejecutado"}


def verificar_portable(run_id):
    _, public = destinos(run_id)
    summary = leer(public / "verificacion.json")
    exigir(summary["run_id"] == run_id, "run-id de cierre incorrecto")
    for entry in summary["public_evidence"]:
        path = public / entry["path"]
        exigir(path.resolve().is_relative_to(public.resolve()), "Ruta de evidencia fuera del paquete")
        exigir(sha(path) == entry["sha256"], f"Evidencia alterada: {entry['path']}")
    meta = leer(public / "ejecucion.json")
    exigir(meta["commit_tested"] == summary["commit_tested"] and meta["image_id"] == summary["image_id"], "Identidad inconsistente")
    for entry in meta["source_files"]:
        path = ROOT / entry["path"]
        exigir(path.resolve().is_relative_to(ROOT), "Fuente fuera del repositorio")
        blob = salida(["git", "hash-object", "--path=" + entry["path"], str(path)])
        exigir(blob == entry["git_blob"], f"Fuente distinta de la probada: {entry['path']}")
    exigir(comparar(public) == summary["results"], "El resumen no coincide con la evidencia")
    print(json.dumps({"run_id": run_id, "portable_verification": "PASÓ", "results": summary["results"]}, ensure_ascii=False))


def cerrar(run_id):
    raw, public, meta = cargar_run(run_id)
    exigir(not public.exists(), "Ya existe paquete público; usar otro run-id")
    acciones = {}
    expected_codes = {"build": 0, "unitarias": 0, "reanudar": 0, "alembic": 0,
                      "integracion": 0, "backend_completo": 2, "backend_diagnostico": 1, "detener": 0}
    for name, code in expected_codes.items():
        record = leer(raw / f"{name}.json")
        exigir(record["run_id"] == run_id and record["commit_tested"] == meta["commit_tested"], "Acciones de distinta ejecución")
        exigir(record["image_id"] == (None if name == "build" else meta["image_id"]), "Imagen inconsistente")
        exigir(record["exit_code"] == code, f"Exit code inesperado: {name}")
        acciones[name] = record
    lab, state = verificar_laboratorio()
    exigir(state == "exited", "Detener laboratorio antes del cierre")
    image = leer(raw / "imagen_y_mounts.json")
    exigir(image["run_id"] == run_id and image["commit_tested"] == meta["commit_tested"]
           and image["image_id"] == meta["image_id"], "Empaquetado de otra ejecución")
    # Preservación de originales, incluyendo secretos: solo hashes, nunca contenido.
    allowed = {".gitattributes", "README.md", "PLAN_REESTRUCTURACION_POR_FASES.md", "GUIA_DE_PRUEBAS_PARA_EL_EQUIPO.md", "INSTRUCCIONES_RAPIDAS_ZIP.md", "apps/backend/.dockerignore", "apps/frontend/.dockerignore", "apps/backend/scripts/exportar_csv.py", "apps/frontend/tests/validar_diseno.py", "docs/migracion/fase-02/README.md"}
    prep = leer(HERE / "preparacion.json")
    changed = [e["path"] for e in prep["files"] if not (ROOT / e["path"]).is_file() or sha(ROOT / e["path"]) != e["sha256"]]
    exigir(set(changed) <= allowed, "Cambios inesperados respecto al inventario inicial")
    inventory = leer(ROOT / "data/manifests/inventario-fase-03.v1.json")
    for record in inventory["files"]:
        exigir(sha(ROOT / record["source"]) == sha(ROOT / record["destination"]) == record["sha256"], "Muestra/modelo alterado")
    public.mkdir(parents=True, exist_ok=False)
    escribir(public / "ejecucion.json", meta)
    escribir(public / "acciones.json", acciones)
    escribir(public / "imagen_y_mounts.json", image)
    # Resumen funcional por allowlist: no publicar tokens, URLs ni rechazos detallados.
    importer = leer(raw / "importacion_canonica.json")
    safe = {k: importer[k] for k in ("reference_clock", "database_initial_counts", "model_hash_unchanged", "prediction_parity", "openapi_unchanged", "database_isolated")}
    safe["samples"] = [{k: s[k] for k in ("archivo", "recibidas", "aceptables_sin_duplicados_bd", "rechazadas")} for s in importer["samples"]]
    safe["uploads"] = [{"archivo": u["archivo"], "bom": u["bom"], "rollback_verified": u["rollback_verified"],
                        "primera_carga": {k: u["primera_carga"][k] for k in ("recibidas", "aceptadas", "rechazadas")},
                        "segunda_carga": u["segunda_carga"]} for u in importer["uploads"]]
    escribir(public / "importacion_canonica.json", safe)
    escribir(public / "cobertura.json", leer(raw / "backend_coverage.json")["totals"])
    for name in ("unitarias", "backend_diagnostico", "backend_completo"):
        junit_publico(raw / f"{name}.xml", public / f"{name}.xml")
    for name in ("diagnostico", "completo"):
        junit_publico(HERE.parent / f"fase-02/backend_despues_{name}.xml", public / f"baseline_{name}.xml")
    results = comparar(public)
    summary = {"run_id": run_id, "commit_tested": meta["commit_tested"], "image_id": meta["image_id"],
               "results": results, "original_files_examined": len(prep["files"]),
               "expected_modified_files": changed, "laboratory": {"db": lab["db"], "volume": lab["volume"], "state": state},
               "public_evidence": [{"path": p.name, "sha256": sha(p)} for p in sorted(public.iterdir())],
               "raw_evidence": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)} for p in sorted(raw.iterdir()) if p.is_file()]}
    escribir(public / "verificacion.json", summary)
    verificar_portable(run_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--verify-only", action="store_true", help="Solo evidencia pública y fuentes; no requiere Docker, modelo ni .env")
    args = parser.parse_args()
    if args.verify_only:
        verificar_portable(args.run_id)
    else:
        cerrar(args.run_id)


if __name__ == "__main__":
    main()
