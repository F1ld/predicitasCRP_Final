"""Pruebas de archivos/CLI sin BD; todos los outputs en tmp_path."""
import csv
from datetime import date
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import exportar_csv as exportador

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent.parent


def exportar(path, **kwargs):
    return exportador.exportar_csv(path, filas=kwargs.get("filas", 3), semilla=7,
                                   fecha_referencia=kwargs.get("fecha", date(2026, 11, 5)))


def test_exportador_crea_directorio_y_trece_columnas_sin_etiqueta(tmp_path):
    path = exportar(tmp_path / "nuevo/subdir/muestra.csv")
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames) == exportador.COLUMNAS
        rows = list(reader)
    assert len(rows) == 7  # Tres válidas y cuatro rechazos, como el generador original.
    assert all(len(row) == 13 and "target_no_show" not in row for row in rows)


def test_exportador_reproducible_y_fecha_explicita_cambia_bytes(tmp_path):
    first = exportar(tmp_path / "primero.csv").read_bytes()
    assert exportar(tmp_path / "segundo.csv").read_bytes() == first
    assert exportar(tmp_path / "otra_fecha.csv", fecha=date(2026, 11, 6)).read_bytes() != first


def test_exportador_no_sobrescribe(tmp_path):
    path = tmp_path / "existente.csv"
    path.write_bytes(b"NO MODIFICAR")
    with pytest.raises(FileExistsError):
        exportar(path)
    assert path.read_bytes() == b"NO MODIFICAR"


def test_apertura_exclusiva_protege_aun_si_destino_aparece_tras_validar(tmp_path, monkeypatch):
    path = tmp_path / "concurrente.csv"
    path.write_bytes(b"OTRO PROCESO")
    monkeypatch.setattr(exportador, "resolver_salida", lambda value: value)
    with pytest.raises(FileExistsError):
        exportar(path)
    assert path.read_bytes() == b"OTRO PROCESO"


@pytest.mark.parametrize("name", ["relativo.csv", "subdir/datos.csv"])
def test_exportador_rechaza_dependencia_de_cwd(name):
    with pytest.raises(ValueError, match="absoluta"):
        exportar(Path(name))


@pytest.mark.parametrize("name", ["salida.json", "salida", "datos.joblib"])
def test_exportador_rechaza_extension(tmp_path, name):
    with pytest.raises(ValueError, match=".csv"):
        exportar(tmp_path / name)


@pytest.mark.parametrize("filas", [0, -1])
def test_exportador_rechaza_filas_no_positivas(tmp_path, filas):
    with pytest.raises(ValueError, match="mayor"):
        exportar(tmp_path / "datos.csv", filas=filas)
    assert not (tmp_path / "datos.csv").exists()


@pytest.mark.parametrize("directory", ["apps/backend", "apps/frontend/public", "data/samples", "artifacts/models", "docs"])
def test_exportador_no_escribe_en_codigo_muestras_artefactos(directory):
    with pytest.raises(ValueError):
        exportar(ROOT / directory / "no_crear_fase3.csv")
    assert not (ROOT / directory / "no_crear_fase3.csv").exists()


