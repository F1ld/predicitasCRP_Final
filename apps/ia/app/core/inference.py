"""Motor de inferencia LightGBM y explicabilidad local TreeSHAP.

Preserva con exactitud matemática las probabilidades redondeadas, umbrales y explicaciones.
"""
from __future__ import annotations

from typing import Any, Literal
import numpy as np
from sklearn.pipeline import Pipeline

from app.config import UMBRAL_ALTO, UMBRAL_MEDIO
from app.core.features import (
    CATEGORIAS_CANALES_ORIGEN,
    CATEGORIAS_DIAS_SEMANA,
    CATEGORIAS_ESPECIALIDADES,
    CATEGORIAS_FRANJAS_CITA,
    CATEGORIAS_TIPOS_PACIENTE,
    FEATURES_NUMERICAS,
    construir_matriz_inferencia,
    derivar_snapshot,
)
from app.schemas import FeaturesPreCita, NivelRiesgoEnum, SnapshotFeatures


def clasificar_nivel_riesgo(probabilidad: float) -> NivelRiesgoEnum:
    """Clasifica la probabilidad redondeada en BAJO, MEDIO o ALTO según RF-046."""
    if probabilidad > UMBRAL_ALTO:
        return "ALTO"
    if probabilidad >= UMBRAL_MEDIO:
        return "MEDIO"
    return "BAJO"


def explicar_prediccion(
    pipeline_lgbm: Pipeline,
    snapshot: SnapshotFeatures,
    probabilidad: float,
) -> str:
    """Extrae los 3 factores locales de mayor impacto mediante TreeSHAP nativo de LightGBM."""
    X_mat = construir_matriz_inferencia([snapshot])
    prep = pipeline_lgbm.named_steps["prep"]
    clf = pipeline_lgbm.named_steps["clf"]

    X_trans = prep.transform(X_mat)
    contrib = clf.booster_.predict(X_trans, pred_contrib=True)[0]

    # Mapeo de las 22 columnas transformadas a atributos legibles
    impacto_antelacion = float(contrib[0] + contrib[5])
    impacto_inasistencias = float(contrib[1] + contrib[4])
    impacto_asistencias = float(contrib[2])
    impacto_reprogramaciones = float(contrib[3])

    offset = len(FEATURES_NUMERICAS)
    n_esp = len(CATEGORIAS_ESPECIALIDADES)
    n_tipo = len(CATEGORIAS_TIPOS_PACIENTE)
    n_canal = len(CATEGORIAS_CANALES_ORIGEN)
    n_franja = len(CATEGORIAS_FRANJAS_CITA)
    n_dia = len(CATEGORIAS_DIAS_SEMANA)

    impacto_esp = float(np.sum(contrib[offset : offset + n_esp]))
    offset += n_esp
    impacto_tipo = float(np.sum(contrib[offset : offset + n_tipo]))
    offset += n_tipo
    impacto_canal = float(np.sum(contrib[offset : offset + n_canal]))
    offset += n_canal
    impacto_franja = float(np.sum(contrib[offset : offset + n_franja]))
    offset += n_franja
    impacto_dia = float(np.sum(contrib[offset : offset + n_dia]))

    candidatos = [
        (impacto_inasistencias, f"Inasistencias previas: {snapshot.inasistencias_previas}"),
        (impacto_antelacion, f"Antelación: {snapshot.antelacion_dias} días"),
        (impacto_reprogramaciones, f"Reprogramaciones: {snapshot.reprogramaciones_prev}"),
        (impacto_tipo, f"Paciente {snapshot.tipo_paciente}"),
        (impacto_canal, f"Canal {snapshot.canal_origen}"),
        (impacto_franja, f"Turno {snapshot.franja_horaria}"),
        (impacto_esp, f"Especialidad {snapshot.especialidad}"),
        (impacto_asistencias, f"Asistencias previas: {snapshot.asistencias_previas}"),
        (impacto_dia, f"Día {snapshot.dia_semana}"),
    ]

    if probabilidad >= UMBRAL_MEDIO:
        ordenados = sorted(candidatos, key=lambda x: x[0], reverse=True)
    else:
        ordenados = sorted(candidatos, key=lambda x: x[0])

    top_3 = [
        f"{idx}) {etiqueta} ({valor:+.2f})"
        for idx, (valor, etiqueta) in enumerate(ordenados[:3], start=1)
    ]
    resumen = f"Factores clave: {' | '.join(top_3)} [Simulado]"
    return resumen[:255]


def ejecutar_inferencia_individual(
    pipeline_lgbm: Pipeline,
    features: FeaturesPreCita,
) -> tuple[float, NivelRiesgoEnum, SnapshotFeatures, str]:
    """Ejecuta inferencia completa para una solicitud individual."""
    snapshot = derivar_snapshot(features)
    X_mat = construir_matriz_inferencia([snapshot])

    prob_raw = float(pipeline_lgbm.predict_proba(X_mat)[0, 1])
    prob_redondeada = round(max(0.0, min(1.0, prob_raw)), 3)
    nivel = clasificar_nivel_riesgo(prob_redondeada)
    resumen = explicar_prediccion(pipeline_lgbm, snapshot, prob_redondeada)

    return prob_redondeada, nivel, snapshot, resumen
