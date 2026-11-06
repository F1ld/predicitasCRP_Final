"""Operaciones componibles de identidad. El caso de uso superior confirma/revierte."""
from dataclasses import fields
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errores import Conflicto, NoEncontrado, Validacion
from app.core.security import hash_password, verify_password
from app.modules.usuarios import repository
from app.modules.usuarios.contratos import Identidad


def _proyectar(usuario) -> Identidad | None:
    if usuario is None:
        return None
    return Identidad(**{campo.name: getattr(usuario, campo.name) for campo in fields(Identidad)})


def por_id(db: Session, id_usuario: int) -> Identidad | None:
    return _proyectar(repository.por_id(db, id_usuario))


def por_correo(db: Session, correo: str) -> Identidad | None:
    return _proyectar(repository.por_correo(db, correo))


def verificar_clave(db: Session, id_usuario: int, clave: str) -> bool:
    usuario = repository.por_id(db, id_usuario)
    return usuario is not None and verify_password(clave, usuario.password_hash)


def cambiar_clave(db: Session, id_usuario: int, actual: str, nueva: str, momento: datetime) -> None:
    """Preserva conflictos, hashing y revocación; no expone la fila ni hace commit."""
    usuario = repository.por_id_para_actualizar(db, id_usuario)
    if usuario is None:
        raise NoEncontrado(f"No existe el usuario {id_usuario}")
    if not verify_password(actual, usuario.password_hash):
        raise Conflicto("La clave actual no es correcta", codigo="CLAVE_ACTUAL_INCORRECTA")
    if nueva == actual:
        raise Validacion("Los datos enviados no son válidos",
                         campos={"clave_nueva": "Debe ser distinta de la clave actual"})
    usuario.password_hash = hash_password(nueva)
    usuario.actualizado_en = momento
