from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.auditoria.models import AuditoriaEvento


def registrar_evento(
    db: Session,
    *,
    modulo: str,
    accion: str,
    entidad_afectada: str,
    direccion_ip: str,
    id_usuario: int | None = None,
    id_entidad: int | None = None,
    datos_before: dict | None = None,
    datos_after: dict | None = None,
    momento: datetime | None = None,
) -> AuditoriaEvento:
    """Agrega el evento a la sesión. Quien llama decide cuándo confirmar (commit)."""
    evento = AuditoriaEvento(
        id_usuario=id_usuario, modulo=modulo, accion=accion,
        entidad_afectada=entidad_afectada, id_entidad=id_entidad,
        datos_before=datos_before, datos_after=datos_after, direccion_ip=direccion_ip,
    )
    if momento is not None:
        evento.creado_en = momento
    db.add(evento)
    return evento


def auditar(db: Session, momento: datetime, **datos):
    """Append con precisión del reloj de identidad; nunca confirma por su cuenta."""
    return registrar_evento(db, momento=momento, **datos)
