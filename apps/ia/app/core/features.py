"""Gestión de variables y derivación pre-cita para inferencia LightGBM.

Aislado de FastAPI backend, SQLAlchemy y modelos relacionales.
"""
from __future__ import annotations

from typing import Any
import numpy as np

from app.schemas import FeaturesPreCita, SnapshotFeatures

FEATURES_CATEGORICAS = [
    "especialidad",
    "tipo_paciente",
    "canal_origen",
    "franja_horaria",
    "dia_semana",
]

FEATURES_NUMERICAS_BASE = [
    "antelacion_dias",
    "inasistencias_previas",
    "asistencias_previas",
    "reprogramaciones_prev",
]

FEATURES_NUMERICAS_DERIVADAS = [
    "tasa_no_show_previa",
    "es_reserva_lejana",
]

FEATURES_NUMERICAS = FEATURES_NUMERICAS_BASE + FEATURES_NUMERICAS_DERIVADAS
FEATURES_ENTRADA_MODELO = FEATURES_NUMERICAS + FEATURES_CATEGORICAS

# Categorías canónicas autorizadas en el OneHotEncoder del pipeline
CATEGORIAS_ESPECIALIDADES = ["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"]
CATEGORIAS_TIPOS_PACIENTE = ["NUEVO", "CONTINUADOR"]
CATEGORIAS_CANALES_ORIGEN = ["WEB", "CALL_CENTER", "PRESENCIAL"]
CATEGORIAS_FRANJAS_CITA = ["MANANA", "TARDE"]
CATEGORIAS_DIAS_SEMANA = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO"]


def derivar_snapshot(features: FeaturesPreCita) -> SnapshotFeatures:
    """Calcula las variables derivadas usando estrictamente información conocida al agendar.

    Fórmula acreditada:
    - tasa_no_show_previa = round(inasistencias / (asistencias + inasistencias + 1.0), 4)
    - es_reserva_lejana = 1 si antelacion_dias >= 15 else 0
    """
    inasistencias = features.inasistencias_previas
    asistencias = features.asistencias_previas
    antelacion = features.antelacion_dias

    tasa_raw = inasistencias / (asistencias + inasistencias + 1.0)
    tasa_derivada = round(tasa_raw, 4)
    es_lejana = 1 if antelacion >= 15 else 0

    return SnapshotFeatures(
        especialidad=features.especialidad,
        tipo_paciente=features.tipo_paciente,
        canal_origen=features.canal_origen,
        franja_horaria=features.franja_horaria,
        dia_semana=features.dia_semana,
        antelacion_dias=antelacion,
        inasistencias_previas=inasistencias,
        asistencias_previas=asistencias,
        reprogramaciones_prev=features.reprogramaciones_prev,
        tasa_no_show_previa=tasa_derivada,
        es_reserva_lejana=es_lejana,
    )


def construir_matriz_inferencia(snapshots: list[SnapshotFeatures]) -> np.ndarray:
    """Construye la matriz NumPy 2D (dtype=object) para el ColumnTransformer del pipeline."""
    filas = []
    for s in snapshots:
        fila = [
            s.antelacion_dias,
            s.inasistencias_previas,
            s.asistencias_previas,
            s.reprogramaciones_prev,
            s.tasa_no_show_previa,
            s.es_reserva_lejana,
            s.especialidad,
            s.tipo_paciente,
            s.canal_origen,
            s.franja_horaria,
            s.dia_semana,
        ]
        filas.append(fila)
    return np.array(filas, dtype=object)
