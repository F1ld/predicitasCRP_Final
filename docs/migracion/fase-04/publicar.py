"""Publica resumen y JUnit sanitizados del bloque A; nunca publica env/logs crudos.

--verify-only verifica el paquete de evidencia, no ejecuta tests ni certifica que
un árbol de trabajo posterior equivalga a las fuentes probadas.
"""
import argparse
import xml.etree.ElementTree as ET

from validar import HERE, ROOT, escribir, fuentes, leer, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    import re
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,40}", args.run_id):
        raise ValueError("run-id inválido")
    target = HERE / "evidencia" / args.run_id
    if args.verify_only:
        manifest = leer(target / "manifest.json")
        assert manifest["run_id"] == args.run_id
        for item in manifest["files"]:
            path = target / item["name"]
            if path.parent != target or sha(path) != item["sha256"]:
                raise ValueError("Paquete de evidencia alterado")
        print("Integridad del paquete de evidencia comprobada; no es una nueva ejecución de pruebas.")
        return
    raw = ROOT / "runtime/test-results/fase-04" / args.run_id
    summary = leer(raw / "resumen.json")
    assert summary["laboratory_state"] == "exited"
    assert summary["source_files"] == fuentes(ROOT)
    assert all(summary["parity"].values()) and summary["protected_unchanged"]
    assert not summary["changed_old_cases"] and set(summary["new_cases"].values()) == {"passed"}
    assert summary["coverage_percent"] >= 75 and summary["complete_collection_unchanged"]
    assert len(set(summary["complete_exit_codes"].values())) == 1
    if "b1_rollback" in summary:
        assert summary["b1_rollback"]["rollback_visible_from_independent_connection"]
    target.mkdir(parents=True, exist_ok=False)
    escribir(target / "resumen.json", summary)
    names = ["baseline_diagnostico", "actual_diagnostico", "baseline_completo", "actual_completo"]
    if "b1_rollback" in summary:
        names.append("b1_focalizadas")
    for name in names:
        original = raw / f"{name}.xml"
        root = ET.Element("testsuite")
        for case in ET.parse(original).iter("testcase"):
            clean = ET.SubElement(root, "testcase", {key: case.attrib[key] for key in ("classname", "name") if key in case.attrib})
            for state in ("failure", "error", "skipped"):
                if case.find(state) is not None:
                    ET.SubElement(clean, state, {"message": "Ver diagnóstico privado; estado preservado"})
        with (target / f"{name}.xml").open("xb") as stream:
            stream.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    manifest = {"run_id": args.run_id, "note": "Resultados del árbol con hashes; sin commit automático",
                "files": [{"name": p.name, "sha256": sha(p)} for p in sorted(target.iterdir())]}
    escribir(target / "manifest.json", manifest)
    print("Resumen y JUnit sanitizados publicados sin env ni logs privados.")


if __name__ == "__main__":
    main()
