from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.errores import Conflicto, NoEncontrado, TransicionInvalida, Validacion
from app.modules.auditoria.public import registrar_evento
from app.modules.auth.public import Principal as Usuario
from app.core.reloj import LIMA
from app.core.transacciones import bloquear_fila
from app.workflows import intervenciones as workflow_intervenciones
from app.modules.citas import public as citas_public
from app.modules.intervenciones import reglas, repository
from app.modules.intervenciones.models import Intervencion
from app.modules.intervenciones.schemas import (
    BandejaIntervencionesOut,
    CitaSugeridaIntervencionOut,
    ElegibleOut,
    IntervencionCreateIn,
    IntervencionOut,
    IntervencionRespuestaIn,
    PaginaElegiblesOut,
    PaginaIntervencionesOut,
    RiesgoResumen,
)
from app.modules.lista_espera import public as lista_espera_public
from app.modules.lista_espera.public import CupoLiberadoOut

# Regla normativa RN07 / RF-066 / RNF-032: máximo 1 recordatorio adicional preventivo por cita.
MAX_RECORDATORIOS_ADICIONALES_POR_CITA = 1
ESTADOS_CITA_INTERVENIBLES = {"RECIBIDA", "CONFIRMADA", "REPROGRAMADA"}


def _bloquear_cita_e_intervencion(db: Session, id_intervencion: int):
    # Lectura sin lock solo para localizar el padre; ningún endpoint cambia id_cita.
    inicial = db.get(Intervencion, id_intervencion)
    if inicial is None:
        raise NoEncontrado(f"No existe la intervención {id_intervencion}")
    cita = citas_public.obtener_cita_consulta(db, inicial.id_cita, bloquear=True)
    if cita is None:
        raise NoEncontrado(f"No existe la cita asociada {inicial.id_cita}")
    intervencion = bloquear_fila(db, Intervencion, id_intervencion)
    if intervencion is None:
        raise NoEncontrado(f"No existe la intervención {id_intervencion}")
    return cita, intervencion


def obtener_intervencion(db: Session, id_intervencion: int) -> IntervencionOut:
    intervencion = db.get(Intervencion, id_intervencion)
    if intervencion is None:
        raise NoEncontrado(f"No existe la intervención {id_intervencion}")
    return _enriquecer_out(intervencion, db=db)


def listar_intervenciones_de_cita(db: Session, id_cita: int) -> list[IntervencionOut]:
    return [_enriquecer_out(i) for i in repository.listar_por_cita(db, id_cita)]


def listar_intervenciones_paginadas(
    db: Session, *, nivel_riesgo=None, especialidad=None, estado_intervencion=None,
    canal_contacto=None, respuesta_paciente=None, desde=None, hasta=None, id_cita=None,
    limite=50, desplazamiento=0,
) -> PaginaIntervencionesOut:
    # Se conserva filtrado/paginación históricos; no endurecer fechas en C (S-12).
    bandeja = listar_bandeja_intervenciones(db, nivel_riesgo=nivel_riesgo, especialidad=especialidad,
        estado_intervencion=estado_intervencion, canal_contacto=canal_contacto)
    historial = [_enriquecer_out(i, db=db) for i in repository.listar_historial(
        db, estado_intervencion=estado_intervencion, canal_contacto=canal_contacto, limite=1000)]
    if id_cita:
        historial = [h for h in historial if h.id_cita == id_cita]
    if respuesta_paciente:
        historial = [h for h in historial if h.respuesta_paciente == respuesta_paciente.upper()]
    if desde:
        try:
            fecha = datetime.fromisoformat(desde)
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=LIMA)
            historial = [h for h in historial if h.fecha_hora_envio >= fecha]
        except ValueError:
            pass
    if hasta:
        try:
            fecha = datetime.fromisoformat(f"{hasta}T23:59:59")
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=LIMA)
            historial = [h for h in historial if h.fecha_hora_envio <= fecha]
        except ValueError:
            pass
    total = len(historial)
    items = historial[desplazamiento:desplazamiento + limite]
    return PaginaIntervencionesOut(total=total, limite=limite, desplazamiento=desplazamiento,
        items=items, total_sugeridas=bandeja.total_sugeridas, total_intervenciones=total,
        citas_sugeridas=bandeja.citas_sugeridas, historial_intervenciones=items)


