"""Adaptador de lectura compuesto de Intervenciones; no cierra transacciones."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.modules.citas.models import Cita
from app.modules.ia.models import PrediccionIA
from app.modules.intervenciones.models import Intervencion
from app.modules.lista_espera import public as lista_espera_public
from app.modules.citas.public import CitaConsulta


def cita_relacionada(intervencion: Intervencion) -> CitaConsulta | None:
    cita = getattr(intervencion, "cita", None)
    return CitaConsulta(**{k: getattr(cita, k) for k in CitaConsulta.__dataclass_fields__}) if cita is not None else None


def listar_por_cita(db: Session, id_cita: int) -> list[Intervencion]:
    stmt = (
        select(Intervencion)
        .where(Intervencion.id_cita == id_cita)
        .order_by(Intervencion.fecha_hora_envio.desc(), Intervencion.id_intervencion.desc())
    )
    return list(db.scalars(stmt))


def listar_estados_previos_por_cita(db: Session, id_cita: int) -> list[str]:
    stmt = (
        select(Intervencion.estado_intervencion)
        .where(Intervencion.id_cita == id_cita)
        .order_by(Intervencion.fecha_hora_envio.asc(), Intervencion.id_intervencion.asc())
    )
    return list(db.scalars(stmt))


def contar_activas_por_cita(db: Session, id_cita: int) -> int:
    stmt = select(func.count(Intervencion.id_intervencion)).where(
        Intervencion.id_cita == id_cita,
        Intervencion.estado_intervencion != "FALLIDA",
    )
    return int(db.scalar(stmt) or 0)


def tiene_optout_vigente(db: Session, id_cita: int, paciente_anon_id: str) -> bool:
    """Verifica si existe derecho de oposición (opt-out) registrado en la cita o para el paciente."""
    stmt = (
        select(Intervencion.id_intervencion)
        .join(Cita, Cita.id_cita == Intervencion.id_cita)
        .where(
            Intervencion.consentimiento_optout.is_(True),
            (Intervencion.id_cita == id_cita) | (Cita.paciente_anon_id == paciente_anon_id),
        )
        .limit(1)
    )
    return db.scalar(stmt) is not None


def listar_historial(
    db: Session,
    *,
    estado_intervencion: str | None = None,
    canal_contacto: str | None = None,
    limite: int = 100,
) -> list[Intervencion]:
    stmt = select(Intervencion).order_by(
        Intervencion.fecha_hora_envio.desc(),
        Intervencion.id_intervencion.desc(),
    )
    if estado_intervencion:
        stmt = stmt.where(Intervencion.estado_intervencion == estado_intervencion.upper())
    if canal_contacto:
        stmt = stmt.where(Intervencion.canal_contacto == canal_contacto.upper())
    return list(db.scalars(stmt.limit(limite)))


def listar_citas_riesgo_medio_alto(
    db: Session,
    *,
    nivel_riesgo: str | None = None,
    especialidad: str | None = None,
) -> list[tuple[Cita, PrediccionIA]]:
    """Filtra el riesgo de la última predicción, nunca el de versiones históricas."""
    niveles = [nivel_riesgo.upper()] if nivel_riesgo else ["ALTO", "MEDIO"]
    numeradas = select(PrediccionIA, func.row_number().over(
        partition_by=PrediccionIA.id_cita,
        order_by=(PrediccionIA.fecha_hora_inferencia.desc(), PrediccionIA.id_prediccion.desc()),
    ).label("rn")).subquery()
    reciente = aliased(PrediccionIA, numeradas)
    stmt = (
        select(Cita, reciente)
        .join(reciente, reciente.id_cita == Cita.id_cita)
        .where(
            numeradas.c.rn == 1,
            Cita.estado_actual.in_(("RECIBIDA", "CONFIRMADA", "REPROGRAMADA")),
            reciente.nivel_riesgo.in_(("ALTO", "MEDIO")),
            reciente.nivel_riesgo.in_(niveles),
        )
        .order_by(
            reciente.probabilidad_no_show.desc(),
            Cita.fecha_hora_cita.asc(),
            Cita.id_cita.asc(),
        )
    )
    if especialidad:
        stmt = stmt.where(Cita.especialidad == especialidad.upper())
    return list(db.execute(stmt).all())


def obtener_prediccion_reciente(db: Session, id_cita: int) -> PrediccionIA | None:
    stmt = (
        select(PrediccionIA)
        .where(PrediccionIA.id_cita == id_cita)
        .order_by(PrediccionIA.fecha_hora_inferencia.desc(), PrediccionIA.id_prediccion.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def obtener_cupo_por_cita_origen(db: Session, id_cita: int) -> lista_espera_public.CupoLiberadoSnapshot | None:
    return lista_espera_public.obtener_cupo_por_cita_origen(db, id_cita)
