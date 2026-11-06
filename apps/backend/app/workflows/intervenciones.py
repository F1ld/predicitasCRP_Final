"""Mutaciones cruzadas de respuesta/liberación; exclusivamente contratos públicos."""
from app.modules.auditoria.public import registrar_evento
from app.modules.citas import public as citas
from app.modules.lista_espera import public as espera


def aplicar_respuesta(db, cita, id_intervencion, respuesta, observacion, *, usuario, ip):
    anterior = cita.estado_actual
    id_cupo = None
    if respuesta == "CONFIRMA" and cita.estado_actual != "CONFIRMADA":
        if citas.permite_confirmacion_por_intervencion(cita.estado_actual):
            cita = citas.transicionar_cita_interno(db, cita.id_cita, "CONFIRMADA", usuario=usuario, ip=ip,
                motivo=observacion or "Confirmación del paciente mediante intervención preventiva", registrar_auditoria=False)
    elif respuesta == "SOLICITA_LIBERACION" and citas.permite_liberacion_por_intervencion(cita.estado_actual):
        cita = citas.transicionar_cita_interno(db, cita.id_cita, "LIBERADA", usuario=usuario, ip=ip,
            motivo=observacion or "Liberación voluntaria del paciente en intervención (RN04)", registrar_auditoria=False)
        cupo = espera.obtener_cupo_por_cita_origen(db, cita.id_cita)
        if cupo is None:
            cupo = espera.crear_cupo_liberado_interno(db, id_cita_origen=cita.id_cita, especialidad=cita.especialidad,
                medico=cita.medico, fecha_hora_cupo=cita.fecha_hora_cita, origen_liberacion="INTERVENCION_VOLUNTARIA",
                usuario=usuario, ip=ip, registrar_auditoria=False)
        id_cupo = cupo.id_cupo_liberado
        registrar_evento(db, modulo="INTERVENCION", accion="LIBERAR", entidad_afectada="cupos_liberados",
            direccion_ip=ip, id_usuario=usuario.id_usuario, id_entidad=id_cupo,
            datos_before={"estado_cita": anterior},
            datos_after={"id_cita_origen": cita.id_cita, "id_intervencion": id_intervencion,
                         "id_cupo_liberado": id_cupo, "estado_cita": "LIBERADA", "estado_cupo": "DISPONIBLE",
                         "origen_liberacion": "INTERVENCION_VOLUNTARIA"})
    return cita, id_cupo


def liberar(db, cita, motivo, *, usuario, ip):
    anterior = cita.estado_actual
    cita = citas.transicionar_cita_interno(db, cita.id_cita, "LIBERADA", usuario=usuario, ip=ip,
        motivo=motivo, registrar_auditoria=False)
    cupo = espera.crear_cupo_liberado_interno(db, id_cita_origen=cita.id_cita, especialidad=cita.especialidad,
        medico=cita.medico, fecha_hora_cupo=cita.fecha_hora_cita, origen_liberacion="INTERVENCION_VOLUNTARIA",
        usuario=usuario, ip=ip, registrar_auditoria=False)
    registrar_evento(db, modulo="INTERVENCION", accion="LIBERAR", entidad_afectada="cupos_liberados",
        direccion_ip=ip, id_usuario=usuario.id_usuario, id_entidad=cupo.id_cupo_liberado,
        datos_before={"estado_cita": anterior}, datos_after={"id_cupo_liberado": cupo.id_cupo_liberado,
            "id_cita_origen": cita.id_cita, "estado_cupo": "DISPONIBLE", "origen_liberacion": "INTERVENCION_VOLUNTARIA",
            "motivo": motivo})
    return cita, cupo
