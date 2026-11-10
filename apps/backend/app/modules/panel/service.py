"""Casos de lectura del panel; sin commits, inferencia ni escrituras."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from app.core.dominio import ESTADOS_CITA, ESTADOS_CUPO, ESTADOS_INTERVENCION, NIVELES_RIESGO
from app.core.errores import Validacion
from app.core.reloj import LIMA
from app.modules.panel import consultas
from app.modules.panel.schemas import PanelPendientesOut, PanelResumenOut


def contexto(fecha: date | None, especialidad, ahora: datetime):
    if ahora.tzinfo is None:
        raise ValueError("El reloj del panel debe incluir zona horaria")
    ahora = ahora.astimezone(LIMA)
    fecha = fecha or ahora.date()
    if fecha == date.max:
        raise Validacion("La fecha no admite construir el límite del día siguiente", campos={"fecha": "Fecha fuera de rango"})
    inicio = datetime.combine(fecha, time.min, tzinfo=LIMA)
    fin = datetime.combine(fecha + timedelta(days=1), time.min, tzinfo=LIMA)
    return {"fecha": fecha, "especialidad": especialidad, "generado_en": ahora}, inicio, fin


def obtener_resumen(db, *, fecha, especialidad, ahora):
    ctx, inicio, fin = contexto(fecha, especialidad, ahora)
    r = consultas.resumen(db, inicio=inicio, fin=fin, especialidad=especialidad, ahora=ctx["generado_en"])
    tasa = None if r["cupos_total"] == 0 else float((
        Decimal(100) * Decimal(r["confirmados"]) / Decimal(r["cupos_total"])
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    ofertas = r["OFERTAS_EN_CURSO"]
    return PanelResumenOut(
        **ctx,
        citas={"total": r["citas_total"],
               "por_estado": {e: r[f"cita_{e}"] for e in ESTADOS_CITA},
               "por_riesgo": {e: r[f"riesgo_{e}"] for e in (*NIVELES_RIESGO, "SIN_PREDICCION")}},
        intervenciones={"total": r["inter_total"], "citas_con_intervencion": r["inter_citas"],
                        "por_estado": {e: r[f"inter_{e}"] for e in ESTADOS_INTERVENCION}},
        cupos={"total_liberados": r["cupos_total"], "por_estado": {e: r[f"cupo_{e}"] for e in ESTADOS_CUPO},
               "disponibles_para_ofrecer": r["disponibles"], "ofertas_en_curso": ofertas,
               "reasignados_confirmados": r["confirmados"], "tasa_recuperacion_pct": tasa},
        pendientes={"citas_sin_intervencion": r["CITAS_SIN_INTERVENCION"],
                    "intervenciones_sin_respuesta": r["INTERVENCIONES_SIN_RESPUESTA"],
                    "ofertas_en_curso": ofertas},
    )


def listar_pendientes(db, *, fecha, especialidad, ahora, tipo, limite, desplazamiento):
    ctx, inicio, fin = contexto(fecha, especialidad, ahora)
    total, items = consultas.pendientes(db, inicio=inicio, fin=fin, especialidad=especialidad,
        ahora=ctx["generado_en"], tipo=tipo, limite=limite, desplazamiento=desplazamiento)
    return PanelPendientesOut(**ctx, tipo=tipo, total=total, limite=limite,
                             desplazamiento=desplazamiento, items=items)
