"""Validación cerrada de metadata v1 remota; independiente del proceso IA."""
from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.modules.ia.puerto import Cerrado


class Matriz(Cerrado):
    tn: int = Field(ge=0)
    fp: int = Field(ge=0)
    fn: int = Field(ge=0)
    tp: int = Field(ge=0)


class Bloque(Cerrado):
    umbral: float = Field(ge=0, le=1)
    f1_score: float = Field(ge=0, le=1)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    roc_auc: float = Field(ge=0, le=1)
    pr_auc: float = Field(ge=0, le=1)
    matriz_confusion: Matriz


class MetricasRemotas(Cerrado):
    version_modelo: str = Field(min_length=1, max_length=100)
    algoritmo: str = Field(min_length=1)
    semilla: int
    fecha_entrenamiento: str
    es_simulacion: Literal[True]
    rotulo_etico: Literal["Resultado simulado — Dataset sintético acreditado (RF-056)"]
    umbral_alto: Literal[0.45]
    umbral_medio: Literal[0.3]
    cumple_meta_f1_82: bool
    metricas_test: Bloque
    metricas_val: Bloque
    metricas_baseline_test: Bloque
    auditoria_equidad: dict[str, Any]
    importancia_global_variables: list[dict[str, Any]]

    @field_validator("es_simulacion", mode="before")
    @classmethod
    def simulacion(cls, value):
        if value is not True:
            raise ValueError("Rotulado sintético obligatorio")
        return value

    @model_validator(mode="after")
    def coherencia(self):
        if self.es_simulacion is not True or self.cumple_meta_f1_82 != (self.metricas_test.f1_score >= 0.82):
            raise ValueError("Métricas incompatibles")
        datetime.fromisoformat(self.fecha_entrenamiento)
        return self


class Split(Cerrado):
    filas: int = Field(ge=1)
    no_show: int = Field(ge=0)
    sha256: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    sha256_ids: str | None = Field(pattern=r"^[a-f0-9]{64}$")


class Particiones(Cerrado):
    train: Split
    val: Split
    test: Split


class Distribucion(Cerrado):
    atendidas: int = Field(ge=1)
    no_show: int = Field(ge=1)


class Leakage(Cerrado):
    aprobado: Literal[True]
    columnas_prohibidas_excluidas: list[str] = Field(min_length=8)
    interseccion_particiones: Literal[0]
    violaciones_temporales: Literal[0]
    invariante_paciente_nuevo_ok: Literal[True]

    @field_validator("aprobado", "invariante_paciente_nuevo_ok", mode="before")
    @classmethod
    def verdaderos(cls, value):
        if value is not True:
            raise ValueError("Declaración de leakage inválida")
        return value

    @field_validator("interseccion_particiones", "violaciones_temporales", mode="before")
    @classmethod
    def ceros(cls, value):
        if type(value) is not int or value != 0:
            raise ValueError("Declaración de leakage inválida")
        return value


class DatasetRemoto(Cerrado):
    version_contrato: Literal["1.0"]
    version_dataset: str = Field(min_length=1, max_length=100)
    version_features: Literal["pre-cita-v1"]
    proposito: Literal["LEGACY_IMPORT", "TRAINING_RUN"]
    fuente: Literal["LEGACY_METADATA_ONLY", "SINTETICO_GENERADO", "SNAPSHOT_SINTETICO_BACKEND"]
    linaje_completo: bool
    semilla: Literal[42]
    fecha_corte: date | None
    generado_en: datetime
    sha256_raw: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    total_historicas: int = Field(ge=1000)
    distribucion: Distribucion
    particiones: Particiones
    sin_interseccion_ids: Literal[True]
    control_leakage: Leakage
    es_simulacion: Literal[True]

    @field_validator("sin_interseccion_ids", "es_simulacion", mode="before")
    @classmethod
    def verdaderos(cls, value):
        if value is not True:
            raise ValueError("Declaración sintética inválida")
        return value

    @model_validator(mode="after")
    def coherencia(self):
        splits = [self.particiones.train, self.particiones.val, self.particiones.test]
        if (sum(s.filas for s in splits) != self.total_historicas
                or sum(s.no_show for s in splits) != self.distribucion.no_show
                or self.distribucion.atendidas + self.distribucion.no_show != self.total_historicas
                or any(s.no_show > s.filas for s in splits) or self.es_simulacion is not True):
            raise ValueError("Distribución incompatible")
        training = self.proposito == "TRAINING_RUN"
        hashes = [self.sha256_raw] + [h for s in splits for h in (s.sha256, s.sha256_ids)]
        if (self.linaje_completo != training or (self.fecha_corte is not None) != training
                or any((h is not None) != training for h in hashes)
                or (self.fuente != "LEGACY_METADATA_ONLY") != training):
            raise ValueError("Linaje incompatible")
        return self
