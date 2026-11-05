from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errores import NoEncontrado, Validacion
from app.core.http import ip_cliente
from app.modules.auth.dependencies import requiere_roles
from app.modules.auth.models import Usuario
from app.modules.citas.reglas import LIMA
from app.modules.citas.router import reloj
from app.modules.intervenciones import reglas, repository, service
from app.modules.intervenciones.models import Intervencion
from app.modules.intervenciones.schemas import (
    BandejaIntervencionesOut,
    IntervencionCreateIn,
    IntervencionEstadoIn,
    IntervencionOut,
    IntervencionRespuestaIn,
    LiberarCupoIn,
    PaginaElegiblesOut,
    PaginaIntervencionesOut,
    PlantillaOut,
)
from app.modules.lista_espera.schemas import CupoLiberadoOut

router = APIRouter(tags=["intervenciones"])

ROLES_LECTURA = ("ADMINISTRADOR", "RECEPCION", "TECNICO_IA")
ROLES_OPERACION = ("ADMINISTRADOR", "RECEPCION")


def modo_sombra() -> bool:
    """Verifica si el sistema de intervenciones opera en modo sombra (simulación sin contacto)."""
    return getattr(get_settings(), "intervencion_modo_sombra", False)


@router.get("/intervenciones/plantillas", response_model=list[PlantillaOut])
def listar_plantillas(
    _: Usuario = Depends(requiere_roles(*ROLES_OPERACION)),
):
    """M05-E09: Catálogo de plantillas aprobadas por canal de contacto."""
    return reglas.obtener_catalogo_plantillas()


@router.get("/intervenciones/elegibles", response_model=PaginaElegiblesOut)
def listar_intervenciones_elegibles(
    desde: str | None = None,
    hasta: str | None = None,
    especialidad: str | None = None,
    nivel_riesgo: str | None = None,
    limite: int = Query(default=50, ge=1, le=200),
    desplazamiento: int = Query(default=0, ge=0),
    ahora: datetime = Depends(reloj),
    _: Usuario = Depends(requiere_roles(*ROLES_OPERACION)),
    db: Session = Depends(get_db),
):
    if nivel_riesgo and nivel_riesgo.upper() not in ("ALTO", "MEDIO"):
        raise Validacion(
            f"El nivel de riesgo '{nivel_riesgo}' no es elegible para intervención",
            campos={"nivel_riesgo": "Solo ALTO y MEDIO son elegibles"},
        )
    return service.listar_citas_elegibles(
        db,
        desde=desde,
        hasta=hasta,
        especialidad=especialidad,
        nivel_riesgo=nivel_riesgo,
        limite=limite,
        desplazamiento=desplazamiento,
        ahora=ahora,
    )


@router.get("/intervenciones", response_model=PaginaIntervencionesOut)
def listar_intervenciones(
    nivel_riesgo: str | None = None,
    especialidad: str | None = None,
    estado_intervencion: str | None = None,
    canal_contacto: str | None = None,
    respuesta_paciente: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    id_cita: int | None = None,
    limite: int = Query(default=50, ge=1, le=200),
    desplazamiento: int = Query(default=0, ge=0),
    _: Usuario = Depends(requiere_roles(*ROLES_LECTURA)),
    db: Session = Depends(get_db),
):
    bandeja = service.listar_bandeja_intervenciones(
        db,
        nivel_riesgo=nivel_riesgo,
        especialidad=especialidad,
        estado_intervencion=estado_intervencion,
        canal_contacto=canal_contacto,
    )
    historial = [service._enriquecer_out(i, db=db) for i in repository.listar_historial(db, estado_intervencion=estado_intervencion, canal_contacto=canal_contacto, limite=1000)]
    if id_cita:
        historial = [h for h in historial if h.id_cita == id_cita]
    if respuesta_paciente:
        historial = [h for h in historial if h.respuesta_paciente == respuesta_paciente.upper()]
    if desde:
        try:
            d_dt = datetime.fromisoformat(desde)
            if d_dt.tzinfo is None:
                d_dt = d_dt.replace(tzinfo=LIMA)
            historial = [h for h in historial if h.fecha_hora_envio >= d_dt]
        except ValueError:
            pass
    if hasta:
        try:
            h_dt = datetime.fromisoformat(f"{hasta}T23:59:59")
            if h_dt.tzinfo is None:
                h_dt = h_dt.replace(tzinfo=LIMA)
            historial = [h for h in historial if h.fecha_hora_envio <= h_dt]
        except ValueError:
            pass

    total = len(historial)
    items_paginados = historial[desplazamiento : desplazamiento + limite]

    return PaginaIntervencionesOut(
        total=total,
        limite=limite,
        desplazamiento=desplazamiento,
        items=items_paginados,
        total_sugeridas=bandeja.total_sugeridas,
        total_intervenciones=total,
        citas_sugeridas=bandeja.citas_sugeridas,
        historial_intervenciones=items_paginados,
    )


@router.post("/intervenciones", response_model=IntervencionOut, status_code=201)
def crear_intervencion_directa(
    datos: IntervencionCreateIn,
    request: Request,
    ahora: datetime = Depends(reloj),
    sombra: bool = Depends(modo_sombra),
    usuario: Usuario = Depends(requiere_roles(*ROLES_OPERACION)),
    db: Session = Depends(get_db),
):
    """M05-E02: Creación de intervención desde el formulario modal de frontend."""
    if not datos.id_cita:
        raise Validacion(
            "El identificador de la cita (id_cita) es obligatorio en el cuerpo de la solicitud",
            campos={"id_cita": "Campo obligatorio"},
        )
    return service.crear_intervencion(
        db,
        datos.id_cita,
        datos,
        usuario=usuario,
        ip=ip_cliente(request),
        ahora=ahora,
        modo_sombra_activo=sombra,
        validar_consentimiento=True,
    )


