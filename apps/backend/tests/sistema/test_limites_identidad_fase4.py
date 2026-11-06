"""Límites del bloque A, no certificación de todos los módulos de fase 4."""
import ast
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect

from app.core import reloj
from app.modules.auth import service as auth
from app.modules.auth.public import Principal
from app.modules.usuarios import public as identidad
from app.modules.usuarios.models import Usuario
from tests.conftest import CLAVE, cabecera

APP = Path(__file__).resolve().parents[2] / "app"


def imports(path):
    """También inspecciona imports dentro de funciones y from ... import privado."""
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.count(".") == 2 and module.startswith("app.modules."):
                yield from (f"{module}.{alias.name}" for alias in node.names)
            else:
                yield module


@pytest.mark.parametrize("area", ["auth", "usuarios", "auditoria"])
def test_identidad_solo_consume_contratos_publicos_ajenos(area):
    # Shim histórico, no código de negocio: debe ser una sola clase ORM canónica.
    excepciones = {("auth/models.py", "app.modules.usuarios.models")}
    encontrados = []
    for path in (APP / "modules" / area).glob("*.py"):
        for target in imports(path):
            parts = target.split(".")
            if len(parts) >= 4 and parts[:2] == ["app", "modules"] and parts[2] != area:
                if parts[3] != "public" and (f"{area}/{path.name}", target) not in excepciones:
                    encontrados.append((path.name, target))
    assert encontrados == []


def test_ningun_consumidor_nuevo_usa_internos_de_auth():
    encontrados = []
    for path in (APP / "modules").rglob("*.py"):
        if path.parent.name == "auth":
            continue
        for target in imports(path):
            if target.startswith("app.modules.auth.") and target != "app.modules.auth.public":
                encontrados.append((str(path.relative_to(APP)), target))
    assert encontrados == []


def test_core_tecnico_no_depende_de_negocio_salvo_shim_historico():
    encontrados = []
    for path in (APP / "core").glob("*.py"):
        if path.name == "models.py":  # compatibilidad hacia bootstrap, no registro duplicado
            continue
        encontrados.extend((path.name, name) for name in imports(path)
                           if name.startswith("app.modules.") or name.startswith("app.bootstrap"))
    assert encontrados == []


def test_ningun_modulo_importa_router_de_otro_modulo():
    encontrados = []
    for path in (APP / "modules").rglob("*.py"):
        for target in imports(path):
            parts = target.split(".")
            if (len(parts) >= 4 and parts[:2] == ["app", "modules"]
                    and parts[2] != path.parent.name and parts[3] == "router"):
                encontrados.append((str(path.relative_to(APP)), target))
    assert encontrados == []


def test_modelo_usuario_unico_con_compatibilidad_sin_otra_tabla():
    from app.bootstrap.models import Usuario as registrado
    from app.core.models import Usuario as historico
    from app.modules.auth.models import Usuario as anterior
    assert Usuario is registrado is historico is anterior
    assert Usuario.__module__ == "app.modules.usuarios.models"
    assert Usuario.__tablename__ == "usuarios"


def test_reloj_dependency_unico_sin_dependencia_entre_routers():
    from app.modules.citas.router import reloj as citas
    from app.modules.intervenciones.router import reloj as intervenciones
    assert citas is intervenciones is reloj.reloj


def test_reloj_utc_conserva_milisegundos_y_lima_offset():
    instante = reloj.ahora()
    assert instante.tzinfo == timezone.utc and instante.microsecond % 1000 == 0
    assert reloj.reloj().utcoffset().total_seconds() == -5 * 3600
    assert reloj.fecha_lima(datetime(2026, 11, 5, 2, tzinfo=timezone.utc)).isoformat() == "2026-11-04"


def test_identidad_es_inmutable_sin_hash_ni_estado_orm(db, usuarios):
    u = usuarios["RECEPCION"]
    principal = identidad.por_id(db, u.id_usuario)
    assert isinstance(principal, Principal)
    assert identidad.por_correo(db, f"  {u.correo_institucional.upper()}  ") == principal
    assert {f.name for f in fields(principal)} == {
        "id_usuario", "nombre_completo", "correo_institucional", "rol", "activo", "creado_en", "actualizado_en",
    }
    assert inspect(principal, raiseerr=False) is None
    assert not hasattr(principal, "password_hash")
    with pytest.raises(FrozenInstanceError):
        principal.rol = "ADMINISTRADOR"
    assert u.rol == "RECEPCION"


def test_consultas_identidad_inexistente_no_exponen_fila(db):
    assert identidad.por_id(db, 999999999) is None
    assert identidad.por_correo(db, "inexistente@predicitas.crp") is None
    assert identidad.verificar_clave(db, 999999999, CLAVE) is False


def test_principal_resuelto_del_token_tampoco_es_orm(client, usuarios, db):
    header = cabecera(client, usuarios["TECNICO_IA"])["Authorization"]
    principal = auth.usuario_de_token(db, header.removeprefix("Bearer "))
    assert isinstance(principal, Principal) and inspect(principal, raiseerr=False) is None
    assert not hasattr(principal, "password_hash")


def test_operacion_componible_clave_no_confirma_y_permite_rollback(db, usuarios, monkeypatch):
    u = usuarios["RECEPCION"]
    anterior = u.password_hash
    class Abortar(Exception):
        pass
    with pytest.raises(Abortar):
        with db.begin_nested():
            monkeypatch.setattr(db, "commit", lambda: pytest.fail("Operación componible hizo commit"))
            identidad.cambiar_clave(db, u.id_usuario, CLAVE, "ClaveNueva2026", reloj.ahora())
            db.flush()
            assert identidad.verificar_clave(db, u.id_usuario, "ClaveNueva2026")
            raise Abortar
    db.refresh(u)
    assert u.password_hash == anterior and u.actualizado_en is None


def test_fallo_auditoria_cambio_clave_no_deja_mutacion_parcial(db, usuarios, monkeypatch):
    u = usuarios["RECEPCION"]
    principal = identidad.por_id(db, u.id_usuario)
    anterior = u.password_hash
    def fallar(*args, **kwargs):
        db.flush()  # falla después de que la escritura alcanzó PostgreSQL
        raise RuntimeError("Fallo de auditoría inyectado")
    with pytest.raises(RuntimeError, match="inyectado"):
        with db.begin_nested():
            monkeypatch.setattr(auth, "auditar", fallar)
            auth.cambiar_clave(db, principal, CLAVE, "ClaveNueva2026", "127.0.0.1")
    db.refresh(u)
    assert u.password_hash == anterior and u.actualizado_en is None


def test_auditoria_publica_es_componible(db, usuarios, monkeypatch):
    from app.modules.auditoria.public import auditar
    from app.modules.auditoria.models import AuditoriaEvento
    from sqlalchemy import select
    class Abortar(Exception):
        pass
    with pytest.raises(Abortar):
        with db.begin_nested():
            monkeypatch.setattr(db, "commit", lambda: pytest.fail("Append hizo commit"))
            evento = auditar(db, reloj.ahora(), modulo="USUARIOS", accion="UPDATE",
                             entidad_afectada="usuarios", direccion_ip="127.0.0.1",
                             id_usuario=usuarios["RECEPCION"].id_usuario)
            db.flush()
            id_log = evento.id_log
            raise Abortar
    assert db.scalar(select(AuditoriaEvento.id_log).where(AuditoriaEvento.id_log == id_log)) is None
