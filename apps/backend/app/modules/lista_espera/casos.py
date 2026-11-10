"""Lógica propia de Lista de Espera; oferta/cierre/reasignación son componibles."""
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.errores import ConflictoDeNegocio, NoEncontrado, ReglaDeNegocioInvalida
from app.modules.auditoria.public import registrar_evento
from app.modules.auth.public import Principal as Usuario
from app.core.reloj import LIMA
from app.core.transacciones import bloquear_fila
from app.modules.citas import public as citas_public
from app.modules.lista_espera import ofertas, repository
from app.modules.lista_espera.models import CupoLiberado, ListaEspera, Reasignacion
from sqlalchemy import select
from app.modules.lista_espera.schemas import (
    CandidatoCreateIn,
    CandidatoOut,
    CandidatoUpdateIn,
    OfertaOut,
    PaginaCandidatoOut,
    PaginaCupoOut,
    CupoDetalleOut,
    CupoLiberadoOut,
    PropuestaCandidatosOut,
    ReasignacionIn,
    ReasignacionOut,
)


def _franja_de_cupo(db: Session, cupo: CupoLiberado) -> str:
    meta = citas_public.obtener_metadatos_cita_para_cupo(db, cupo.id_cita_origen)
    if meta is not None:
        return meta[1]
    hora_lima = cupo.fecha_hora_cupo.astimezone(LIMA).hour
    return "MANANA" if hora_lima < 13 else "TARDE"


def _cupo_a_out(db: Session, cupo: CupoLiberado) -> CupoLiberadoOut:
    out = CupoLiberadoOut.model_validate(cupo)
    meta = citas_public.obtener_metadatos_cita_para_cupo(db, cupo.id_cita_origen)
    if meta is not None:
        out.id_cita_externa_origen = meta[0]
        out.franja_horaria = meta[1]
    else:
        out.id_cita_externa_origen = f"CIT-{cupo.id_cita_origen}"
        hora_lima = cupo.fecha_hora_cupo.astimezone(LIMA).hour
        out.franja_horaria = "MANANA" if hora_lima < 13 else "TARDE"
    return out


def obtener_detalle_cupo(db: Session, id_cupo: int) -> CupoDetalleOut:
    cupo = db.get(CupoLiberado, id_cupo)
    if cupo is None:
        raise NoEncontrado(f"No existe el cupo liberado {id_cupo}")

    cupo_out = _cupo_a_out(db, cupo)
    proyeccion = ofertas.consultar(db, id_cupo)
    if cupo.estado_cupo == "EN_OFERTA" and proyeccion.vigente is not None:
        event = proyeccion.vigente
        candidato = db.get(ListaEspera, event.datos_after["id_candidato"])
        if candidato is not None:
            cupo_out.oferta_vigente = OfertaOut(id_candidato=candidato.id_candidato,
                paciente_anon_id=candidato.paciente_anon_id, id_operador=event.id_usuario,
                fecha_hora_oferta=event.creado_en)
    registro = db.execute(
        select(Reasignacion, ListaEspera.paciente_anon_id)
        .join(ListaEspera, ListaEspera.id_candidato == Reasignacion.id_candidato)
        .where(Reasignacion.id_cupo_liberado == id_cupo)
    ).one_or_none()

    reasig_out = None
    if registro is not None:
        reasig, paciente_anon_id = registro
        reasig_out = ReasignacionOut(
            id_reasignacion=reasig.id_reasignacion,
            id_cupo_liberado=reasig.id_cupo_liberado,
            id_candidato=reasig.id_candidato,
            paciente_anon_id=paciente_anon_id,
            id_operador_confirma=reasig.id_operador_confirma,
            confirmacion_humana=reasig.confirmacion_humana,
            medio_confirmacion=reasig.medio_confirmacion,
            observaciones=reasig.observaciones,
            fecha_hora_reasigna=reasig.fecha_hora_reasigna,
            estado_cupo_final=cupo.estado_cupo,
            estado_candidato_final="ASIGNADO",
        )

    return CupoDetalleOut(
        **cupo_out.model_dump(),
        reasignacion=reasig_out,
        historial_ofertas=list(proyeccion.historial),
    )