@router.post("/intervenciones/{id_intervencion}/estado", response_model=IntervencionOut)
def cambiar_estado(
    id_intervencion: int,
    datos: IntervencionEstadoIn,
    request: Request,
    ahora: datetime = Depends(reloj),
    usuario: Usuario = Depends(requiere_roles(*ROLES_OPERACION)),
    db: Session = Depends(get_db),
):
    """M05-E05: Registro explícito del avance de envío/entrega/fallo."""
    return service.cambiar_estado_intervencion(
        db,
        id_intervencion,
        datos.estado_intervencion,
        usuario=usuario,
        ip=ip_cliente(request),
        ahora=ahora,
    )


@router.post("/intervenciones/{id_intervencion}/respuesta", response_model=IntervencionOut)
def registrar_respuesta_post(
    id_intervencion: int,
    datos: IntervencionRespuestaIn,
    request: Request,
    ahora: datetime = Depends(reloj),
    usuario: Usuario = Depends(requiere_roles(*ROLES_OPERACION)),
    db: Session = Depends(get_db),
):
    """M05-E06: Registro de respuesta del paciente (sin transicionar la cita)."""
    return service.registrar_respuesta_intervencion(
        db,
        id_intervencion,
        datos,
        usuario=usuario,
        ip=ip_cliente(request),
        ahora=ahora,
        cambiar_cita=False,
    )


@router.post("/intervenciones/{id_intervencion}/optout", response_model=IntervencionOut)
def registrar_optout_endpoint(
    id_intervencion: int,
    request: Request,
    usuario: Usuario = Depends(requiere_roles(*ROLES_OPERACION)),
    db: Session = Depends(get_db),
):
    """M05-E07: Registro de derecho de oposición posterior (opt-out)."""
    return service.registrar_optout_intervencion(
        db,
        id_intervencion,
        usuario=usuario,
        ip=ip_cliente(request),
    )


@router.post("/intervenciones/{id_intervencion}/liberar-cupo", response_model=CupoLiberadoOut, status_code=201)
def liberar_cupo_endpoint(
    id_intervencion: int,
    request: Request,
    datos: LiberarCupoIn | None = None,
    ahora: datetime = Depends(reloj),
    usuario: Usuario = Depends(requiere_roles(*ROLES_OPERACION)),
    db: Session = Depends(get_db),
):
    """M05-E08: Liberación atómica de cita y cupo tras confirmación del operador."""
    return service.liberar_cupo_desde_intervencion(
        db,
        id_intervencion,
        datos.motivo if datos else None,
        usuario=usuario,
        ip=ip_cliente(request),
        ahora=ahora,
    )


@router.get("/intervenciones/{id_intervencion}", response_model=IntervencionOut)
def obtener_intervencion(
    id_intervencion: int,
    _: Usuario = Depends(requiere_roles(*ROLES_LECTURA)),
    db: Session = Depends(get_db),
):
    intervencion = db.get(Intervencion, id_intervencion)
    if intervencion is None:
        raise NoEncontrado(f"No existe la intervención {id_intervencion}")
    return service._enriquecer_out(intervencion, db=db)


@router.patch("/intervenciones/{id_intervencion}", response_model=IntervencionOut)
def registrar_respuesta_patch(
    id_intervencion: int,
    datos: IntervencionRespuestaIn,
    request: Request,
    usuario: Usuario = Depends(requiere_roles(*ROLES_OPERACION)),
    db: Session = Depends(get_db),
):
    """Endpoint legado PATCH: registra respuesta y actualiza cita si aplica."""
    return service.registrar_respuesta_intervencion(
        db,
        id_intervencion,
        datos,
        usuario=usuario,
        ip=ip_cliente(request),
        cambiar_cita=True,
        validar_transicion=False,
    )


@router.get("/citas/{id_cita}/intervenciones", response_model=list[IntervencionOut])
def listar_intervenciones_de_cita(
    id_cita: int,
    _: Usuario = Depends(requiere_roles(*ROLES_LECTURA)),
    db: Session = Depends(get_db),
):
    return [service._enriquecer_out(i) for i in repository.listar_por_cita(db, id_cita)]


@router.post("/citas/{id_cita}/intervenciones", response_model=IntervencionOut)
def crear_intervencion_para_cita(
    id_cita: int,
    datos: IntervencionCreateIn,
    request: Request,
    ahora: datetime = Depends(reloj),
    sombra: bool = Depends(modo_sombra),
    usuario: Usuario = Depends(requiere_roles(*ROLES_OPERACION)),
    db: Session = Depends(get_db),
):
    """Endpoint legado: creación vinculada directamente a la ruta /citas/{id_cita}."""
    # Para el endpoint legado, el estado por defecto histórico es ENVIADA
    if datos.estado_intervencion == "PENDIENTE":
        datos.estado_intervencion = "ENVIADA"
    return service.crear_intervencion(
        db,
        id_cita,
        datos,
        usuario=usuario,
        ip=ip_cliente(request),
        ahora=ahora,
        modo_sombra_activo=sombra,
        validar_consentimiento=False,
        validar_catalogo=False,
        validar_elegibilidad=False,
    )
