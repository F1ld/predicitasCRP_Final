"""Adaptador explícito de lectura compuesta. Una sentencia/snapshot por respuesta.

Lee modelos de Citas, IA, Intervenciones y Lista de espera; nunca los modifica.
Los mismos SELECT filtrados alimentan el contador y la página de cada categoría.
"""
from sqlalchemy import case, exists, func, literal, select, true
from sqlalchemy.orm import Session

from app.core.dominio import ESTADOS_CITA, ESTADOS_CUPO, ESTADOS_INTERVENCION, NIVELES_RIESGO
from app.modules.citas.models import Cita
from app.modules.ia.models import PrediccionIA
from app.modules.intervenciones.models import Intervencion
from app.modules.lista_espera.models import CupoLiberado, Reasignacion


def _universos(inicio, fin, especialidad):
    citas_stmt = select(Cita.__table__).where(Cita.fecha_hora_cita >= inicio, Cita.fecha_hora_cita < fin)
    cupos_stmt = select(CupoLiberado.__table__).where(
        CupoLiberado.fecha_hora_cupo >= inicio, CupoLiberado.fecha_hora_cupo < fin)
    if especialidad is not None:
        citas_stmt = citas_stmt.where(Cita.especialidad == especialidad)
        cupos_stmt = cupos_stmt.where(CupoLiberado.especialidad == especialidad)
    citas = citas_stmt.cte("citas_base")
    numeradas = select(
        PrediccionIA.id_cita, PrediccionIA.id_prediccion, PrediccionIA.nivel_riesgo,
        PrediccionIA.probabilidad_no_show,
        func.row_number().over(partition_by=PrediccionIA.id_cita, order_by=(
            PrediccionIA.fecha_hora_inferencia.desc(), PrediccionIA.id_prediccion.desc())).label("rn"),
    ).join(citas, citas.c.id_cita == PrediccionIA.id_cita).cte("predicciones_ordenadas")
    pred = select(numeradas).where(numeradas.c.rn == 1).cte("prediccion_por_cita")
    con_riesgo = select(
        citas, pred.c.id_prediccion, pred.c.nivel_riesgo, pred.c.probabilidad_no_show,
    ).select_from(citas.outerjoin(pred, pred.c.id_cita == citas.c.id_cita)).cte(
        "citas_con_riesgo").prefix_with("MATERIALIZED", dialect="postgresql")
    # El límite de materialización evita que el filtro de riesgo se empuje a la
    # ventana y produzca nested loops con estimaciones de cardinalidad muy bajas.
    cupos = cupos_stmt.cte("cupos_base")
    confirmado = exists(select(Reasignacion.id_reasignacion).where(
        Reasignacion.id_cupo_liberado == cupos.c.id_cupo_liberado,
        Reasignacion.confirmacion_humana.is_(True)))
    cupos = select(cupos, confirmado.label("confirmado")).cte("cupos_con_confirmacion")
    return con_riesgo, cupos


def _sin_optout(citas):
    # El opt-out no se recorta por fecha ni especialidad del panel.
    otras = Cita.__table__.alias("citas_optout")
    oposicion = Intervencion.__table__.alias("intervenciones_optout")
    return ~exists(select(oposicion.c.id_intervencion).select_from(
        oposicion.join(otras, otras.c.id_cita == oposicion.c.id_cita)
    ).where(otras.c.paciente_anon_id == citas.c.paciente_anon_id,
            oposicion.c.consentimiento_optout.is_(True)))


def _cupo_accionable(cupos, estado, ahora):
    return (cupos.c.estado_cupo == estado) & (cupos.c.fecha_hora_cupo > ahora) & ~cupos.c.confirmado