def listar_espera(db: Session, *, q=None, especialidad_req=None, franja_preferida=None,
                  estado_candidato=None, limite=50, desplazamiento=0) -> PaginaCandidatoOut:
    candidatos = repository.listar_candidatos(db, especialidad_req=especialidad_req,
        franja_preferida=franja_preferida, estado_candidato=estado_candidato)
    if q:
        q_norm = q.strip().upper()
        candidatos = [c for c in candidatos if q_norm in c.paciente_anon_id.upper()]
    return PaginaCandidatoOut(total=len(candidatos), limite=limite, desplazamiento=desplazamiento,
        items=[CandidatoOut.model_validate(c) for c in candidatos[desplazamiento:desplazamiento + limite]])


def listar_cupos_paginados(db: Session, *, estado_cupo=None, especialidad=None, desde=None, hasta=None,
                          limite=50, desplazamiento=0) -> PaginaCupoOut:
    cupos = listar_cupos(db, estado_cupo=estado_cupo, especialidad=especialidad)
    if desde:
        try:
            fecha = datetime.fromisoformat(desde)
            cupos = [c for c in cupos if c.fecha_hora_cupo >= fecha]
        except ValueError:
            pass
    if hasta:
        try:
            fecha = datetime.fromisoformat(f"{hasta}T23:59:59")
            cupos = [c for c in cupos if c.fecha_hora_cupo <= fecha]
        except ValueError:
            pass
    return PaginaCupoOut(total=len(cupos), limite=limite, desplazamiento=desplazamiento,
        items=cupos[desplazamiento:desplazamiento + limite])


def _validar_compatibilidad(db: Session, cupo: CupoLiberado, candidato: ListaEspera) -> None:
    franja_cupo = _franja_de_cupo(db, cupo)
    if candidato.especialidad_req != cupo.especialidad:
        raise ConflictoDeNegocio(
            f"Incompatibilidad de especialidad: el cupo es de '{cupo.especialidad}' "
            f"y el candidato requiere '{candidato.especialidad_req}'")
    if candidato.franja_preferida not in (franja_cupo, "INDIFERENTE"):
        raise ConflictoDeNegocio(
            f"Incompatibilidad de franja horaria: el cupo es en turno '{franja_cupo}' "
            f"y el candidato prefiere '{candidato.franja_preferida}'")


def _cupo_bloqueado(db: Session, id_cupo: int) -> CupoLiberado:
    cupo = bloquear_fila(db, CupoLiberado, id_cupo)
    if cupo is None:
        raise NoEncontrado(f"No existe el cupo {id_cupo}")
    return cupo


def registrar_oferta(db: Session, id_cupo: int, id_candidato: int, *, usuario: Usuario, ip: str) -> CupoDetalleOut:
    cupo = _cupo_bloqueado(db, id_cupo)
    if cupo.estado_cupo != "DISPONIBLE":
        raise ConflictoDeNegocio("El cupo no admite una nueva oferta", codigo="CUPO_NO_DISPONIBLE")
    candidato = bloquear_fila(db, ListaEspera, id_candidato)
    if candidato is None:
        raise NoEncontrado(f"No existe el candidato {id_candidato}")
    if candidato.estado_candidato not in ("ACTIVO", "CONTACTADO"):
        raise ConflictoDeNegocio("El candidato no está disponible", codigo="CANDIDATO_NO_DISPONIBLE")
    _validar_compatibilidad(db, cupo, candidato)
    if repository.candidato_tiene_oferta_ajena(db, id_candidato, id_cupo):
        raise ConflictoDeNegocio("El candidato ya tiene otra oferta vigente", codigo="CANDIDATO_EN_OFERTA")
    antes = {"estado_cupo": cupo.estado_cupo, "estado_candidato": candidato.estado_candidato}
    cupo.estado_cupo, candidato.estado_candidato = "EN_OFERTA", "CONTACTADO"
    registrar_evento(db, modulo="REASIGNACION", accion="OFERTAR", entidad_afectada="cupos_liberados",
        direccion_ip=ip, id_usuario=usuario.id_usuario, id_entidad=id_cupo, datos_before=antes,
        datos_after={"id_cupo_liberado": id_cupo, "id_candidato": id_candidato,
                     "estado_cupo": "EN_OFERTA", "estado_candidato": "CONTACTADO"})
    db.flush()  # DTO y bitácora visibles dentro de esta transacción; no confirmar
    return obtener_detalle_cupo(db, id_cupo)


