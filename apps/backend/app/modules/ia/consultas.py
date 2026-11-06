"""Lecturas IA autorizadas sobre Citas; nunca modifica sus filas."""
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.citas.models import Cita
from app.modules.ia.models import PrediccionIA


@dataclass(frozen=True)
class CitaInferencia:
    id_cita: int
    estado_actual: str
    especialidad: str
    tipo_paciente: str
    canal_origen: str
    franja_horaria: str
    dia_semana: str
    antelacion_dias: int
    inasistencias_previas: int
    asistencias_previas: int
    reprogramaciones_prev: int


def _snapshot(cita):
    return CitaInferencia(**{k: getattr(cita, k) for k in CitaInferencia.__dataclass_fields__})


def cita_para_inferencia(db: Session, id_cita: int):
    cita = db.get(Cita, id_cita)
    return _snapshot(cita) if cita is not None else None


def citas_operativas_sin_prediccion(db: Session, version_modelo: str, forzar: bool = False):
    stmt = select(Cita).where(Cita.estado_actual == "RECIBIDA", Cita.target_no_show.is_(None)).order_by(
        Cita.fecha_hora_cita.asc(), Cita.id_cita.asc())
    if not forzar:
        stmt = stmt.where(Cita.id_cita.not_in(select(PrediccionIA.id_cita).where(PrediccionIA.version_modelo == version_modelo)))
    return [_snapshot(c) for c in db.scalars(stmt)]


def historicas(db: Session):
    # Consumidor legacy de entrenamiento; solo lectura, retirada en fase 5.
    return list(db.scalars(select(Cita).where(Cita.target_no_show.is_not(None)).order_by(Cita.id_cita_externa.asc())))


def conteos_dataset_bd(db: Session) -> dict[str, int]:
    total = db.scalar(select(func.count(Cita.id_cita)).where(Cita.target_no_show.is_not(None))) or 0
    no_show = db.scalar(select(func.count(Cita.id_cita)).where(Cita.target_no_show == 1)) or 0
    atendidas = db.scalar(select(func.count(Cita.id_cita)).where(Cita.target_no_show == 0)) or 0
    proximas = db.scalar(select(func.count(Cita.id_cita)).where(Cita.target_no_show.is_(None))) or 0
    return {"total_historicas_bd": int(total), "atendidas_bd": int(atendidas), "no_show_bd": int(no_show), "proximas_bd": int(proximas)}
