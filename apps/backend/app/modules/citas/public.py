"""Contrato público y operaciones componibles del módulo de Citas (M02).

Proporciona lecturas desacopladas y transiciones internas sin commit (RNF-014),
garantizando que cada cambio de estado legal genere exactamente un historial
y la auditoría requerida por el caso de uso coordinador.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errores import NoEncontrado, TransicionInvalida
from app.modules.auth.public import Principal as Usuario
from app.modules.citas.models import Cita
from app.modules.citas.reglas import ESTADOS_ACTIVOS, TRANSICIONES, puede_transicionar_a_liberada


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


def _snapshot(cita: Cita) -> CitaConsulta:
    return CitaConsulta(**{campo: getattr(cita, campo) for campo in CitaConsulta.__dataclass_fields__})


def obtener_cita_consulta(db: Session, id_cita: int, *, bloquear: bool = False) -> CitaConsulta | None:
    """Consulta de lectura de una cita sin exponer la fila ORM mutada."""
    cita = db.get(Cita, id_cita, with_for_update=True) if bloquear else db.get(Cita, id_cita)
    if cita is None:
        return None
    return _snapshot(cita)


def permite_confirmacion_por_intervencion(estado: str) -> bool:
    return "CONFIRMADA" in TRANSICIONES.get(estado, set())


def permite_liberacion_por_intervencion(estado: str) -> bool:
    return puede_transicionar_a_liberada(estado)


def obtener_metadatos_cita_para_cupo(db: Session, id_cita: int) -> tuple[str, str] | None:
    """Retorna (id_cita_externa, franja_horaria) para detalles o emparejamiento de cupos."""
    cita = db.get(Cita, id_cita)
    if cita is None:
        return None
    return cita.id_cita_externa, cita.franja_horaria


def transicionar_cita_interno(
    db: Session,
    id_cita: int,
    estado_nuevo: str,
    *,
    usuario: Usuario,
    ip: str,
    motivo: str | None = None,
    extra_despues: dict | None = None,
    registrar_auditoria: bool = True,
) -> CitaConsulta:
    """Aplica una transición legal sobre la cita, agrega historial y audita.

    NO hace commit (RNF-014). El caso de uso coordinador es responsable de
    cerrar la transacción.
    """
    # Igual que el contrato histórico: reprogramar necesita fecha y variables
    # derivadas; solo el caso de uso M02-E05 puede hacerlo.
    if estado_nuevo == "REPROGRAMADA":
        raise TransicionInvalida("REPROGRAMADA exige nueva_fecha_hora_cita: use POST /citas/{id_cita}/estado")
    cita = db.get(Cita, id_cita, with_for_update=True)
    if cita is None:
        raise NoEncontrado(f"No existe la cita {id_cita}")

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
    return _snapshot(cita)


def transicionar(
    db: Session,
    id_cita: int,
    estado_nuevo: str,
    *,
    usuario: Usuario,
    ip: str,
    motivo: str | None = None,
) -> None:
    """Entrada pública por ID; el servicio interno conserva su contrato ORM histórico."""
    transicionar_cita_interno(db, id_cita, estado_nuevo, usuario=usuario, ip=ip, motivo=motivo)
