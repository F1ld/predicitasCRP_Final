"""DTOs autónomos de metadata; no importan código del backend."""
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class MatrizConfusion(ClosedModel):
    tn: int
    fp: int
    fn: int
    tp: int


class BloqueMetricas(ClosedModel):
    umbral: float
    f1_score: float
    precision: float
    recall: float
    roc_auc: float
    pr_auc: float
    matriz_confusion: MatrizConfusion


class MetricasModelo(ClosedModel):
    version_modelo: str
    algoritmo: str
    semilla: int
    fecha_entrenamiento: str
    es_simulacion: Literal[True]
    rotulo_etico: str
    umbral_alto: Literal[0.45]
    umbral_medio: Literal[0.3]
    cumple_meta_f1_82: bool
    metricas_test: BloqueMetricas
    metricas_val: BloqueMetricas
    metricas_baseline_test: BloqueMetricas
    auditoria_equidad: dict[str, Any]
    importancia_global_variables: list[dict[str, Any]]


class SplitLegacy(ClosedModel):
    filas: int = Field(ge=1)
    no_show: int = Field(ge=0)
    sha256: None
    sha256_ids: None


class ParticionesLegacy(ClosedModel):
    train: SplitLegacy
    val: SplitLegacy
    test: SplitLegacy


class Distribucion(ClosedModel):
    atendidas: int = Field(ge=1)
    no_show: int = Field(ge=1)


class ControlLeakage(ClosedModel):
    aprobado: Literal[True]
    columnas_prohibidas_excluidas: list[str] = Field(min_length=8)
    interseccion_particiones: Literal[0]
    violaciones_temporales: Literal[0]
    invariante_paciente_nuevo_ok: Literal[True]


class DatasetLegacy(ClosedModel):
    version_contrato: Literal["1.0"]
    version_dataset: str = Field(min_length=1, max_length=100)
    version_features: Literal["pre-cita-v1"]
    proposito: Literal["LEGACY_IMPORT"]
    fuente: Literal["LEGACY_METADATA_ONLY"]
    linaje_completo: Literal[False]
    semilla: Literal[42]
    fecha_corte: None
    generado_en: datetime
    sha256_raw: None
    total_historicas: int = Field(ge=1000)
    distribucion: Distribucion
    particiones: ParticionesLegacy
    sin_interseccion_ids: Literal[True]
    control_leakage: ControlLeakage
    es_simulacion: Literal[True]
