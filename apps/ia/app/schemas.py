"""Esquemas Pydantic del servicio IA autónomo.

Cumplen estrictamente con los schemas y contratos de `contracts/ia/` y `contracts/data/`.
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==============================================================================
# Features pre-cita (contracts/data/features.v1.schema.json)
# ==============================================================================

EspecialidadEnum = Literal["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"]
TipoPacienteEnum = Literal["NUEVO", "CONTINUADOR"]
CanalOrigenEnum = Literal["WEB", "CALL_CENTER", "PRESENCIAL"]
FranjaHorariaEnum = Literal["MANANA", "TARDE"]
DiaSemanaEnum = Literal["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO"]


class FeaturesPreCita(BaseModel):
    """Features crudas pre-cita según perfil de extracción v1."""

    model_config = ConfigDict(extra="forbid")

    especialidad: EspecialidadEnum
    tipo_paciente: TipoPacienteEnum
    canal_origen: CanalOrigenEnum
    franja_horaria: FranjaHorariaEnum
    dia_semana: DiaSemanaEnum
    antelacion_dias: int = Field(..., ge=0)
    inasistencias_previas: int = Field(..., ge=0)
    asistencias_previas: int = Field(..., ge=0)
    reprogramaciones_prev: int = Field(..., ge=0)


class SnapshotFeatures(BaseModel):
    """Features efectivas conocidas y derivadas (contracts/data/snapshot-features.v1.schema.json)."""

    model_config = ConfigDict(extra="forbid")

    especialidad: EspecialidadEnum
    tipo_paciente: TipoPacienteEnum
    canal_origen: CanalOrigenEnum
    franja_horaria: FranjaHorariaEnum
    dia_semana: DiaSemanaEnum
    antelacion_dias: int = Field(..., ge=0)
    inasistencias_previas: int = Field(..., ge=0)
    asistencias_previas: int = Field(..., ge=0)
    reprogramaciones_prev: int = Field(..., ge=0)
    tasa_no_show_previa: float = Field(..., ge=0.0, le=1.0)
    es_reserva_lejana: Literal[0, 1]


class Umbrales(BaseModel):
    """Umbrales operativos congelados para clasificación de riesgo."""

    model_config = ConfigDict(extra="forbid")

    medio: float = 0.3
    alto: float = 0.45


# ==============================================================================
# Inferencia individual (contracts/ia/predict-*.v1.schema.json)
# ==============================================================================

NivelRiesgoEnum = Literal["BAJO", "MEDIO", "ALTO"]


class PredictRequest(BaseModel):
    """Solicitud de inferencia individual."""

    model_config = ConfigDict(extra="forbid")

    version_contrato: Literal["1.0"] = "1.0"
    id_solicitud: UUID
    version_modelo: str = Field(..., min_length=1, max_length=100)
    version_features: Literal["pre-cita-v1"] = "pre-cita-v1"
    features: FeaturesPreCita


class PredictResponse(BaseModel):
    """Respuesta de inferencia individual con score, nivel, snapshot y explicabilidad."""

    model_config = ConfigDict(extra="forbid")

    version_contrato: Literal["1.0"] = "1.0"
    id_solicitud: UUID
    version_modelo: str = Field(..., min_length=1, max_length=100)
    version_features: Literal["pre-cita-v1"] = "pre-cita-v1"
    probabilidad_no_show: float = Field(..., ge=0.0, le=1.0)
    nivel_riesgo: NivelRiesgoEnum
    umbrales: Umbrales = Field(default_factory=Umbrales)
    features_snapshot: SnapshotFeatures
    explicabilidad_resumen: str = Field(..., min_length=1, max_length=255)
    es_simulacion: Literal[True] = True
    rotulo_etico: Literal["Resultado simulado — Dataset sintético acreditado (RF-056)"] = (
        "Resultado simulado — Dataset sintético acreditado (RF-056)"
    )


# ==============================================================================
# Inferencia por lote (contracts/ia/batch-*.v1.schema.json)
# ==============================================================================


class BatchItemRequest(BaseModel):
    """Elemento individual de un lote de inferencia."""

    model_config = ConfigDict(extra="forbid")

    id_item: str = Field(..., pattern=r"^[A-Za-z0-9_-]{1,64}$")
    features: FeaturesPreCita


class BatchRequest(BaseModel):
    """Solicitud de inferencia en lote (1..100 elementos)."""

    model_config = ConfigDict(extra="forbid")

    version_contrato: Literal["1.0"] = "1.0"
    id_solicitud: UUID
    version_modelo: str = Field(..., min_length=1, max_length=100)
    version_features: Literal["pre-cita-v1"] = "pre-cita-v1"
    items: list[BatchItemRequest] = Field(..., min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def validar_unicidad_ids(cls, v: list[BatchItemRequest]) -> list[BatchItemRequest]:
        ids = [item.id_item for item in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Los id_item dentro del lote deben ser estrictamente únicos.")
        return v


class BatchItemResponse(BaseModel):
    """Resultado individual de un ítem dentro de la respuesta en lote."""

    model_config = ConfigDict(extra="forbid")

    id_item: str = Field(..., pattern=r"^[A-Za-z0-9_-]{1,64}$")
    resultado: PredictResponse


class BatchResponse(BaseModel):
    """Respuesta completa de inferencia en lote."""

    model_config = ConfigDict(extra="forbid")

    version_contrato: Literal["1.0"] = "1.0"
    id_solicitud: UUID
    version_modelo: str = Field(..., min_length=1, max_length=100)
    items: list[BatchItemResponse]


# ==============================================================================
# Errores estándar de contrato (contracts/ia/error.v1.schema.json)
# ==============================================================================

CodigoErrorEnum = Literal[
    "NO_AUTENTICADO",
    "VALIDACION",
    "MODELO_NO_DISPONIBLE",
    "VERSION_MODELO_INCOMPATIBLE",
    "ERROR_INTERNO",
    "SOLICITUD_DEMASIADO_GRANDE",
]


class ErrorDetail(BaseModel):
    """Detalle del error en conformidad con error.v1.schema.json."""

    model_config = ConfigDict(extra="forbid")

    codigo: CodigoErrorEnum
    mensaje: str = Field(..., min_length=1, max_length=255)
    campos: dict[str, str] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Cuerpo de respuesta para errores HTTP del servicio IA."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


# ==============================================================================
# Metadatos del modelo (ModelMetadata en openapi.objetivo.v1.json)
# ==============================================================================


class ModelMetadata(BaseModel):
    """Metadatos del modelo activo expuestos en /v1/model."""

    model_config = ConfigDict(extra="forbid")

    version_contrato: Literal["1.0"] = "1.0"
    version_modelo: str = Field(..., min_length=1, max_length=100)
    version_features: Literal["pre-cita-v1"] = "pre-cita-v1"
    version_dataset: str = Field(..., min_length=1, max_length=100)
    umbrales: Umbrales = Field(default_factory=Umbrales)
    features_autorizadas: list[str] = Field(..., min_length=9, max_length=9)
    es_simulacion: Literal[True] = True
    rotulo_etico: Literal["Resultado simulado — Dataset sintético acreditado (RF-056)"] = (
        "Resultado simulado — Dataset sintético acreditado (RF-056)"
    )


# ==============================================================================
# Health schemas
# ==============================================================================


class LiveStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estado: Literal["vivo"] = "vivo"


class ReadyStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estado: Literal["listo"] = "listo"
