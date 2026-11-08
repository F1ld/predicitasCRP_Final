"""Puerto de inferencia pre-cita. Sin HTTP, BD, entrenamiento ni imports ML."""
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import Field
from app.modules.ia.dto_motor import Cerrado

if TYPE_CHECKING:
    from app.modules.ia.metadata_motor import DatosDatasetMotor
    from app.modules.ia.schemas import MetricasModeloOut


class FeaturesMotor(Cerrado):
    especialidad: Literal["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"]
    tipo_paciente: Literal["NUEVO", "CONTINUADOR"]
    canal_origen: Literal["WEB", "CALL_CENTER", "PRESENCIAL"]
    franja_horaria: Literal["MANANA", "TARDE"]
    dia_semana: Literal["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO"]
    antelacion_dias: int = Field(ge=0)
    inasistencias_previas: int = Field(ge=0)
    asistencias_previas: int = Field(ge=0)
    reprogramaciones_prev: int = Field(ge=0)

    def snapshot(self) -> dict:
        # El backend conserva y verifica el snapshot enviado a persistencia.
        return self.model_dump() | {
            "tasa_no_show_previa": round(self.inasistencias_previas /
                (self.asistencias_previas + self.inasistencias_previas + 1.0), 4),
            "es_reserva_lejana": int(self.antelacion_dias >= 15),
        }


class ResultadoMotor(Cerrado):
    version_modelo: str = Field(min_length=1, max_length=100)
    probabilidad_no_show: Decimal = Field(ge=0, le=1)
    nivel_riesgo: Literal["BAJO", "MEDIO", "ALTO"]
    umbral_aplicado: Decimal
    features_snapshot: dict
    explicabilidad_resumen: str = Field(min_length=1, max_length=255)


class MotorPredictivo(Protocol):
    def version(self) -> str: ...

    def predecir(self, features: FeaturesMotor, *, version: str) -> ResultadoMotor: ...

    def predecir_lote(self, features: list[FeaturesMotor], *, version: str) -> list[ResultadoMotor]: ...

    def metricas(self) -> "MetricasModeloOut": ...

    def dataset(self) -> "DatosDatasetMotor": ...

    def close(self) -> None: ...
