from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errores import Validacion
from app.core.exportacion import responder
from app.core.http import ip_cliente
from app.modules.auditoria.public import registrar_evento
from app.modules.auth.public import Principal as Usuario, requiere_roles
from app.modules.reportes import service
from app.modules.reportes.schemas import Rep02Out, Rep03Out

router = APIRouter(prefix="/reportes", tags=["reportes"])

ROLES_REPORTE = ("ADMINISTRADOR", "RECEPCION")


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
    formato_norm = (formato or "json").lower()
    if formato_norm not in ("json", "csv", "xlsx"):
        raise Validacion("Formato no disponible", codigo="FORMATO_NO_DISPONIBLE", campos={"formato": "Formato no disponible"})

    if canal_contacto and canal_contacto.upper() not in ("WHATSAPP", "SMS", "LLAMADA_TELEFONICA"):
        raise Validacion("Canal de contacto no admitido", campos={"canal_contacto": "Canal no admitido"})

    reporte = service.generar_rep02(
        db,
        desde=desde,
        hasta=hasta,
        canal_contacto=canal_contacto,
        nivel_riesgo=nivel_riesgo,
        especialidad=especialidad,
    )
    if formato_norm in ("csv", "xlsx"):
        filtros = {}
        if desde:
            filtros["desde"] = desde
        if hasta:
            filtros["hasta"] = hasta
        if especialidad:
            filtros["especialidad"] = especialidad.upper()
        if canal_contacto:
            filtros["canal_contacto"] = canal_contacto.upper()
        if nivel_riesgo:
            filtros["nivel_riesgo"] = nivel_riesgo.upper()

        registrar_evento(
            db,
            modulo="REPORTES",
            accion="EXPORT",
            entidad_afectada="rep-02",
            direccion_ip=ip_cliente(request),
            id_usuario=usuario.id_usuario,
            datos_after={"formato": formato_norm, "filtros": filtros},
        )
        db.commit()

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
    desde: str | None = None,
    hasta: str | None = None,
    especialidad: str | None = None,
    id_operador: int | None = None,
    formato: str = Query(default="json", regex="^(json|csv|xlsx)$"),
    _: Usuario = Depends(requiere_roles(*ROLES_REPORTE)),
    db: Session = Depends(get_db),
):
    reporte = service.generar_rep03(
        db,
        desde=desde,
        hasta=hasta,
        especialidad=especialidad,
        id_operador=id_operador,
    )
    if formato in ("csv", "xlsx"):
        contenido_csv = service.generar_rep03_csv(reporte)
        return Response(
            content=contenido_csv.encode("utf-8-sig"),
            media_type="text/csv" if formato == "csv" else "application/vnd.ms-excel",
            headers={"Content-Disposition": f'attachment; filename="rep-03.{formato}"'},
        )
    return reporte


# Alias directos para las rutas intuitivas
@router.get("/intervenciones", response_model=Rep02Out)
def alias_reporte_intervenciones(
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
        desde=desde,
        hasta=hasta,
        canal_contacto=canal_contacto,
        nivel_riesgo=nivel_riesgo,
        especialidad=especialidad,
        formato=formato,
        _=usuario,
        db=db,
    )


@router.get("/reasignaciones", response_model=Rep03Out)
def alias_reporte_reasignaciones(
    desde: str | None = None,
    hasta: str | None = None,
    especialidad: str | None = None,
    id_operador: int | None = None,
    formato: str = Query(default="json", regex="^(json|csv|xlsx)$"),
    usuario: Usuario = Depends(requiere_roles(*ROLES_REPORTE)),
    db: Session = Depends(get_db),
):
    return obtener_rep03(
        desde=desde,
        hasta=hasta,
        especialidad=especialidad,
        id_operador=id_operador,
        formato=formato,
        _=usuario,
        db=db,
    )