def _registrar_cierre(db: Session, cupo: CupoLiberado, oferta, candidato: ListaEspera,
                     cierre: str, antes: dict, *, usuario: Usuario, ip: str) -> None:
    accion = {"RECHAZA": "RECHAZAR", "SIN_RESPUESTA": "DESISTIR", "REASIGNADO": "CERRAR_OFERTA"}[cierre]
    registrar_evento(db, modulo="REASIGNACION", accion=accion, entidad_afectada="cupos_liberados",
        direccion_ip=ip, id_usuario=usuario.id_usuario, id_entidad=cupo.id_cupo_liberado, datos_before=antes,
        datos_after={"id_oferta": oferta.id_log, "id_candidato": candidato.id_candidato,
                     "cierre": cierre, "estado_cupo": cupo.estado_cupo,
                     "estado_candidato": candidato.estado_candidato})


def cerrar_oferta(db: Session, id_cupo: int, *, cierre: str, usuario: Usuario, ip: str) -> CupoDetalleOut:
    if cierre not in ("RECHAZA", "SIN_RESPUESTA"):
        raise ReglaDeNegocioInvalida("Cierre de oferta no admitido")
    cupo = _cupo_bloqueado(db, id_cupo)
    if cupo.estado_cupo != "EN_OFERTA":
        raise ConflictoDeNegocio("No hay oferta vigente para cerrar", codigo="SIN_OFERTA_VIGENTE")
    oferta = ofertas.consultar(db, id_cupo).vigente
    if oferta is None:
        raise ConflictoDeNegocio("Oferta legacy sin candidato registrado; requiere revisión", codigo="OFERTA_NO_REGISTRADA")
    candidato = bloquear_fila(db, ListaEspera, oferta.datos_after["id_candidato"])
    if candidato is None:
        raise NoEncontrado("No existe el candidato de la oferta")
    antes = {"estado_cupo": cupo.estado_cupo, "estado_candidato": candidato.estado_candidato}
    cupo.estado_cupo = "DISPONIBLE"
    if candidato.estado_candidato == "CONTACTADO":
        candidato.estado_candidato = "ACTIVO"  # no reactivar ASIGNADO/DESISTIDO
    _registrar_cierre(db, cupo, oferta, candidato, cierre, antes, usuario=usuario, ip=ip)
    db.flush()
    return obtener_detalle_cupo(db, id_cupo)


def crear_candidato(
    db: Session,
    datos: CandidatoCreateIn,
    *,
    usuario: Usuario,
    ip: str,
) -> CandidatoOut:
    candidato = ListaEspera(
        paciente_anon_id=datos.paciente_anon_id,
        especialidad_req=datos.especialidad_req,
        franja_preferida=datos.franja_preferida,
        estado_candidato="ACTIVO",
        prioridad_registro=datos.prioridad_registro,
    )
    db.add(candidato)
    db.flush()

    registrar_evento(
        db,
        modulo="REASIGNACION",
        accion="CREATE",
        entidad_afectada="lista_espera",
        direccion_ip=ip,
        id_usuario=usuario.id_usuario,
        id_entidad=candidato.id_candidato,
        datos_after={
            "paciente_anon_id": candidato.paciente_anon_id,
            "especialidad_req": candidato.especialidad_req,
            "franja_preferida": candidato.franja_preferida,
            "prioridad_registro": candidato.prioridad_registro,
            "estado_candidato": candidato.estado_candidato,
        },
    )
    db.commit()
    db.refresh(candidato)
    return CandidatoOut.model_validate(candidato)


