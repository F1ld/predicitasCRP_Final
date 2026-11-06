"""Contrato público y operaciones componibles del módulo de Citas (M02).

Proporciona lecturas desacopladas y transiciones internas sin commit (RNF-014),
garantizando que cada cambio de estado legal genere exactamente un historial
y la auditoría requerida por el caso de uso coordinador.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errores import NoEncontrado
from app.modules.auth.public import Principal as Usuario
from app.modules.citas.models import Cita


@dataclass(frozen=True)
class CitaConsulta:
    id_cita: int
    id_cita_externa: str
    paciente_anon_id: str
    especialidad: str
    medico: str
    fecha_hora_cita: datetime
    estado_actual: str
    franja_horaria: str


def obtener_cita_consulta(db: Session, id_cita: int) -> CitaConsulta | None:
    """Consulta de lectura de una cita sin exponer la fila ORM mutada."""
    cita = db.get(Cita, id_cita)
    if cita is None:
        return None
    return CitaConsulta(
        id_cita=cita.id_cita,
        id_cita_externa=cita.id_cita_externa,
        paciente_anon_id=cita.paciente_anon_id,
        especialidad=cita.especialidad,
        medico=cita.medico,
        fecha_hora_cita=cita.fecha_hora_cita,
        estado_actual=cita.estado_actual,
        franja_horaria=cita.franja_horaria,
    )


def obtener_metadatos_cita_para_cupo(db: Session, id_cita: int) -> tuple[str, str] | None:
    """Retorna (id_cita_externa, franja_horaria) para detalles o emparejamiento de cupos."""
    cita = db.get(Cita, id_cita)
    if cita is None:
        return None
    return cita.id_cita_externa, cita.franja_horaria


def transicionar_cita_interno(
    db: Session,
    cita_o_id: Cita | int,
    estado_nuevo: str,
    *,
    usuario: Usuario,
    ip: str,
    motivo: str | None = None,
    extra_despues: dict | None = None,
    registrar_auditoria: bool = True,
    with_for_update: bool = True,
) -> Cita:
    """Aplica una transición legal sobre la cita, agrega historial y audita.

    NO hace commit (RNF-014). El caso de uso coordinador es responsable de
    cerrar la transacción.
    """
    if isinstance(cita_o_id, int):
        cita = db.get(Cita, cita_o_id, with_for_update=with_for_update)
        if cita is None:
            raise NoEncontrado(f"No existe la cita {cita_o_id}")
    else:
        cita = cita_o_id

    from app.modules.citas.service import _aplicar_transicion, _foto
    _aplicar_transicion(
        db,
        cita,
        estado_nuevo,
        usuario=usuario,
        ip=ip,
        motivo=motivo,
        antes=_foto(cita),
        extra_despues=extra_despues,
        registrar_auditoria=registrar_auditoria,
    )
    return cita


def transicionar(
    db: Session,
    cita: Cita,
    estado_nuevo: str,
    *,
    usuario: Usuario,
    ip: str,
    motivo: str | None = None,
) -> None:
    """Shim de compatibilidad con el servicio interno histórico (contratos/comun.json)."""
    from app.modules.citas.service import transicionar as _transicionar
    _transicionar(db, cita, estado_nuevo, usuario=usuario, ip=ip, motivo=motivo)
