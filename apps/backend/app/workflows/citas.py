"""Cancelación y cupo: no conoce filas ORM ni abre otra transacción."""
from app.core.errores import Conflicto, NoEncontrado
from app.modules.auditoria.public import registrar_evento
from app.modules.citas import public as citas
from app.modules.lista_espera import public as espera


def cancelar_liberando(db, id_cita, *, usuario, ip, ahora, motivo):
    cita = citas.obtener_cita_consulta(db, id_cita, bloquear=True)
    if cita is None:
        raise NoEncontrado(f"No existe la cita {id_cita}")
    if cita.fecha_hora_cita <= ahora:
        raise Conflicto("Solo se libera el cupo de una cita futura", codigo="CITA_PASADA")
    cupo = espera.crear_cupo_liberado_interno(db, id_cita_origen=id_cita,
        especialidad=cita.especialidad, medico=cita.medico, fecha_hora_cupo=cita.fecha_hora_cita,
        origen_liberacion="CANCELACION_EXTERNA", usuario=usuario, ip=ip, registrar_auditoria=False)
    citas.transicionar_cita_interno(db, id_cita, "CANCELADA", usuario=usuario, ip=ip, motivo=motivo)
    registrar_evento(db, modulo="REASIGNACION", accion="LIBERAR", entidad_afectada="cupos_liberados",
        direccion_ip=ip, id_usuario=usuario.id_usuario, id_entidad=cupo.id_cupo_liberado,
        datos_after={"id_cita_origen": id_cita, "estado_cupo": cupo.estado_cupo,
                     "origen_liberacion": cupo.origen_liberacion,
                     "fecha_hora_cupo": cupo.fecha_hora_cupo.isoformat()})
