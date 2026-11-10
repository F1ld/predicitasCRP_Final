"""Gates D: límites completos, DAG de imports y composición reversible."""
import ast
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app.bootstrap.limites import COMPATIBILIDAD, LECTURAS
from app.core.transacciones import bloquear_fila

APP = Path(__file__).resolve().parents[2] / "app"


def imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if not node.level:
                yield from (f"{node.module}.{a.name}" for a in node.names)


def test_limites_entre_todos_los_modulos_solo_public_o_lecturas_explicitas():
    root = APP / "modules"
    for path in root.rglob("*.py"):
        if path.parent == root:
            continue  # __init__.py del paquete, no un módulo de negocio
        area = path.relative_to(root).parts[0]
        relative = path.relative_to(root).as_posix()
        # Panel es un lector HTTP sin consumidor interno: no crear public.py vacío.
        assert (root / area / "public.py").is_file() or area == "panel"
        for name in imports(path):
            parts = name.split(".")
            if len(parts) > 3 and parts[:2] == ["app", "modules"] and parts[2] != area:
                prefix = ".".join(parts[:4])
                assert parts[3] == "public" or (relative, prefix) in COMPATIBILIDAD or (
                    parts[3] == "models" and parts[2] in LECTURAS.get(relative, set())), (relative, name)


@pytest.mark.parametrize("relative", sorted(LECTURAS))
def test_adaptadores_de_lectura_no_mutan_ni_confirman(relative):
    tree = ast.parse((APP / "modules" / relative).read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"add", "add_all", "delete", "commit", "rollback", "flush", "update", "values"}
        if isinstance(node, ast.Assign):
            assert all(not isinstance(t, ast.Attribute) for t in node.targets)


def test_workflows_solo_componen_contratos_y_no_hacen_commit():
    for path in (APP / "workflows").glob("*.py"):
        for target in imports(path):
            parts = target.split(".")
            if parts[:2] == ["app", "modules"]:
                assert parts[3] == "public", (path.name, target)
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr in {"commit", "begin", "begin_nested"} for n in ast.walk(tree))


def test_imports_de_aplicacion_sin_ciclos_incluyendo_imports_locales():
    modules = {"app." + p.relative_to(APP).with_suffix("").as_posix().replace("/", "."): p
               for p in APP.rglob("*.py") if p.name != "__init__.py"}
    graph = {}
    for name, path in modules.items():
        targets = set()
        for target in imports(path):
            while target and target not in modules:
                target = target.rpartition(".")[0]
            if target and target != name:
                targets.add(target)
        graph[name] = targets
    visiting, visited = [], set()
    def visit(name):
        assert name not in visiting, " -> ".join(visiting + [name])
        if name in visited:
            return
        visiting.append(name)
        for target in sorted(graph[name]):
            visit(target)
        visiting.pop()
        visited.add(name)
    for name in sorted(graph):
        visit(name)


def test_lock_siempre_refresca_identity_map():
    db = Mock()
    db.identity_map = {}
    db.dirty = set()
    from app.modules.citas.models import Cita
    bloquear_fila(db, Cita, 7)
    db.get.assert_called_once_with(Cita, 7, with_for_update=True, populate_existing=True)


def test_transiciones_compuestas_conservan_cambio_propio_sin_commit(db, usuarios, monkeypatch):
    from app.modules.citas import public
    from app.modules.citas.models import Cita, HistorialEstadoCita
    from tests.intervenciones.conftest import crear_cita
    cita = crear_cita(db, nivel=None)
    with db.begin_nested() as savepoint:
        monkeypatch.setattr(db, "commit", lambda: pytest.fail("Contrato componible hizo commit"))
        public.transicionar_cita_interno(db, cita.id_cita, "CONFIRMADA", usuario=usuarios["RECEPCION"], ip="127.0.0.1")
        public.transicionar_cita_interno(db, cita.id_cita, "LIBERADA", usuario=usuarios["RECEPCION"], ip="127.0.0.1")
        db.flush()
        hist = list(db.scalars(select(HistorialEstadoCita).where(HistorialEstadoCita.id_cita == cita.id_cita)
                              .order_by(HistorialEstadoCita.id_historial)))
        assert [(h.estado_anterior, h.estado_nuevo) for h in hist][-2:] == [("RECIBIDA", "CONFIRMADA"), ("CONFIRMADA", "LIBERADA")]
        savepoint.rollback()
    assert db.get(Cita, cita.id_cita).estado_actual == "RECIBIDA"


def test_importador_componible_revierte_sin_begin_ni_commit(db, usuarios, monkeypatch):
    from app.modules.citas.public import importar_citas_interno
    from app.modules.citas.models import Cita
    from tests.intervenciones.conftest import BASE, HOY
    with db.begin_nested() as savepoint:
        monkeypatch.setattr(db, "commit", lambda: pytest.fail("Importador componible hizo commit"))
        result = importar_citas_interno(db, [{**BASE, "id_cita_externa": "CIT-D-IMPORT"}],
            id_usuario=usuarios["RECEPCION"].id_usuario, ip="127.0.0.1", origen="QA D", ahora=HOY)
        assert result.aceptadas == 1
        db.flush()
        assert db.scalar(select(Cita).where(Cita.id_cita_externa == "CIT-D-IMPORT")) is not None
        savepoint.rollback()
    assert db.scalar(select(Cita).where(Cita.id_cita_externa == "CIT-D-IMPORT")) is None