def _enriquecer_out(
    intervencion: Intervencion,
    *,
    db: Session | None = None,
    estado_cita_actual: str | None = None,
    id_cupo_liberado: int | None = None,
    id_cita_externa: str | None = None,
) -> IntervencionOut:
    base = IntervencionOut.model_validate(intervencion)
    base.estado_cita_actual = estado_cita_actual
    base.id_cupo_liberado_generado = id_cupo_liberado

    if id_cita_externa is not None:
        base.id_cita_externa = id_cita_externa
    elif db is not None:
        cita = citas_public.obtener_cita_consulta(db, intervencion.id_cita)
        if cita:
            base.id_cita_externa = cita.id_cita_externa
            if not estado_cita_actual:
                base.estado_cita_actual = cita.estado_actual
    else:
        cita = repository.cita_relacionada(intervencion)
        if cita is not None:
            base.id_cita_externa = cita.id_cita_externa
            base.estado_cita_actual = estado_cita_actual or cita.estado_actual

    cita_estado = estado_cita_actual or base.estado_cita_actual or "RECIBIDA"
    base.acciones_disponibles = reglas.acciones_disponibles(
        intervencion.estado_intervencion,
        intervencion.canal_contacto,
        intervencion.respuesta_paciente,
        intervencion.consentimiento_optout,
        cita_estado,
    )
    return base


def listar_citas_elegibles(
    db: Session,
    *,
    desde: str | None = None,
    hasta: str | None = None,
    especialidad: str | None = None,
    nivel_riesgo: str | None = None,
    limite: int = 50,
    desplazamiento: int = 0,
    ahora: datetime | None = None,
) -> PaginaElegiblesOut:
    pares = repository.listar_citas_riesgo_medio_alto(
        db,
        nivel_riesgo=nivel_riesgo,
        especialidad=especialidad,
    )
    items: list[ElegibleOut] = []
    vistos: set[int] = set()
    ahora_ref = ahora or datetime.now(timezone.utc)
    if ahora_ref.tzinfo is None:
        ahora_ref = ahora_ref.replace(tzinfo=LIMA)

    limite_inferior = ahora_ref
    if desde:
        try:
            d_dt = datetime.fromisoformat(desde)
            if d_dt.tzinfo is None:
                d_dt = d_dt.replace(tzinfo=ahora_ref.tzinfo)
            limite_inferior = d_dt
        except ValueError:
            pass

    limite_superior = ahora_ref + timedelta(days=7)
    if hasta:
        try:
            h_dt = datetime.fromisoformat(f"{hasta}T23:59:59")
            if h_dt.tzinfo is None:
                h_dt = h_dt.replace(tzinfo=ahora_ref.tzinfo)
            limite_superior = h_dt
        except ValueError:
            pass

    for cita, pred in pares:
        if cita.id_cita in vistos:
            continue
        vistos.add(cita.id_cita)

        if cita.estado_actual not in ESTADOS_CITA_INTERVENIBLES:
            continue
        if cita.fecha_hora_cita <= ahora_ref:
            continue
        if cita.fecha_hora_cita < limite_inferior or cita.fecha_hora_cita > limite_superior:
            continue

        # Regla de límite: si no admite otra intervención
        estados_previos = repository.listar_estados_previos_por_cita(db, cita.id_cita)
        if not reglas.puede_crear_otra(estados_previos):
            continue

        optout = repository.tiene_optout_vigente(db, cita.id_cita, cita.paciente_anon_id)
        if optout:
            continue

        # La consulta ya entrega una predicción por cita y filtra su riesgo vigente.

        items.append(
            ElegibleOut(
                id_cita=cita.id_cita,
                id_cita_externa=cita.id_cita_externa,
                paciente_anon_id=cita.paciente_anon_id,
                especialidad=cita.especialidad,
                medico=cita.medico,
                fecha_hora_cita=cita.fecha_hora_cita,
                estado_actual=cita.estado_actual,
                riesgo=RiesgoResumen(
                    id_prediccion=pred.id_prediccion,
                    probabilidad_no_show=float(pred.probabilidad_no_show),
                    nivel_riesgo=pred.nivel_riesgo,
                    version_modelo=pred.version_modelo,
                    fecha_hora_inferencia=pred.fecha_hora_inferencia,
                    resultado_simulado=getattr(pred, "resultado_simulado", True),
                ),
                intervenciones_previas=len(estados_previos),
            )
        )

    # Ordenar: reintentos primero (intervenciones_previas > 0), luego ALTO antes de MEDIO, luego probabilidad descendente
    items.sort(
        key=lambda x: (
            x.intervenciones_previas > 0,
            1 if x.riesgo.nivel_riesgo == "ALTO" else 0,
            x.riesgo.probabilidad_no_show,
        ),
        reverse=True,
    )

    total = len(items)
    items_paginados = items[desplazamiento : desplazamiento + limite]
    return PaginaElegiblesOut(
        total=total,
        limite=limite,
        desplazamiento=desplazamiento,
        items=items_paginados,
    )


