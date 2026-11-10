from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exportacion import responder
from app.core.http import ip_cliente
from app.modules.auth.public import Principal as Usuario, requiere_roles
from app.modules.reportes import service
from app.modules.reportes.schemas import EspecialidadRep01, NivelRiesgoRep01, Rep01Out, Rep02Out, Rep03Out

router = APIRouter(prefix="/reportes", tags=["reportes"])

ROLES_REPORTE = ("ADMINISTRADOR", "RECEPCION")


@router.get("/rep-01", response_model=Rep01Out, dependencies=[Depends(requiere_roles("RECEPCION"))])
def obtener_rep01(
    fecha: Annotated[str, Query(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")],
    especialidad: EspecialidadRep01 | None = None,
    nivel_riesgo: NivelRiesgoRep01 | None = None,
    db: Session = Depends(get_db),
):
    return service.obtener_rep01(db, fecha=fecha, especialidad=especialidad, nivel_riesgo=nivel_riesgo)


@router.get("/rep-02", response_model=Rep02Out)
def obtener_rep02(
    request: Request,
    desde: str | None = None,
    hasta: str | None = None,
    canal_contacto: str | None = None,
    nivel_riesgo: str | None = None,
    especialidad: str | None = None,
    formato: str = "json",
    usuario: Usuario = Depends(requiere_roles(*ROLES_REPORTE)),
    db: Session = Depends(get_db),
):
    reporte, formato_norm = service.preparar_rep02(
        db,
        usuario=usuario,
        ip=ip_cliente(request),
        formato=formato,
        desde=desde,
        hasta=hasta,
        canal_contacto=canal_contacto,
        nivel_riesgo=nivel_riesgo,
        especialidad=especialidad,
    )
    if formato_norm in ("csv", "xlsx"):
        COLUMNAS_REP02 = [
            "id_intervencion",
            "id_cita_externa",
            "especialidad",
            "nivel_riesgo",
            "canal_contacto",
            "estado_intervencion",
            "respuesta_paciente",
            "tiempo_respuesta_minutos",
            "cupo_liberado",
        ]
        filas_dicts = [f.model_dump() for f in reporte.filas]
        return responder(filas_dicts, COLUMNAS_REP02, formato_norm, "rep-02")
    return reporte


@router.get("/rep-03", response_model=Rep03Out)
def obtener_rep03(
    request: Request,
    desde: str | None = None,
    hasta: str | None = None,
    especialidad: str | None = None,
    id_operador: int | None = None,
    formato: str = Query(default="json", regex="^(json|csv|xlsx)$"),
    usuario: Usuario = Depends(requiere_roles(*ROLES_REPORTE)),
    db: Session = Depends(get_db),
):
    return service.preparar_rep03(
        db,
        usuario=usuario,
        ip=ip_cliente(request),
        formato=formato,
        desde=desde,
        hasta=hasta,
        especialidad=especialidad,
        id_operador=id_operador,
    )


# Alias directos para las rutas intuitivas
@router.get("/intervenciones", response_model=Rep02Out)
def alias_reporte_intervenciones(
    request: Request,
    desde: str | None = None,
    hasta: str | None = None,
    canal_contacto: str | None = None,
    nivel_riesgo: str | None = None,
    especialidad: str | None = None,
    formato: str = Query(default="json", regex="^(json|csv|xlsx)$"),
    usuario: Usuario = Depends(requiere_roles(*ROLES_REPORTE)),
    db: Session = Depends(get_db),
):
    return obtener_rep02(
        request=request,
        desde=desde,
        hasta=hasta,
        canal_contacto=canal_contacto,
        nivel_riesgo=nivel_riesgo,
        especialidad=especialidad,
        formato=formato,
        usuario=usuario,
        db=db,
    )


@router.get("/reasignaciones", response_model=Rep03Out)
def alias_reporte_reasignaciones(
    request: Request,
    desde: str | None = None,
    hasta: str | None = None,
    especialidad: str | None = None,
    id_operador: int | None = None,
    formato: str = Query(default="json", regex="^(json|csv|xlsx)$"),
    usuario: Usuario = Depends(requiere_roles(*ROLES_REPORTE)),
    db: Session = Depends(get_db),
):
    return obtener_rep03(
        request=request,
        desde=desde,
        hasta=hasta,
        especialidad=especialidad,
        id_operador=id_operador,
        formato=formato,
        usuario=usuario,
        db=db,
    )