def _pendientes(citas, cupos, ahora):
    datos_cita = [citas.c.id_cita, citas.c.id_cita_externa, citas.c.paciente_anon_id,
                  citas.c.fecha_hora_cita, citas.c.especialidad, citas.c.medico,
                  citas.c.estado_actual.label("estado_cita")]
    sin_inter = select(
        literal("CITAS_SIN_INTERVENCION").label("tipo"), *datos_cita,
        citas.c.id_prediccion, citas.c.nivel_riesgo, citas.c.probabilidad_no_show,
    ).where(
        citas.c.estado_actual == "RECIBIDA", citas.c.fecha_hora_cita > ahora,
        citas.c.nivel_riesgo.in_(("ALTO", "MEDIO")), _sin_optout(citas),
        ~exists(select(Intervencion.id_intervencion).where(Intervencion.id_cita == citas.c.id_cita)),
    )
    sin_respuesta = select(
        literal("INTERVENCIONES_SIN_RESPUESTA").label("tipo"), *datos_cita,
        Intervencion.id_intervencion, Intervencion.canal_contacto,
        Intervencion.estado_intervencion, Intervencion.fecha_hora_envio,
    ).select_from(citas.join(Intervencion, Intervencion.id_cita == citas.c.id_cita)).where(
        Intervencion.estado_intervencion.in_(("ENVIADA", "ENTREGADA")),
        Intervencion.fecha_hora_respuesta.is_(None), Intervencion.respuesta_paciente.is_(None),
        citas.c.estado_actual.in_(("RECIBIDA", "CONFIRMADA", "REPROGRAMADA")),
        citas.c.fecha_hora_cita > ahora, _sin_optout(citas),
    )
    ofertas = select(
        literal("OFERTAS_EN_CURSO").label("tipo"), cupos.c.id_cupo_liberado,
        cupos.c.id_cita_origen, cupos.c.fecha_hora_cupo, cupos.c.especialidad,
        cupos.c.medico, cupos.c.estado_cupo, cupos.c.origen_liberacion,
    ).where(_cupo_accionable(cupos, "EN_OFERTA", ahora))
    return {
        "CITAS_SIN_INTERVENCION": (sin_inter, (
            case((citas.c.nivel_riesgo == "ALTO", 0), else_=1),
            citas.c.probabilidad_no_show.desc(), citas.c.fecha_hora_cita, citas.c.id_cita)),
        "INTERVENCIONES_SIN_RESPUESTA": (sin_respuesta, (
            citas.c.fecha_hora_cita, Intervencion.fecha_hora_envio, Intervencion.id_intervencion)),
        "OFERTAS_EN_CURSO": (ofertas, (cupos.c.fecha_hora_cupo, cupos.c.id_cupo_liberado)),
    }


def _desglose(columna, valores, prefijo):
    return [func.count().filter(columna == valor).label(f"{prefijo}_{valor}") for valor in valores]


def sentencia_resumen(inicio, fin, especialidad, ahora):
    citas, cupos = _universos(inicio, fin, especialidad)
    citas_ag = select(
        func.count().label("citas_total"),
        *_desglose(citas.c.estado_actual, ESTADOS_CITA, "cita"),
        *_desglose(func.coalesce(citas.c.nivel_riesgo, "SIN_PREDICCION"),
                   (*NIVELES_RIESGO, "SIN_PREDICCION"), "riesgo"),
    ).select_from(citas).subquery("resumen_citas")
    inter_ag = select(
        func.count().label("inter_total"), func.count(func.distinct(Intervencion.id_cita)).label("inter_citas"),
        *_desglose(Intervencion.estado_intervencion, ESTADOS_INTERVENCION, "inter"),
    ).select_from(citas.join(Intervencion, Intervencion.id_cita == citas.c.id_cita)).subquery("resumen_inter")
    cupos_ag = select(
        func.count().label("cupos_total"), *_desglose(cupos.c.estado_cupo, ESTADOS_CUPO, "cupo"),
        func.count().filter(_cupo_accionable(cupos, "DISPONIBLE", ahora)).label("disponibles"),
        func.count().filter(cupos.c.confirmado).label("confirmados"),
    ).select_from(cupos).subquery("resumen_cupos")
    pendientes = [select(func.count()).select_from(stmt.subquery()).scalar_subquery().label(tipo)
                  for tipo, (stmt, _) in _pendientes(citas, cupos, ahora).items()]
    return select(citas_ag, inter_ag, cupos_ag, *pendientes).select_from(
        citas_ag.join(inter_ag, true()).join(cupos_ag, true()))


def resumen(db: Session, *, inicio, fin, especialidad, ahora):
    return db.execute(sentencia_resumen(inicio, fin, especialidad, ahora)).mappings().one()


def sentencia_pendientes(inicio, fin, especialidad, ahora, tipo, limite, desplazamiento):
    citas, cupos = _universos(inicio, fin, especialidad)
    stmt, orden = _pendientes(citas, cupos, ahora)[tipo]
    base = stmt.add_columns(func.row_number().over(order_by=orden).label("_orden")).cte("pendientes")
    total = select(func.count().label("total")).select_from(base).subquery("total_pendientes")
    pagina = select(base).order_by(base.c._orden).limit(limite).offset(desplazamiento).subquery("pagina")
    # LEFT JOIN conserva total incluso con universo vacío u offset fuera de rango.
    return select(total.c.total, pagina).select_from(total.outerjoin(pagina, true())).order_by(pagina.c._orden)


def pendientes(db: Session, *, inicio, fin, especialidad, ahora, tipo, limite, desplazamiento):
    filas = db.execute(sentencia_pendientes(
        inicio, fin, especialidad, ahora, tipo, limite, desplazamiento)).mappings().all()
    items = [{k: v for k, v in fila.items() if k not in ("total", "_orden")}
             for fila in filas if fila["_orden"] is not None]
    return filas[0]["total"], items
