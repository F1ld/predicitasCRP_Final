"""Contrato público y operaciones componibles del módulo de Intervenciones (M05)."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.intervenciones import reglas
from app.modules.intervenciones.models import Intervencion


@dataclass(frozen=True)
class IntervencionSnapshot:
    id_intervencion: int
    id_cita: int
    canal_contacto: str
    estado_intervencion: str
    respuesta_paciente: str | None
    consentimiento_optout: bool
    fecha_hora_envio: datetime | None
    fecha_hora_respuesta: datetime | None


def validar_intervencion_de_cita(db: Session, id_intervencion: int, id_cita: int) -> bool:
    """Valida si la intervención existe y pertenece a la cita especificada."""
    inter = db.get(Intervencion, id_intervencion)
    return inter is not None and inter.id_cita == id_cita


def acciones_disponibles_intervencion(
    estado_intervencion: str,
    canal_contacto: str,
    respuesta_paciente: str | None,
    consentimiento_optout: bool,
    estado_cita: str,
) -> list[str]:
    """Expone el cálculo canónico de acciones disponibles de M05."""
    return reglas.acciones_disponibles(
        estado_intervencion,
        canal_contacto,
        respuesta_paciente,
        consentimiento_optout,
        estado_cita,
    )
