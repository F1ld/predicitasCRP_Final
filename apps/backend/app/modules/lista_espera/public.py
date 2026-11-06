"""Contrato público y operaciones componibles del módulo de Lista de Espera (M06).

Proporciona operaciones de creación y consulta de cupos liberados sin commit (RNF-014),
para que los workflows de cancelación o liberación coordinen la persistencia
atómica en una sola transacción.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.modules.auditoria.public import registrar_evento
from app.modules.auth.public import Principal as Usuario
from app.modules.lista_espera.models import CupoLiberado


@dataclass(frozen=True)
class CupoLiberadoSnapshot:
    id_cupo_liberado: int
    id_cita_origen: int
    especialidad: str
    medico: str
    fecha_hora_cupo: datetime
    estado_cupo: str
    origen_liberacion: str
    liberado_en: datetime | None


def crear_cupo_liberado_interno(
    db: Session,
    *,
    id_cita_origen: int,
    especialidad: str,
    medico: str,
    fecha_hora_cupo: datetime,
    origen_liberacion: str,
    usuario: Usuario,
    ip: str,
    modulo_auditoria: str = "REASIGNACION",
    datos_after_extra: dict | None = None,
    datos_before: dict | None = None,
    fabrica_cupo: Any = None,
) -> CupoLiberado:
    """Crea y registra un cupo liberado en la sesión activa.

    NO hace commit (RNF-014). El workflow coordinador cierra la transacción.
    """
    fabrica = fabrica_cupo or CupoLiberado
    cupo = fabrica(
        id_cita_origen=id_cita_origen,
        especialidad=especialidad,
        medico=medico,
        fecha_hora_cupo=fecha_hora_cupo,
        estado_cupo="DISPONIBLE",
        origen_liberacion=origen_liberacion,
    )
    db.add(cupo)
    db.flush()

    datos_after = {
        "id_cita_origen": id_cita_origen,
        "estado_cupo": cupo.estado_cupo,
        "origen_liberacion": cupo.origen_liberacion,
        "fecha_hora_cupo": cupo.fecha_hora_cupo.isoformat(),
        **(datos_after_extra or {}),
    }
    registrar_evento(
        db,
        modulo=modulo_auditoria,
        accion="LIBERAR",
        entidad_afectada="cupos_liberados",
        direccion_ip=ip,
        id_usuario=usuario.id_usuario,
        id_entidad=cupo.id_cupo_liberado,
        datos_before=datos_before,
        datos_after=datos_after,
    )
    return cupo


def obtener_cupo_por_cita_origen(db: Session, id_cita_origen: int) -> CupoLiberado | None:
    """Obtiene el cupo liberado correspondiente a una cita de origen."""
    from app.modules.lista_espera import repository
    return repository.obtener_cupo_por_cita_origen(db, id_cita_origen)
