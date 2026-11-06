"""Pruebas de paridad matemática estricta contra la línea base congelada del predictor histórico."""
from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from app.config import MODEL_PATH
from app.core.inference import ejecutar_inferencia_individual
from app.core.model_registry import registry
from app.schemas import FeaturesPreCita

CASOS_CONGELADOS = [
    {
        "caso": {
            "especialidad": "TRAUMATOLOGIA",
            "tipo_paciente": "CONTINUADOR",
            "canal_origen": "CALL_CENTER",
            "franja_horaria": "TARDE",
            "dia_semana": "VIERNES",
            "antelacion_dias": 32,
            "inasistencias_previas": 3,
            "asistencias_previas": 1,
            "reprogramaciones_prev": 2,
        },
        "esperado": {
            "probabilidad_no_show": 0.999,
            "nivel_riesgo": "ALTO",
            "tasa_no_show_previa": 0.6,
            "es_reserva_lejana": 1,
            "explicabilidad_resumen": "Factores clave: 1) Inasistencias previas: 3 (+5.94) | 2) Antelación: 32 días (+1.98) | 3) Reprogramaciones: 2 (+1.87) [Simulado]",
        },
    },
    {
        "caso": {
            "especialidad": "CARDIOLOGIA",
            "tipo_paciente": "NUEVO",
            "canal_origen": "WEB",
            "franja_horaria": "MANANA",
            "dia_semana": "LUNES",
            "antelacion_dias": 3,
            "inasistencias_previas": 0,
            "asistencias_previas": 0,
            "reprogramaciones_prev": 0,
        },
        "esperado": {
            "probabilidad_no_show": 0.001,
            "nivel_riesgo": "BAJO",
            "tasa_no_show_previa": 0.0,
            "es_reserva_lejana": 0,
            "explicabilidad_resumen": "Factores clave: 1) Antelación: 3 días (-2.09) | 2) Inasistencias previas: 0 (-1.81) | 3) Turno MANANA (-0.27) [Simulado]",
        },
    },
    {
        "caso": {
            "especialidad": "PEDIATRIA",
            "tipo_paciente": "CONTINUADOR",
            "canal_origen": "PRESENCIAL",
            "franja_horaria": "TARDE",
            "dia_semana": "MIERCOLES",
            "antelacion_dias": 16,
            "inasistencias_previas": 1,
            "asistencias_previas": 5,
            "reprogramaciones_prev": 1,
        },
        "esperado": {
            "probabilidad_no_show": 0.185,
            "nivel_riesgo": "BAJO",
            "tasa_no_show_previa": 0.1429,
            "es_reserva_lejana": 1,
            "explicabilidad_resumen": "Factores clave: 1) Inasistencias previas: 1 (-0.40) | 2) Asistencias previas: 5 (-0.36) | 3) Paciente CONTINUADOR (-0.17) [Simulado]",
        },
    },
    {
        "caso": {
            "especialidad": "TRAUMATOLOGIA",
            "tipo_paciente": "NUEVO",
            "canal_origen": "CALL_CENTER",
            "franja_horaria": "MANANA",
            "dia_semana": "JUEVES",
            "antelacion_dias": 45,
            "inasistencias_previas": 0,
            "asistencias_previas": 0,
            "reprogramaciones_prev": 0,
        },
        "esperado": {
            "probabilidad_no_show": 0.763,
            "nivel_riesgo": "ALTO",
            "tasa_no_show_previa": 0.0,
            "es_reserva_lejana": 1,
            "explicabilidad_resumen": "Factores clave: 1) Antelación: 45 días (+4.12) | 2) Asistencias previas: 0 (+1.27) | 3) Paciente NUEVO (+1.10) [Simulado]",
        },
    },
    {
        "caso": {
            "especialidad": "CARDIOLOGIA",
            "tipo_paciente": "CONTINUADOR",
            "canal_origen": "WEB",
            "franja_horaria": "TARDE",
            "dia_semana": "SABADO",
            "antelacion_dias": 1,
            "inasistencias_previas": 4,
            "asistencias_previas": 0,
            "reprogramaciones_prev": 3,
        },
        "esperado": {
            "probabilidad_no_show": 0.982,
            "nivel_riesgo": "ALTO",
            "tasa_no_show_previa": 0.8,
            "es_reserva_lejana": 0,
            "explicabilidad_resumen": "Factores clave: 1) Inasistencias previas: 4 (+8.58) | 2) Reprogramaciones: 3 (+1.71) | 3) Asistencias previas: 0 (+0.36) [Simulado]",
        },
    },
]


@pytest.mark.parametrize("item", CASOS_CONGELADOS)
def test_paridad_estricta_con_linea_base_congelada(item: dict):
    features_obj = FeaturesPreCita(**item["caso"])
    assert registry.pipeline is not None

    prob, nivel, snapshot, explicacion = ejecutar_inferencia_individual(registry.pipeline, features_obj)
    esp = item["esperado"]

    assert prob == esp["probabilidad_no_show"], f"Probabilidad difiere para caso {item['caso']}"
    assert nivel == esp["nivel_riesgo"], f"Nivel difiere para caso {item['caso']}"
    assert explicacion == esp["explicabilidad_resumen"], f"Explicación difiere para caso {item['caso']}"
    assert snapshot.tasa_no_show_previa == esp["tasa_no_show_previa"], "Tasa previa difiere"
    assert snapshot.es_reserva_lejana == esp["es_reserva_lejana"], "Bandera reserva lejana difiere"


def test_inferencia_no_modifica_artefacto():
    """Garantiza que invocar la inferencia no altera en absoluto el archivo Joblib en disco."""
    if not MODEL_PATH.exists():
        pytest.skip("Modelo no presente en ruta esperada")

    hash_antes = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()

    # Ejecutar 10 inferencias
    caso = CASOS_CONGELADOS[0]["caso"]
    features_obj = FeaturesPreCita(**caso)
    for _ in range(10):
        ejecutar_inferencia_individual(registry.pipeline, features_obj)

    hash_despues = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    assert hash_antes == hash_despues, "La inferencia modificó el artefacto del modelo en disco"