def listar_bandeja_intervenciones(
    db: Session,
    *,
    nivel_riesgo: str | None = None,
    especialidad: str | None = None,
    estado_intervencion: str | None = None,
    canal_contacto: str | None = None,
) -> BandejaIntervencionesOut:
    pares = repository.listar_citas_riesgo_medio_alto(
        db,
        nivel_riesgo=nivel_riesgo,
        especialidad=especialidad,
    )
    sugeridas: list[CitaSugeridaIntervencionOut] = []
    vistos: set[int] = set()
    for cita, pred in pares:
        if cita.id_cita in vistos:
            continue
        vistos.add(cita.id_cita)
        enviadas = repository.contar_activas_por_cita(db, cita.id_cita)
        optout = repository.tiene_optout_vigente(db, cita.id_cita, cita.paciente_anon_id)
        if pred.nivel_riesgo == "ALTO":
            accion_sug = "CONFIRMACION_PREVIA_O_LIBERACION_VOLUNTARIA"
            canal_sug = "LLAMADA_TELEFONICA"
        else:
            accion_sug = "RECORDATORIO_PREVENTIVO_ADICIONAL"
            canal_sug = "WHATSAPP"

        sugeridas.append(
            CitaSugeridaIntervencionOut(
                id_cita=cita.id_cita,
                id_cita_externa=cita.id_cita_externa,
                paciente_anon_id=cita.paciente_anon_id,
                especialidad=cita.especialidad,
                medico=cita.medico,
                fecha_hora_cita=cita.fecha_hora_cita,
                franja_horaria=cita.franja_horaria,
                estado_actual=cita.estado_actual,
                probabilidad_no_show=pred.probabilidad_no_show,
                nivel_riesgo=pred.nivel_riesgo,
                explicabilidad_resumen=pred.explicabilidad_resumen,
                accion_sugerida=accion_sug,
                canal_sugerido=canal_sug,
                intervenciones_enviadas=enviadas,
                tiene_optout=optout,
            )
        )

    historial = repository.listar_historial(
        db,
        estado_intervencion=estado_intervencion,
        canal_contacto=canal_contacto,
    )
    return BandejaIntervencionesOut(
        total_sugeridas=len(sugeridas),
        total_intervenciones=len(historial),
        citas_sugeridas=sugeridas,
        historial_intervenciones=[IntervencionOut.model_validate(i) for i in historial],
    )


