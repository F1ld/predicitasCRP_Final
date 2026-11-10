"""Contrato público v1 del Panel Operativo (RF-083, RF-085..087)."""
from datetime import date
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.core.dominio import (CANALES_CONTACTO, ESPECIALIDADES, ESTADOS_CITA,
                              ESTADOS_CUPO, ESTADOS_INTERVENCION, NIVELES_RIESGO)

Especialidad = Literal[ESPECIALIDADES]
TipoPendiente = Literal["CITAS_SIN_INTERVENCION", "INTERVENCIONES_SIN_RESPUESTA", "OFERTAS_EN_CURSO"]
Conteo = Annotated[int, Field(ge=0)]


class ContextoPanelOut(BaseModel):
    fecha: date
    especialidad: Especialidad | None
    zona_horaria: Literal["America/Lima"] = "America/Lima"
    generado_en: AwareDatetime


class CitasResumenOut(BaseModel):
    total: Conteo
    por_estado: dict[Literal[ESTADOS_CITA], Conteo]
    por_riesgo: dict[Literal[NIVELES_RIESGO + ("SIN_PREDICCION",)], Conteo]


class IntervencionesResumenOut(BaseModel):
    total: Conteo
    citas_con_intervencion: Conteo
    por_estado: dict[Literal[ESTADOS_INTERVENCION], Conteo]


class CuposResumenOut(BaseModel):
    total_liberados: Conteo
    por_estado: dict[Literal[ESTADOS_CUPO], Conteo]
    disponibles_para_ofrecer: Conteo
    ofertas_en_curso: Conteo
    reasignados_confirmados: Conteo
    tasa_recuperacion_pct: Annotated[float, Field(ge=0, le=100)] | None


class PendientesResumenOut(BaseModel):
    citas_sin_intervencion: Conteo
    intervenciones_sin_respuesta: Conteo
    ofertas_en_curso: Conteo


class PanelResumenOut(ContextoPanelOut):
    citas: CitasResumenOut
    intervenciones: IntervencionesResumenOut
    cupos: CuposResumenOut
    pendientes: PendientesResumenOut


class CitaPendienteOut(BaseModel):
    id_cita: int
    id_cita_externa: str
    paciente_anon_id: str
    fecha_hora_cita: AwareDatetime
    especialidad: Especialidad
    medico: str
    estado_cita: Literal[ESTADOS_CITA]


class CitaSinIntervencionOut(CitaPendienteOut):
    tipo: Literal["CITAS_SIN_INTERVENCION"]
    id_prediccion: int
    nivel_riesgo: Literal["ALTO", "MEDIO"]
    probabilidad_no_show: Annotated[float, Field(ge=0, le=1)]


class IntervencionSinRespuestaOut(CitaPendienteOut):
    tipo: Literal["INTERVENCIONES_SIN_RESPUESTA"]
    id_intervencion: int
    canal_contacto: Literal[CANALES_CONTACTO]
    estado_intervencion: Literal["ENVIADA", "ENTREGADA"]
    fecha_hora_envio: AwareDatetime | None


class OfertaEnCursoOut(BaseModel):
    tipo: Literal["OFERTAS_EN_CURSO"]
    id_cupo_liberado: int
    id_cita_origen: int
    fecha_hora_cupo: AwareDatetime
    especialidad: Especialidad
    medico: str
    estado_cupo: Literal["EN_OFERTA"]
    origen_liberacion: str


ItemPendiente = Annotated[
    CitaSinIntervencionOut | IntervencionSinRespuestaOut | OfertaEnCursoOut,
    Field(discriminator="tipo"),
]


class PanelPendientesOut(ContextoPanelOut):
    tipo: TipoPendiente
    total: Conteo
    limite: Annotated[int, Field(ge=1, le=100)]
    desplazamiento: Conteo
    items: list[ItemPendiente]