def actualizar_candidato(
    db: Session,
    id_candidato: int,
    datos: CandidatoUpdateIn,
    *,
    usuario: Usuario,
    ip: str,
) -> CandidatoOut:
    candidato = bloquear_fila(db, ListaEspera, id_candidato)
    if candidato is None:
        raise NoEncontrado(f"No existe el candidato {id_candidato} en lista de espera")

    antes = {
        "franja_preferida": candidato.franja_preferida,
        "estado_candidato": candidato.estado_candidato,
        "prioridad_registro": candidato.prioridad_registro,
    }
    if datos.franja_preferida is not None:
        candidato.franja_preferida = datos.franja_preferida
    if datos.estado_candidato is not None:
        candidato.estado_candidato = datos.estado_candidato
    if datos.prioridad_registro is not None:
        candidato.prioridad_registro = datos.prioridad_registro

    registrar_evento(
        db,
        modulo="REASIGNACION",
        accion="UPDATE",
        entidad_afectada="lista_espera",
        direccion_ip=ip,
        id_usuario=usuario.id_usuario,
        id_entidad=candidato.id_candidato,
        datos_before=antes,
        datos_after={
            "franja_preferida": candidato.franja_preferida,
            "estado_candidato": candidato.estado_candidato,
            "prioridad_registro": candidato.prioridad_registro,
        },
    )
    db.commit()
    db.refresh(candidato)
    return CandidatoOut.model_validate(candidato)


def listar_cupos(
    db: Session,
    *,
    estado_cupo: str | None = "DISPONIBLE",
    especialidad: str | None = None,
) -> list[CupoLiberadoOut]:
    cupos = repository.listar_cupos_liberados(db, estado_cupo=estado_cupo, especialidad=especialidad)
    return [_cupo_a_out(db, c) for c in cupos]


def proponer_candidatos_para_cupo(db: Session, id_cupo: int) -> PropuestaCandidatosOut:
    cupo = db.get(CupoLiberado, id_cupo)
    if cupo is None:
        raise NoEncontrado(f"No existe el cupo liberado {id_cupo}")

    franja_cupo = _franja_de_cupo(db, cupo)
    compatibles = repository.buscar_candidatos_compatibles(
        db,
        especialidad=cupo.especialidad,
        franja_cupo=franja_cupo,
    )

    candidatos_out: list[CandidatoOut] = []
    for c in compatibles:
        c_out = CandidatoOut.model_validate(c)
        tipo_match_franja = (
            f"Coincidencia exacta de franja ({franja_cupo})"
            if c.franja_preferida == franja_cupo
            else f"Franja INDIFERENTE compatible con {franja_cupo}"
        )
        c_out.criterio_compatibilidad = (
            f"Especialidad {c.especialidad_req} | {tipo_match_franja} | Prioridad {c.prioridad_registro} (FIFO)"
        )
        candidatos_out.append(c_out)

    return PropuestaCandidatosOut(
        cupo=_cupo_a_out(db, cupo),
        total_compatibles=len(candidatos_out),
        candidatos=candidatos_out,
    )