def crear_intervencion(
    db: Session,
    id_cita: int,
    datos: IntervencionCreateIn,
    *,
    usuario: Usuario,
    ip: str,
    ahora: datetime | None = None,
    modo_sombra_activo: bool = False,
) -> IntervencionOut:
    if modo_sombra_activo:
        raise Conflicto(
            "No se pueden registrar intervenciones: el sistema opera en modo sombra (simulación sin contacto con pacientes)",
            codigo="MODO_SOMBRA",
        )

    # Validar canal y plantilla contra el catálogo oficial
    canales_validos = reglas.canales_de(datos.plantilla_mensaje)
    if not canales_validos:
        raise Validacion(
            f"La plantilla '{datos.plantilla_mensaje}' no existe en el catálogo",
            codigo="VALIDACION",
            campos={"plantilla_mensaje": "Plantilla no disponible"},
        )
    if datos.canal_contacto not in canales_validos:
        raise Validacion(
            f"La plantilla '{datos.plantilla_mensaje}' no está permitida para el canal '{datos.canal_contacto}'",
            codigo="VALIDACION",
            campos={"plantilla_mensaje": "Canal no admitido por la plantilla"},
        )

    # Validación estricta de consentimiento (RF-063, RN13, D-024)
    val = datos.consentimiento_confirmado
    if val is None or val is False:
        raise Validacion(
            "Debe confirmar el consentimiento del paciente",
            codigo="CONSENTIMIENTO_REQUERIDO",
            campos={"consentimiento_confirmado": "Consentimiento obligatorio"},
        )
    if val is not True:
        raise Validacion(
            "El consentimiento debe ser verdadero (booleano True)",
            codigo="VALIDACION",
            campos={"consentimiento_confirmado": "Debe ser verdadero"},
        )

    cita = citas_public.obtener_cita_consulta(db, id_cita, bloquear=True)
    if cita is None:
        raise NoEncontrado(f"No existe la cita {id_cita}")

    # Regla dura 1: Derecho de oposición / Opt-Out (RF-064, RF-065, RN07)
    if datos.consentimiento_optout or repository.tiene_optout_vigente(db, id_cita, cita.paciente_anon_id):
        raise Conflicto(
            "Envío rechazado: el paciente ejerció su derecho de oposición (opt-out)",
            codigo="OPTOUT_VIGENTE",
        )

    # Regla dura 2: Elegibilidad de la cita (estado activo, fecha futura, riesgo ALTO o MEDIO)
    prediccion = repository.obtener_prediccion_reciente(db, cita.id_cita)
    ahora_ref = ahora or datetime.now(timezone.utc)
    es_pasada = cita.fecha_hora_cita <= ahora_ref

    if (
        cita.estado_actual not in ESTADOS_CITA_INTERVENIBLES
        or es_pasada
        or prediccion is None
        or prediccion.nivel_riesgo not in ("ALTO", "MEDIO")
    ):
        raise Conflicto(
            f"La cita {id_cita} no es elegible para intervención preventiva (RF-057)",
            codigo="NO_ELEGIBLE",
        )

    # Regla dura 3: Límite normativo de intervenciones (RF-066, RN07)
    estados_previos = repository.listar_estados_previos_por_cita(db, cita.id_cita)
    if not reglas.puede_crear_otra(estados_previos):
        raise Conflicto(
            f"La cita {id_cita} ya alcanzó el límite normativo de intervenciones (RF-066 / RN07)",
            codigo="LIMITE_INTERVENCION",
        )

    intervencion = Intervencion(
        id_cita=cita.id_cita,
        id_operador=usuario.id_usuario,
        canal_contacto=datos.canal_contacto,
        plantilla_mensaje=datos.plantilla_mensaje,
        consentimiento_optout=False,
        estado_intervencion="PENDIENTE",
    )
    db.add(intervencion)
    db.flush()

    registrar_evento(
        db,
        modulo="INTERVENCION",
        accion="CREATE",
        entidad_afectada="intervenciones",
        direccion_ip=ip,
        id_usuario=usuario.id_usuario,
        id_entidad=intervencion.id_intervencion,
        datos_after={
            "id_cita": cita.id_cita,
            "id_prediccion": prediccion.id_prediccion if prediccion else None,
            "canal_contacto": intervencion.canal_contacto,
            "plantilla_mensaje": intervencion.plantilla_mensaje,
            "estado_intervencion": intervencion.estado_intervencion,
            "consentimiento_confirmado": True,
        },
    )
    db.commit()
    db.refresh(intervencion)
    return _enriquecer_out(intervencion, db=db, estado_cita_actual=cita.estado_actual, id_cita_externa=cita.id_cita_externa)


def cambiar_estado_intervencion(
    db: Session,
    id_intervencion: int,
    nuevo_estado: str,
    *,
    usuario: Usuario,
    ip: str,
    ahora: datetime | None = None,
) -> IntervencionOut:
    intervencion = bloquear_fila(db, Intervencion, id_intervencion)
    if intervencion is None:
        raise NoEncontrado(f"No existe la intervención {id_intervencion}")

    anterior = intervencion.estado_intervencion
    permitidos = reglas.TRANSICIONES_ENVIO.get(anterior, set())
    if nuevo_estado not in permitidos:
        raise Conflicto(
            f"Transición de '{anterior}' a '{nuevo_estado}' no permitida",
            codigo="TRANSICION_INVALIDA",
        )

    ahora_ref = ahora or datetime.now(timezone.utc)
    if nuevo_estado == "ENVIADA":
        intervencion.fecha_hora_envio = ahora_ref

    intervencion.estado_intervencion = nuevo_estado
    registrar_evento(
        db,
        modulo="INTERVENCION",
        accion="UPDATE",
        entidad_afectada="intervenciones",
        direccion_ip=ip,
        id_usuario=usuario.id_usuario,
        id_entidad=intervencion.id_intervencion,
        datos_before={"estado_intervencion": anterior},
        datos_after={"estado_intervencion": nuevo_estado},
    )
    db.commit()
    db.refresh(intervencion)
    return _enriquecer_out(intervencion, db=db)


