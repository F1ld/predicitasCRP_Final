"""Derivación temporal legacy necesaria para generar datos, sin backend."""
from datetime import datetime
from zoneinfo import ZoneInfo

LIMA = ZoneInfo("America/Lima")
DIAS_SEMANA = ("LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO")


class FechasInconsistentes(ValueError):
    pass


class FechaEnDomingo(ValueError):
    pass


def derivar_variables(fecha_hora_cita: datetime, fecha_registro_cita: datetime) -> dict:
    cita = fecha_hora_cita.astimezone(LIMA)
    registro = fecha_registro_cita.astimezone(LIMA)
    antelacion = (cita.date() - registro.date()).days
    if antelacion < 0:
        raise FechasInconsistentes("fecha_registro_cita es posterior a fecha_hora_cita")
    if cita.weekday() == 6:
        raise FechaEnDomingo("la cita cae en domingo (fuera de los días del piloto)")
    return {"antelacion_dias": antelacion,
        "franja_horaria": "MANANA" if cita.hour < 13 else "TARDE", "dia_semana": DIAS_SEMANA[cita.weekday()]}