def reasignar_cupo(
    db: Session,
    id_cupo: int,
    datos: ReasignacionIn,
    *,
    usuario: Usuario,
    ip: str,
) -> ReasignacionOut:
    # Regla dura Human-in-the-Loop (RF-079, RNF-029, RN11)
    if datos.confirmacion_humana is not True:
        raise ReglaDeNegocioInvalida(
            "La reasignación asistida exige confirmación humana explícita (confirmacion_humana=True) (RF-079 / RN11)"
        )

    # Bloqueo pesimista sobre el cupo liberado para impedir doble reasignación concurrente (RF-081)
    cupo = bloquear_fila(db, CupoLiberado, id_cupo)
    if cupo is None:
        raise NoEncontrado(f"No existe el cupo liberado {id_cupo}")
    if cupo.estado_cupo not in ("DISPONIBLE", "EN_OFERTA"):
        raise ConflictoDeNegocio(
            f"El cupo {id_cupo} no está disponible para reasignación (estado actual: '{cupo.estado_cupo}')"
        )

    # Bloqueo pesimista sobre el candidato en lista de espera
    candidato = bloquear_fila(db, ListaEspera, datos.id_candidato)
    if candidato is None:
        raise NoEncontrado(f"No existe el candidato {datos.id_candidato} en lista de espera")
    if candidato.estado_candidato not in ("ACTIVO", "CONTACTADO"):
        raise ConflictoDeNegocio(
            f"El candidato {datos.id_candidato} no está disponible (estado actual: '{candidato.estado_candidato}')"
        )

    # Validación de compatibilidad de especialidad y franja (RF-074, RF-075)
    _validar_compatibilidad(db, cupo, candidato)

    oferta = ofertas.consultar(db, id_cupo).vigente if cupo.estado_cupo == "EN_OFERTA" else None
    if oferta is not None and oferta.datos_after["id_candidato"] != candidato.id_candidato:
        raise ConflictoDeNegocio("La oferta vigente pertenece a otro candidato", codigo="CANDIDATO_NO_OFERTADO")

    estado_cupo_antes = cupo.estado_cupo
    estado_candidato_antes = candidato.estado_candidato

    cupo.estado_cupo = "REASIGNADO"
    candidato.estado_candidato = "ASIGNADO"

    reasignacion = Reasignacion(
        id_cupo_liberado=cupo.id_cupo_liberado,
        id_candidato=candidato.id_candidato,
        id_operador_confirma=usuario.id_usuario,
        confirmacion_humana=True,
        medio_confirmacion=datos.medio_confirmacion,
        observaciones=datos.observaciones,
    )
    db.add(reasignacion)
    db.flush()

    registrar_evento(
        db,
        modulo="REASIGNACION",
        accion="REASIGNAR",
        entidad_afectada="reasignaciones",
        direccion_ip=ip,
        id_usuario=usuario.id_usuario,
        id_entidad=reasignacion.id_reasignacion,
        datos_before={
            "estado_cupo": estado_cupo_antes,
            "estado_candidato": estado_candidato_antes,
        },
        datos_after={
            "id_reasignacion": reasignacion.id_reasignacion,
            "id_cupo_liberado": cupo.id_cupo_liberado,
            "id_cita_origen": cupo.id_cita_origen,
            "id_candidato": candidato.id_candidato,
            "paciente_anon_id": candidato.paciente_anon_id,
            "confirmacion_humana": True,
            "medio_confirmacion": reasignacion.medio_confirmacion,
            "estado_cupo": "REASIGNADO",
            "estado_candidato": "ASIGNADO",
        },
    )
    if oferta is not None:
        _registrar_cierre(db, cupo, oferta, candidato, "REASIGNADO",
            {"estado_cupo": estado_cupo_antes, "estado_candidato": estado_candidato_antes}, usuario=usuario, ip=ip)
    db.flush()
    db.refresh(reasignacion)

    return ReasignacionOut(
        id_reasignacion=reasignacion.id_reasignacion,
        id_cupo_liberado=reasignacion.id_cupo_liberado,
        id_candidato=reasignacion.id_candidato,
        paciente_anon_id=candidato.paciente_anon_id,
        id_operador_confirma=reasignacion.id_operador_confirma,
        confirmacion_humana=reasignacion.confirmacion_humana,
        medio_confirmacion=reasignacion.medio_confirmacion,
        observaciones=reasignacion.observaciones,
        fecha_hora_reasigna=reasignacion.fecha_hora_reasigna,
        estado_cupo_final=cupo.estado_cupo,
        estado_candidato_final=candidato.estado_candidato,
    )
