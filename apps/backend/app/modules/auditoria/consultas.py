"""Consultas de sesión sobre la bitácora propia, sin writes ni commit."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auditoria.models import AuditoriaEvento


def _logins(id_usuario: int):
    return (AuditoriaEvento.id_usuario == id_usuario) & (AuditoriaEvento.accion == "LOGIN")


def fallos_recientes(db: Session, id_usuario: int, desde: datetime, limite: int) -> list[datetime]:
    """Fallos posteriores al último éxito, desde el más reciente (D-009)."""
    ultimo_exito = db.scalar(
        select(func.max(AuditoriaEvento.creado_en))
        .where(_logins(id_usuario), AuditoriaEvento.datos_after["resultado"].astext == "EXITOSO")
    )
    consulta = (
        select(AuditoriaEvento.creado_en)
        .where(_logins(id_usuario), AuditoriaEvento.creado_en >= desde,
               AuditoriaEvento.datos_after["resultado"].astext == "FALLIDO")
        .order_by(AuditoriaEvento.creado_en.desc())
        .limit(limite)
    )
    if ultimo_exito is not None:
        consulta = consulta.where(AuditoriaEvento.creado_en > ultimo_exito)
    return list(db.scalars(consulta))


def hay_logout_desde(db: Session, id_usuario: int, momento: datetime) -> bool:
    return db.scalar(
        select(AuditoriaEvento.id_log)
        .where(AuditoriaEvento.id_usuario == id_usuario, AuditoriaEvento.accion == "LOGOUT",
               AuditoriaEvento.creado_en >= momento)
        .limit(1)
    ) is not None
