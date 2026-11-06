"""Lectura de ofertas sobre la bitácora existente: sin tablas ni writes."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.auditoria.public import EventoEntidad, eventos_entidad
from app.modules.lista_espera.schemas import HistorialOfertaOut

ACCIONES = ("OFERTAR", "RECHAZAR", "DESISTIR", "CERRAR_OFERTA")


@dataclass(frozen=True)
class OfertasCupo:
    vigente: EventoEntidad | None
    historial: tuple[HistorialOfertaOut, ...]


def proyectar(eventos: list[EventoEntidad]) -> OfertasCupo:
    vigente = None
    historial = []
    for event in eventos:
        if event.accion == "OFERTAR":
            id_candidato = event.datos_after.get("id_candidato")
            if not isinstance(id_candidato, int):
                continue  # no inventar identidad de eventos legacy incompletos
            vigente = event
            historial.append(HistorialOfertaOut(id_candidato=id_candidato, fecha_hora_oferta=event.creado_en))
        elif vigente and event.datos_after.get("id_oferta") == vigente.id_log:
            cierre = event.datos_after.get("cierre")
            if cierre in ("RECHAZA", "SIN_RESPUESTA", "REASIGNADO"):
                historial[-1].cierre = cierre
                vigente = None
    return OfertasCupo(vigente=vigente, historial=tuple(historial))


def consultar(db: Session, id_cupo: int) -> OfertasCupo:
    return proyectar(eventos_entidad(db, modulo="REASIGNACION", entidad="cupos_liberados",
                                   id_entidad=id_cupo, acciones=ACCIONES))
