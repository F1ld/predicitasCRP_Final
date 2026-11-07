"""Mapping explícito plano legacy -> fila lógica de entrenamiento v1.

No escribe JSONL, particiones ni manifiestos; ese pipeline sigue en fase 6.
Las reglas de acreditación no cambian la validación operacional del backend.
"""
from datetime import datetime
import re

from datasets.temporal import LIMA, derivar_variables

FEATURES = ("especialidad", "tipo_paciente", "canal_origen", "franja_horaria", "dia_semana",
    "antelacion_dias", "inasistencias_previas", "asistencias_previas", "reprogramaciones_prev")
DOMINIOS = {
    "especialidad": {"CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"}, "tipo_paciente": {"NUEVO", "CONTINUADOR"},
    "canal_origen": {"WEB", "CALL_CENTER", "PRESENCIAL"}, "franja_horaria": {"MANANA", "TARDE"},
    "dia_semana": {"LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO"},
}


def fila_entrenamiento(registro, *, corte: datetime):
    if corte.utcoffset() is None:
        raise ValueError("Corte con zona requerido")
    state = registro["estado_actual"]
    target = registro["target_no_show"]
    if state not in ("ATENDIDA", "NO_SHOW") or type(target) is not int or target != int(state == "NO_SHOW"):
        raise ValueError("Solo históricos con target coherente")
    for field, prefix in (("id_cita_externa", "CIT"), ("paciente_anon_id", "PAC")):
        if not re.fullmatch(prefix + r"-SIM-[A-Za-z0-9_-]+", registro[field]) or len(registro[field]) > 50:
            raise ValueError("Identificador sintético no canónico")
    appointment = datetime.fromisoformat(registro["fecha_hora_cita"])
    registered = datetime.fromisoformat(registro["fecha_registro_cita"])
    if appointment.utcoffset() is None or registered.utcoffset() is None or not registered <= appointment <= corte:
        raise ValueError("Fechas fuera del corte o sin zona")
    features = {k: registro[k] for k in FEATURES}
    if any(features[k] not in valid for k, valid in DOMINIOS.items()):
        raise ValueError("Catálogo no canónico")
    if any(type(features[k]) is not int or features[k] < 0 for k in FEATURES[5:]):
        raise ValueError("Contadores/antelación no canónicos")
    if any(features[k] != v for k, v in derivar_variables(appointment, registered).items()):
        raise ValueError("Variables temporales inconsistentes")
    if features["tipo_paciente"] == "NUEVO" and (features["inasistencias_previas"] or features["asistencias_previas"]):
        raise ValueError("NUEVO con historial previo")
    return {k: registro[k] for k in ("id_cita_externa", "paciente_anon_id", "fecha_hora_cita", "fecha_registro_cita", "estado_actual", "target_no_show")} | {"features": features}
