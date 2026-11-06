"""Evaluación y equidad extraídas sin cambiar fórmulas, bordes o redondeos."""
import numpy as np
from sklearn.metrics import (
    average_precision_score, confusion_matrix, f1_score, precision_score,
    recall_score, roc_auc_score,
)


def calcular_metricas(y_true, probs, umbral):
    # Evaluación histórica usa >=; no confundir con nivel ALTO (> 0.450).
    y_pred = (probs >= umbral).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "umbral": round(float(umbral), 3),
        "f1_score": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, probs)), 4),
        "pr_auc": round(float(average_precision_score(y_true, probs)), 4),
        "matriz_confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def auditar_equidad_subgrupos(registros_test, y_test, probs_test, umbral):
    resultado = {}
    for dim in ("especialidad", "tipo_paciente", "franja_horaria"):
        grupos = {}
        valores = sorted({str(r[dim]) for r in registros_test})
        for val in valores:
            mask = np.array([str(r[dim]) == val for r in registros_test])
            if mask.sum() == 0 or len(np.unique(y_test[mask])) < 2:
                continue
            y_sub = y_test[mask]
            p_sub = probs_test[mask]
            pred_sub = (p_sub >= umbral).astype(int)
            grupos[val] = {
                "n": int(mask.sum()), "tasa_positiva_real": round(float(y_sub.mean()), 4),
                "f1_score": round(float(f1_score(y_sub, pred_sub, zero_division=0)), 4),
                "recall": round(float(recall_score(y_sub, pred_sub, zero_division=0)), 4),
                "precision": round(float(precision_score(y_sub, pred_sub, zero_division=0)), 4),
            }
        resultado[dim] = grupos
    return resultado


def importancia_global(importancias_raw):
    agrupada = [
        {"variable": "inasistencias_previas / tasa_previa", "importancia": int(importancias_raw[1] + importancias_raw[4])},
        {"variable": "antelacion_dias", "importancia": int(importancias_raw[0] + importancias_raw[5])},
        {"variable": "reprogramaciones_prev", "importancia": int(importancias_raw[3])},
        {"variable": "asistencias_previas", "importancia": int(importancias_raw[2])},
        {"variable": "tipo_paciente", "importancia": int(np.sum(importancias_raw[9:11]))},
        {"variable": "canal_origen", "importancia": int(np.sum(importancias_raw[11:14]))},
        {"variable": "franja_horaria", "importancia": int(np.sum(importancias_raw[14:16]))},
        {"variable": "especialidad", "importancia": int(np.sum(importancias_raw[6:9]))},
        {"variable": "dia_semana", "importancia": int(np.sum(importancias_raw[16:22]))},
    ]
    agrupada.sort(key=lambda x: x["importancia"], reverse=True)
    return agrupada