def registrar_respuesta_intervencion(
    db: Session,
    id_intervencion: int,
    datos: IntervencionRespuestaIn,
    *,
    usuario: Usuario,
    ip: str,
    ahora: datetime | None = None,
    cambiar_cita: bool = False,
    validar_transicion: bool = True,
) -> IntervencionOut:
    cita, intervencion = _bloquear_cita_e_intervencion(db, id_intervencion)

    if validar_transicion and not reglas.admite_respuesta(intervencion.estado_intervencion, intervencion.canal_contacto):
        raise Conflicto(
            f"La intervención en estado '{intervencion.estado_intervencion}' por canal '{intervencion.canal_contacto}' no admite registro de respuesta",
            codigo="TRANSICION_INVALIDA",
        )

    ahora_ref = ahora or datetime.now(timezone.utc)
    intervencion.estado_intervencion = "RESPONDIDA"
    intervencion.respuesta_paciente = datos.respuesta_paciente
    intervencion.fecha_hora_respuesta = ahora_ref

    optout_activo = bool(datos.optout or datos.consentimiento_optout)
    if optout_activo and not intervencion.consentimiento_optout:
        intervencion.consentimiento_optout = True
        registrar_evento(
            db,
            modulo="INTERVENCION",
            accion="OPTOUT",
            entidad_afectada="intervenciones",
            direccion_ip=ip,
            id_usuario=usuario.id_usuario,
            id_entidad=intervencion.id_intervencion,
            datos_after={"consentimiento_optout": True, "id_cita": intervencion.id_cita},
        )

    # Si se invoca vía PATCH legado (donde cambiar_cita es True), actualizamos la cita
    id_cupo_generado: int | None = None
    if cambiar_cita:
        cita, id_cupo_generado = workflow_intervenciones.aplicar_respuesta(db, cita, intervencion.id_intervencion,
            datos.respuesta_paciente, datos.observacion, usuario=usuario, ip=ip)

    registrar_evento(
        db,
        modulo="INTERVENCION",
        accion="RESPUESTA",
        entidad_afectada="intervenciones",
        direccion_ip=ip,
        id_usuario=usuario.id_usuario,
        id_entidad=intervencion.id_intervencion,
        datos_after={
            "respuesta_paciente": datos.respuesta_paciente,
            "consentimiento_optout": intervencion.consentimiento_optout,
        },
    )
    db.commit()
    db.refresh(intervencion)
    return _enriquecer_out(
        intervencion,
        db=db,
        estado_cita_actual=cita.estado_actual,
        id_cupo_liberado=id_cupo_generado,
    )


def registrar_optout_intervencion(
    db: Session,
    id_intervencion: int,
    *,
    usuario: Usuario,
    ip: str,
) -> IntervencionOut:
    intervencion = bloquear_fila(db, Intervencion, id_intervencion)
    if intervencion is None:
        raise NoEncontrado(f"No existe la intervención {id_intervencion}")

    if not intervencion.consentimiento_optout:
        intervencion.consentimiento_optout = True
        registrar_evento(
            db,
            modulo="INTERVENCION",
            accion="OPTOUT",
            entidad_afectada="intervenciones",
            direccion_ip=ip,
            id_usuario=usuario.id_usuario,
            id_entidad=intervencion.id_intervencion,
            datos_after={"consentimiento_optout": True, "id_cita": intervencion.id_cita},
        )
        db.commit()
        db.refresh(intervencion)

    return _enriquecer_out(intervencion, db=db)


def liberar_cupo_desde_intervencion(
    db: Session,
    id_intervencion: int,
    motivo: str | None,
    *,
    usuario: Usuario,
    ip: str,
    ahora: datetime | None = None,
) -> CupoLiberadoOut:
    cita, intervencion = _bloquear_cita_e_intervencion(db, id_intervencion)

    if intervencion.respuesta_paciente != "SOLICITA_LIBERACION":
        raise Conflicto("El paciente no ha solicitado la liberación de su cupo", codigo="SIN_SOLICITUD_LIBERACION")

    cupo_existente = repository.obtener_cupo_por_cita_origen(db, cita.id_cita)
    if cupo_existente is not None or cita.estado_actual == "LIBERADA":
        raise Conflicto("El cupo de esta cita ya fue liberado previamente", codigo="CUPO_YA_LIBERADO")

    ahora_ref = ahora or datetime.now(timezone.utc)
    if cita.fecha_hora_cita <= ahora_ref:
        raise Conflicto("No se puede liberar una cita cuya fecha u hora ya pasó", codigo="CITA_PASADA")

    if not citas_public.permite_liberacion_por_intervencion(cita.estado_actual):
        raise Conflicto(f"La cita en estado '{cita.estado_actual}' no admite transición a LIBERADA", codigo="TRANSICION_INVALIDA")

    motivo_final = motivo or "Paciente cede su cupo voluntariamente mediante intervención preventiva"
    cita, nuevo_cupo = workflow_intervenciones.liberar(db, cita, motivo_final, usuario=usuario, ip=ip)
    db.commit()

    out = CupoLiberadoOut.model_validate(nuevo_cupo)
    out.id_cita_externa_origen = cita.id_cita_externa
    return out
