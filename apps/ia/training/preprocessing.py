"""Extracción mecánica del preprocesado legacy; mismo orden y categorías."""
from typing import Any

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.core.features import (
    FEATURES_ENTRADA_MODELO, FEATURES_NUMERICAS,
    CATEGORIAS_ESPECIALIDADES, CATEGORIAS_TIPOS_PACIENTE, CATEGORIAS_CANALES_ORIGEN,
    CATEGORIAS_FRANJAS_CITA, CATEGORIAS_DIAS_SEMANA,
)


def derivar_features_fila(fila: dict[str, Any]) -> dict[str, Any]:
    """Normalización histórica para datos offline, no cambia validación HTTP."""
    antelacion = int(fila["antelacion_dias"])
    inasistencias = int(fila.get("inasistencias_previas", 0) or 0)
    asistencias = int(fila.get("asistencias_previas", 0) or 0)
    reprogramaciones = int(fila.get("reprogramaciones_prev", 0) or 0)
    tipo = str(fila["tipo_paciente"]).upper()
    canal = str(fila["canal_origen"]).upper()
    tasa_previa = inasistencias / (asistencias + inasistencias + 1.0)
    es_lejana = 1 if antelacion >= 15 else 0
    return {
        "antelacion_dias": antelacion,
        "inasistencias_previas": inasistencias,
        "asistencias_previas": asistencias,
        "reprogramaciones_prev": reprogramaciones,
        "tasa_no_show_previa": round(tasa_previa, 4),
        "es_reserva_lejana": es_lejana,
        "especialidad": str(fila["especialidad"]).upper(),
        "tipo_paciente": tipo,
        "canal_origen": canal,
        "franja_horaria": str(fila["franja_horaria"]).upper(),
        "dia_semana": str(fila["dia_semana"]).upper(),
    }


def construir_matriz(registros):
    filas = [derivar_features_fila(r) for r in registros]
    return np.array([[f[c] for c in FEATURES_ENTRADA_MODELO] for f in filas], dtype=object), filas


def crear_preprocesador() -> ColumnTransformer:
    idx_num = list(range(len(FEATURES_NUMERICAS)))
    idx_cat = list(range(len(FEATURES_NUMERICAS), len(FEATURES_ENTRADA_MODELO)))
    rama_numerica = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    rama_categorica = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("ohe", OneHotEncoder(categories=[
            list(CATEGORIAS_ESPECIALIDADES), list(CATEGORIAS_TIPOS_PACIENTE),
            list(CATEGORIAS_CANALES_ORIGEN), list(CATEGORIAS_FRANJAS_CITA), list(CATEGORIAS_DIAS_SEMANA),
        ], handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer(transformers=[("num", rama_numerica, idx_num), ("cat", rama_categorica, idx_cat)], remainder="drop")
