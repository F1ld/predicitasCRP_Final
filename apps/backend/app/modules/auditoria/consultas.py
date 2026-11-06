"""Consultas de sesión sobre la bitácora propia, sin writes ni commit."""
from datetime import datetime
from copy import deepcopy
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auditoria.models import AuditoriaEvento


@dataclass(frozen=True)
class EventoEntidad:
    id_log: int
    accion: str
    id_usuario: int | None
    creado_en: datetime
    datos_after: dict


def eventos_entidad(db: Session, *, modulo: str, entidad: str, id_entidad: int,
                    acciones: tuple[str, ...]) -> list[EventoEntidad]:
    """Proyección de bitácora: orden causal por ID, sin entregar ORM mutable."""
    rows = db.scalars(select(AuditoriaEvento).where(
        AuditoriaEvento.modulo == modulo, AuditoriaEvento.entidad_afectada == entidad,
        AuditoriaEvento.id_entidad == id_entidad, AuditoriaEvento.accion.in_(acciones),
    ).order_by(AuditoriaEvento.id_log))
    return [EventoEntidad(r.id_log, r.accion, r.id_usuario, r.creado_en, deepcopy(r.datos_after or {})) for r in rows]


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
