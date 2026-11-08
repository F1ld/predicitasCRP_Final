"""Controles del harness, sin Docker, red ni BD."""
import importlib.util
from pathlib import Path
import sys

import pytest

@pytest.fixture
def herramientas(monkeypatch):
    tools = next((parent / "docs/migracion/fase-03" for parent in Path(__file__).resolve().parents
                  if (parent / "docs/migracion/fase-03/evidencia.py").is_file()), None)
    if tools is None:
        pytest.skip("El verificador de evidencia requiere el árbol del repositorio")
    monkeypatch.syspath_prepend(str(tools))
    modules = []
    for name in ("evidencia", "verificar_cierre"):
        spec = importlib.util.spec_from_file_location(name, tools / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


@pytest.mark.parametrize("run_id", ["../fuera", "x", "a/b", "a\\b", "A123"])
def test_run_id_rechaza_rutas_y_valores_invalidos(herramientas, run_id):
    with pytest.raises(ValueError):
        herramientas[0].destinos(run_id)


def test_evidencia_exclusiva_no_sobrescribe(herramientas, tmp_path):
    evidencia, _ = herramientas
    path = tmp_path / "resultado.json"
    evidencia.escribir(path, {"original": True})
    before = path.read_bytes()
    assert b"\r" not in before, "La evidencia pública debe tener LF también en Windows"
    with pytest.raises(FileExistsError):
        evidencia.escribir(path, {"original": False})
    assert path.read_bytes() == before


def test_run_ausente_no_recurre_a_final(herramientas, tmp_path, monkeypatch):
    evidencia, _ = herramientas
    monkeypatch.setattr(evidencia, "ROOT", tmp_path)
    monkeypatch.setattr(evidencia, "HERE", tmp_path / "docs")
    legacy = tmp_path / "runtime/test-results/fase-03/ejecucion_final.json"
    evidencia.escribir(legacy, {"run_id": "otro"})
    with pytest.raises(FileNotFoundError):
        evidencia.cargar_run("ausente", comprobar_codigo=False)


def test_junit_publico_no_expone_logs_propiedades_ni_tracebacks(herramientas, tmp_path):
    _, cierre = herramientas
    source = tmp_path / "privado.xml"
    source.write_text('<testsuite><properties><property name="password" value="SECRETO"/></properties>'
                      '<testcase classname="tests.ejemplo" name="caso"><failure message="SECRETO">SECRETO</failure>'
                      '<system-out>SECRETO</system-out></testcase></testsuite>', encoding="utf-8")
    target = tmp_path / "publico.xml"
    cierre.junit_publico(source, target)
    assert "SECRETO" not in target.read_text()
    assert cierre.junit(target) == cierre.junit(source)


def test_clon_verifica_hashes_antes_de_aceptar_resumen(herramientas, tmp_path, monkeypatch):
    evidencia, cierre = herramientas
    monkeypatch.setattr(cierre, "destinos", lambda run: (tmp_path / "raw", tmp_path / "public"))
    public = tmp_path / "public"
    evidencia.escribir(public / "ejecucion.json", {"original": True})
    digest = evidencia.sha(public / "ejecucion.json")
    evidencia.escribir(public / "verificacion.json", {"run_id": "prueba", "public_evidence": [
        {"path": "ejecucion.json", "sha256": digest}]})
    (public / "ejecucion.json").write_text('{}', encoding="utf-8")
    with pytest.raises(ValueError, match="Evidencia alterada"):
        cierre.verificar_portable("prueba")
