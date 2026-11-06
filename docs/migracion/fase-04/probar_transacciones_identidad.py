"""Persistencia entre conexiones independientes, SOLO en laboratorio nuevo fase 4."""
from datetime import timedelta
import json
from pathlib import Path
import sys
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select, text

from app.core.database import SessionLocal, engine
from app.core.errores import DemasiadosIntentos, NoAutenticado
from app.core import reloj
from app.core.security import hash_password
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.auth import service
from app.modules.usuarios import public as identidad
from app.modules.usuarios.models import Usuario


def main():
    if engine.url.database != "predicitas_fase4_test" or not engine.url.host.startswith("predicitas-fase4-"):
        raise SystemExit("Destino no autorizado")
    with SessionLocal() as db:
        assert db.scalar(text("select current_database()")) == "predicitas_fase4_test"
        assert db.scalar(text("select current_user")) == "predicitas_app"
        correo = f"fase4-{uuid4().hex}@predicitas.crp"
        usuario = Usuario(nombre_completo="QA aislado fase 4", correo_institucional=correo,
                          password_hash=hash_password("ClaveInicial2026"), rol="TECNICO_IA", activo=True)
        db.add(usuario)
        db.commit()
        id_usuario = usuario.id_usuario
    inicio = reloj.ahora()
    for n in range(5):
        with patch("app.core.reloj.ahora", return_value=inicio + timedelta(seconds=n)):
            with SessionLocal() as db:
                try:
                    service.autenticar(db, correo, "Incorrecta2026", "127.0.0.1")
                except NoAutenticado:
                    pass
                else:
                    raise AssertionError("Se esperaba rechazo 401")
        # Una conexión distinta ve el evento después de cerrar la petición fallida.
        with SessionLocal() as db:
            eventos = list(db.scalars(select(AuditoriaEvento).where(
                AuditoriaEvento.id_usuario == id_usuario, AuditoriaEvento.accion == "LOGIN")))
            assert len(eventos) == n + 1
            assert all(e.datos_after["resultado"] == "FALLIDO" for e in eventos)
    with patch("app.core.reloj.ahora", return_value=inicio + timedelta(seconds=5)):
        with SessionLocal() as db:
            try:
                service.autenticar(db, correo, "ClaveInicial2026", "127.0.0.1")
            except DemasiadosIntentos:
                pass
            else:
                raise AssertionError("Se esperaba bloqueo 429")
    with SessionLocal() as db:
        ultimo = db.scalar(select(AuditoriaEvento).where(AuditoriaEvento.id_usuario == id_usuario)
                           .order_by(AuditoriaEvento.id_log.desc()).limit(1))
        assert ultimo.datos_after["resultado"] == "BLOQUEADO"

    def fallar_auditoria(db, *args, **kwargs):
        db.flush()
        raise RuntimeError("Fallo tras flush de contraseña")
    try:
        with SessionLocal() as db:
            principal = identidad.por_id(db, id_usuario)
            with patch("app.modules.auth.service.auditar", side_effect=fallar_auditoria):
                service.cambiar_clave(db, principal, "ClaveInicial2026", "ClaveNueva2026", "127.0.0.1")
    except RuntimeError as exc:
        assert str(exc) == "Fallo tras flush de contraseña"
    else:
        raise AssertionError("No se inyectó el fallo")
    with SessionLocal() as db:
        assert identidad.verificar_clave(db, id_usuario, "ClaveInicial2026")
        assert not identidad.verificar_clave(db, id_usuario, "ClaveNueva2026")
        assert identidad.por_id(db, id_usuario).actualizado_en is None
        assert db.scalar(select(AuditoriaEvento.id_log).where(
            AuditoriaEvento.id_usuario == id_usuario, AuditoriaEvento.accion == "CAMBIO_CLAVE")) is None
    result = {"failed_login_commits_visible_from_other_connections": 5,
              "blocked_login_commit_visible_from_other_connection": True,
              "password_rollback_after_flush_verified_from_other_connection": True,
              "database": "predicitas_fase4_test", "runtime_role": "predicitas_app",
              "preservation": "Cuenta sintética QA conservada solo en el volumen nuevo de pruebas"}
    with Path(sys.argv[1]).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print("Persistencia de fallos/bloqueo y rollback de contraseña comprobados entre conexiones.")


if __name__ == "__main__":
    main()
