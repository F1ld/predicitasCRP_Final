"""Entrenamiento en memoria, solo por llamada explícita con datos/versiones/fecha.

Mismos estimadores e hiperparámetros legacy. No lee BD, genera datos, escribe
archivos, promueve modelos ni modifica el registry de serving.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.config import UMBRAL_ALTO, UMBRAL_MEDIO
from app.core.features import FEATURES_ENTRADA_MODELO
from training.evaluation import SEMILLA_OFICIAL, Particiones, particionar, verificar_sin_data_leakage
from training.metrics import calcular_metricas, auditar_equidad_subgrupos, importancia_global
from training.preprocessing import construir_matriz, crear_preprocesador

LEGACY_VERSION = "LightGBM_v1.0.0"


@dataclass(frozen=True)
class Entrenamiento:
    artefacto: dict[str, Any]
    particiones: Particiones


def crear_modelos():
    baseline = Pipeline([
        ("prep", crear_preprocesador()),
        ("clf", LogisticRegression(C=0.05, max_iter=1000, random_state=SEMILLA_OFICIAL)),
    ])
    principal = Pipeline([
        ("prep", crear_preprocesador()),
        ("clf", LGBMClassifier(objective="binary", n_estimators=220, learning_rate=0.045,
            num_leaves=23, max_depth=5, min_child_samples=12, subsample=0.85,
            colsample_bytree=0.85, class_weight="balanced", random_state=SEMILLA_OFICIAL, verbose=-1)),
    ])
    return baseline, principal


def validar_identidad(version_modelo, version_dataset, fecha_entrenamiento):
    for value in (version_modelo, version_dataset):
        if not isinstance(value, str) or not value.strip() or len(value) > 100:
            raise ValueError("Versiones explícitas no vacías de hasta 100 caracteres requeridas")
    if version_modelo == LEGACY_VERSION:
        raise ValueError("No se permite reutilizar la versión legacy activa para un candidato")
    if not isinstance(fecha_entrenamiento, datetime) or fecha_entrenamiento.utcoffset() is None:
        raise ValueError("Fecha de entrenamiento explícita con zona horaria requerida")


def entrenar(registros, *, version_modelo: str, version_dataset: str, fecha_entrenamiento: datetime) -> Entrenamiento:
    validar_identidad(version_modelo, version_dataset, fecha_entrenamiento)
    if len(registros) < 1000:
        raise ValueError(f"Se requieren al menos 1,000 citas históricas acreditadas; se encontraron {len(registros)}.")
    X_all, _ = construir_matriz(registros)
    y_all = np.array([int(r["target_no_show"]) for r in registros], dtype=int)
    split = particionar(y_all)
    idx_train, idx_val, idx_test = split.train, split.val, split.test
    X_train, X_val, X_test = X_all[idx_train], X_all[idx_val], X_all[idx_test]
    y_train, y_val, y_test = y_all[idx_train], y_all[idx_val], y_all[idx_test]
    registros_test = [registros[i] for i in idx_test]
    leakage = verificar_sin_data_leakage(registros, idx_train, idx_val, idx_test)
    baseline, principal = crear_modelos()
    baseline.fit(X_train, y_train)
    principal.fit(X_train, y_train)
    probs_val = principal.predict_proba(X_val)[:, 1]
    probs_test = principal.predict_proba(X_test)[:, 1]
    probs_base = baseline.predict_proba(X_test)[:, 1]
    metricas_val = calcular_metricas(y_val, probs_val, UMBRAL_ALTO)
    metricas_test = calcular_metricas(y_test, probs_test, UMBRAL_ALTO)
    metricas_base = calcular_metricas(y_test, probs_base, UMBRAL_ALTO)
    if metricas_test["f1_score"] < 0.82:
        raise RuntimeError(f"El modelo LightGBM no alcanzó la meta F1-Score >= 0.82 en Test (obtenido: {metricas_test['f1_score']:.4f}).")
    artefacto = {
        "version_modelo": version_modelo, "algoritmo": "LGBMClassifier", "semilla": SEMILLA_OFICIAL,
        "fecha_entrenamiento": fecha_entrenamiento.astimezone(timezone.utc).isoformat(),
        "es_simulacion": True, "rotulo_etico": "Resultado simulado — Dataset sintético acreditado (RF-056 / RN16)",
        "umbral_alto": UMBRAL_ALTO, "umbral_medio": UMBRAL_MEDIO,
        "features_entrada": list(FEATURES_ENTRADA_MODELO), "pipeline": principal, "pipeline_baseline": baseline,
        "dataset_info": {
            "version_dataset": version_dataset, "semilla": SEMILLA_OFICIAL,
            "total_historicas": len(registros), "train_size": int(len(idx_train)),
            "val_size": int(len(idx_val)), "test_size": int(len(idx_test)),
            "tasa_no_show_global": round(float(y_all.mean()), 4),
            "tasa_no_show_train": round(float(y_train.mean()), 4),
            "tasa_no_show_val": round(float(y_val.mean()), 4),
            "tasa_no_show_test": round(float(y_test.mean()), 4), "control_leakage": leakage,
        },
        "metricas_val": metricas_val, "metricas_test": metricas_test, "metricas_baseline_test": metricas_base,
        "auditoria_equidad": auditar_equidad_subgrupos(registros_test, y_test, probs_test, UMBRAL_ALTO),
        "importancia_global_variables": importancia_global(principal.named_steps["clf"].feature_importances_),
    }
    return Entrenamiento(artefacto, split)
