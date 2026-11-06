"""Compatibilidad interna de consultas; no constituye un contrato entre módulos."""
from app.modules.intervenciones.consultas import (
    listar_por_cita, listar_estados_previos_por_cita, contar_activas_por_cita,
    tiene_optout_vigente, listar_historial, listar_citas_riesgo_medio_alto,
    obtener_prediccion_reciente, obtener_cupo_por_cita_origen, cita_relacionada,
)
