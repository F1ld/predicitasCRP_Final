"""Metadata interna normalizada; no cambia los esquemas públicos existentes."""
from typing import Any

from app.modules.ia.dto_motor import Cerrado

FEATURES_MODELO = ["antelacion_dias", "inasistencias_previas", "asistencias_previas",
    "reprogramaciones_prev", "tasa_no_show_previa", "es_reserva_lejana", "especialidad",
    "tipo_paciente", "canal_origen", "franja_horaria", "dia_semana"]
ROTULO_PUBLICO = "Resultado simulado — Dataset sintético acreditado (RF-056 / RN16)"


class DatosDatasetMotor(Cerrado):
    version_dataset: str
    semilla: int
    total_historicas: int
    train_size: int
    val_size: int
    test_size: int
    tasa_no_show_global: float
    tasa_no_show_train: float
    tasa_no_show_val: float
    tasa_no_show_test: float
    control_leakage: dict[str, Any]
    rotulo_etico: str
