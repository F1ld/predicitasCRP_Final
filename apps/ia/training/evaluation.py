"""Split estratificado y controles legacy; sin obtención implícita de datos."""
from dataclasses import dataclass

import numpy as np
from sklearn.model_selection import train_test_split

from app.core.features import FEATURES_ENTRADA_MODELO

SEMILLA_OFICIAL = 42
COLUMNAS_PROHIBIDAS_LEAKAGE = {
    "id_cita", "id_cita_externa", "paciente_anon_id", "estado_actual", "target_no_show",
    "fecha_hora_cita", "fecha_registro_cita", "medico",
}


@dataclass(frozen=True)
class Particiones:
    train: np.ndarray
    val: np.ndarray
    test: np.ndarray


def particionar(y_all: np.ndarray) -> Particiones:
    indices = np.arange(len(y_all))
    idx_train, idx_temp, _, y_temp = train_test_split(
        indices, y_all, test_size=0.30, stratify=y_all, random_state=SEMILLA_OFICIAL)
    idx_val, idx_test, _, _ = train_test_split(
        idx_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=SEMILLA_OFICIAL)
    return Particiones(idx_train, idx_val, idx_test)


def verificar_sin_data_leakage(registros, idx_train, idx_val, idx_test):
    interseccion_prohibida = set(FEATURES_ENTRADA_MODELO) & COLUMNAS_PROHIBIDAS_LEAKAGE
    if interseccion_prohibida:
        raise ValueError(f"Data leakage detectado: columnas prohibidas en X: {interseccion_prohibida}")
    ids_train = {registros[i]["id_cita_externa"] for i in idx_train}
    ids_val = {registros[i]["id_cita_externa"] for i in idx_val}
    ids_test = {registros[i]["id_cita_externa"] for i in idx_test}
    if (ids_train & ids_val) or (ids_train & ids_test) or (ids_val & ids_test):
        raise ValueError("Data leakage detectado: contaminación de registros entre Train, Val y Test.")
    violaciones_temporales = 0
    violaciones_nuevo = 0
    for r in registros:
        if int(r["antelacion_dias"]) < 0:
            violaciones_temporales += 1
        if r["tipo_paciente"] == "NUEVO" and (r["inasistencias_previas"] > 0 or r["asistencias_previas"] > 0):
            violaciones_nuevo += 1
    if violaciones_temporales > 0 or violaciones_nuevo > 0:
        raise ValueError(f"Inconsistencia temporal/clínica: antelacion<0={violaciones_temporales}, nuevo_con_historial={violaciones_nuevo}")
    return {
        "aprobado": True, "columnas_prohibidas_excluidas": sorted(COLUMNAS_PROHIBIDAS_LEAKAGE),
        "interseccion_particiones": 0, "violaciones_temporales": 0, "invariante_paciente_nuevo_ok": True,
    }