def test_cli_desde_otro_cwd_con_pythonpath_explicito(tmp_path):
    output = tmp_path / "externo/muestra.csv"
    result = subprocess.run([sys.executable, "-m", "scripts.exportar_csv", "--salida", str(output),
                             "--fecha-referencia", "2026-11-05", "--filas", "2"],
                            cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(BACKEND)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert output.is_file() and "SHA-256=" in result.stdout
    assert not (tmp_path / "data").exists()


def test_cli_exige_salida_y_fecha(tmp_path):
    result = subprocess.run([sys.executable, "-m", "scripts.exportar_csv"], cwd=tmp_path,
                            env={**os.environ, "PYTHONPATH": str(BACKEND)}, capture_output=True, text=True)
    assert result.returncode == 2
    assert not list(tmp_path.iterdir())


@pytest.fixture
def rutas_qa():
    spec = importlib.util.spec_from_file_location("rutas_qa_fase3", ROOT / "apps/frontend/tests/rutas_validacion.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_qa_resultados_nuevos_no_sobrescriben_y_no_usan_fixture_historico(rutas_qa, tmp_path):
    result = rutas_qa.crear_directorio_resultados("a1b2c3d4", tmp_path)
    assert result == tmp_path / "diseno/a1b2c3d4"
    (result / "evidencia.json").write_text("conservar", encoding="utf-8")
    with pytest.raises(FileExistsError):
        rutas_qa.crear_directorio_resultados("a1b2c3d4", tmp_path)
    assert (result / "evidencia.json").read_text(encoding="utf-8") == "conservar"


@pytest.mark.parametrize("marca", ["../subir", "", "../../xx", "abcdefgh"])
def test_qa_rechaza_traversal(rutas_qa, tmp_path, marca):
    with pytest.raises(ValueError):
        rutas_qa.crear_directorio_resultados(marca, tmp_path)


def test_qa_rechaza_ruta_relativa_y_fuente(rutas_qa):
    for base in (Path("relativo"), ROOT / "apps/frontend/tests/fixtures", ROOT / "data"):
        with pytest.raises(ValueError):
            rutas_qa.crear_directorio_resultados("a1b2c3d4", base)


def test_qa_configuracion_externa_absoluta(rutas_qa, tmp_path, monkeypatch):
    monkeypatch.setenv("PREDICITAS_TEST_RESULTS_DIR", str(tmp_path))
    assert rutas_qa.crear_directorio_resultados("00112233") == tmp_path / "diseno/00112233"


@pytest.mark.parametrize("actual,expected", [("predicitas", None), ("predicitas", "predicitas"), ("predicitas_crp", "predicitas_crp"), ("predicitas_test", "otra_test"), ("contest", "contest")])
def test_qa_no_conecta_a_principal_ni_base_no_confirmada(rutas_qa, actual, expected):
    with pytest.raises(ValueError):
        rutas_qa.validar_base_pruebas(actual, expected)


def test_qa_admite_solo_nombre_test_explicito(rutas_qa):
    rutas_qa.validar_base_pruebas("predicitas_fase3_test", "predicitas_fase3_test")


def test_importacion_limpia_validar_diseno_sin_efectos_secundarios():
    """Importar apps.frontend.tests.validar_diseno en subproceso no debe tener efectos secundarios:
    no cambia el CWD, no crea directorios en runtime/test-results/diseno, no abre conexiones ni falla.
    Lanzado con cwd=ROOT y PYTHONPATH=ROOT para resolver en cualquier entorno (host y contenedor)."""
    diseno_dir = ROOT / "runtime/test-results/diseno"
    dirs_before = set(diseno_dir.iterdir()) if diseno_dir.exists() else set()

    codigo = (
        "import os\n"
        "cwd_antes = os.path.realpath(os.getcwd())\n"
        "import sys\n"
        "path_antes = list(sys.path)\n"
        "import apps.frontend.tests.validar_diseno as vd\n"
        "cwd_despues = os.path.realpath(os.getcwd())\n"
        "print('CWD_ANTES:' + cwd_antes)\n"
        "print('CWD_DESPUES:' + cwd_despues)\n"
        "assert cwd_antes == cwd_despues, f'{cwd_antes} != {cwd_despues}'\n"
        "assert sys.path == path_antes, 'Import cambió sys.path'\n"
        "assert hasattr(vd, 'main'), 'validar_diseno debe exponer funcion main'\n"
    )

    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    res = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Fallo al importar: {res.stderr}\nStdout: {res.stdout}"
    assert "CWD_ANTES:" in res.stdout
    assert "CWD_DESPUES:" in res.stdout

    dirs_after = set(diseno_dir.iterdir()) if diseno_dir.exists() else set()
    assert dirs_before == dirs_after, f"Se crearon directorios al importar: {dirs_after - dirs_before}"


def test_main_qa_valida_antes_de_crear_y_crea_solo_al_ejecutar(tmp_path):
    """Camino positivo acotado: conexión simulada corta antes de usar BD/servidor."""
    codigo = r'''
import os
from pathlib import Path
from unittest.mock import Mock, patch
import apps.frontend.tests.validar_diseno as vd
from app.core import database

base = Path(os.environ["PREDICITAS_TEST_RESULTS_DIR"])
engine = Mock()
engine.url.database = "predicitas_fase3_test"
class FinSimulado(Exception):
    pass
engine.connect.side_effect = FinSimulado
with patch.object(database, "engine", engine):
    try:
        vd.main()
    except ValueError:
        pass
    else:
        raise AssertionError("Debió rechazar la BD no confirmada")
    assert not list(base.iterdir()), "La guarda creó resultados"
    engine.connect.assert_not_called()
    os.environ["PREDICITAS_QA_DATABASE_NAME"] = "predicitas_fase3_test"
    with patch.object(vd.uuid, "uuid4") as uuid:
        uuid.return_value.hex = "a1b2c3d4" * 4
        try:
            vd.main()
        except FinSimulado:
            pass
        else:
            raise AssertionError("No se llegó a la conexión simulada")
    engine.connect.assert_called_once_with()
    assert (base / "diseno/a1b2c3d4").is_dir()
'''
    env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(ROOT), str(BACKEND))),
           "PREDICITAS_TEST_RESULTS_DIR": str(tmp_path)}
    env.pop("PREDICITAS_QA_DATABASE_NAME", None)
    result = subprocess.run([sys.executable, "-c", codigo], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_invariantes_centralizacion_y_manifiesto():
    """Valida los invariantes de centralización:
    1. Las copias de compatibilidad legacy son byte-a-byte idénticas al canónico.
    2. El inventario data/manifests/inventario-fase-03.v1.json coincide con los archivos en disco.
    3. Ningún módulo operativo en apps/backend/app referencia rutas legacy de CSV."""
    import json
    import hashlib

    # 1. Comparación byte a byte de muestras canónicas vs copias de compatibilidad
    canon_variado = ROOT / "data/samples/importacion/citas_para_importar_variado.csv"
    raiz_variado = ROOT / "citas_para_importar_variado.csv"
    backend_variado = ROOT / "apps/backend/data/citas_para_importar_variado.csv"

    assert canon_variado.is_file(), "Muestra canónica variado no encontrada"
    assert canon_variado.read_bytes() == raiz_variado.read_bytes(), "Copia en raíz difiere del canónico variado"
    assert canon_variado.read_bytes() == backend_variado.read_bytes(), "Copia en apps/backend/data difiere del canónico variado"

    canon_demo = ROOT / "data/samples/importacion/citas_demo.csv"
    backend_demo = ROOT / "apps/backend/data/citas_demo.csv"

    assert canon_demo.is_file(), "Muestra canónica demo no encontrada"
    assert canon_demo.read_bytes() == backend_demo.read_bytes(), "Copia en apps/backend/data difiere del canónico demo"

    # 2. Validación de concordancia con el manifiesto
    manifiesto_path = ROOT / "data/manifests/inventario-fase-03.v1.json"
    assert manifiesto_path.is_file(), "Manifiesto inventario no encontrado"
    inventario = json.loads(manifiesto_path.read_text(encoding="utf-8"))

    for item in inventario.get("files", []):
        dest = ROOT / item["destination"]
        assert dest.is_file(), f"Archivo registrado en inventario no existe: {dest}"
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        assert digest.lower() == item["sha256"].lower(), f"Hash en disco difiere del manifiesto para {dest}"

    # 3. Guardia de centralización: ningún archivo en apps/backend/app debe referenciar rutas legacy de datos
    app_dir = ROOT / "apps/backend/app"
    patrones_prohibidos = ["apps/backend/data", "citas_demo.csv", "citas_para_importar_variado.csv"]
    for py_file in app_dir.rglob("*.py"):
        texto = py_file.read_text(encoding="utf-8")
        for patron in patrones_prohibidos:
            assert patron not in texto, f"Ruta legacy '{patron}' referenciada en código operacional: {py_file.relative_to(ROOT)}"
