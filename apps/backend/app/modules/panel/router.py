from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.reloj import reloj
from app.modules.auth.public import requiere_roles
from app.modules.panel import service
from app.modules.panel.schemas import Especialidad, PanelPendientesOut, PanelResumenOut, TipoPendiente

router = APIRouter(prefix="/panel", tags=["panel"],
                   dependencies=[Depends(requiere_roles("ADMINISTRADOR", "RECEPCION"))])


@router.get("/resumen", response_model=PanelResumenOut)
def resumen(fecha: date | None = None, especialidad: Especialidad | None = None,
            db: Session = Depends(get_db), ahora: datetime = Depends(reloj)):
    """Estado actual de la jornada programada; no reconstruye cierres históricos."""
    return service.obtener_resumen(db, fecha=fecha, especialidad=especialidad, ahora=ahora)


@router.get("/pendientes", response_model=PanelPendientesOut)
def pendientes(tipo: TipoPendiente, fecha: date | None = None, especialidad: Especialidad | None = None,
               limite: int = Query(default=20, ge=1, le=100),
               desplazamiento: int = Query(default=0, ge=0),
               db: Session = Depends(get_db), ahora: datetime = Depends(reloj)):
    """Pendientes accionables, con total completo y página del mismo snapshot SQL."""
    return service.listar_pendientes(db, fecha=fecha, especialidad=especialidad, ahora=ahora,
                                    tipo=tipo, limite=limite, desplazamiento=desplazamiento)
