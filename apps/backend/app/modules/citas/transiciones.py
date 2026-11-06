"""Mutaciones propias de Citas, componibles y sin commit."""
from sqlalchemy.orm import Session

from app.core.errores import TransicionInvalida
from app.modules.auditoria.public import registrar_evento
from app.modules.auth.public import Principal as Usuario
from app.modules.citas.models import Cita, HistorialEstadoCita
from app.modules.citas.reglas import ESTADOS_DESENLACE, TRANSICIONES


def foto(cita: Cita) -> dict:
    return {"estado_actual": cita.estado_actual, "target_no_show": cita.target_no_show}


def validar(cita: Cita, estado_nuevo: str) -> None:
    permitidos = TRANSICIONES.get(cita.estado_actual, set())
    if estado_nuevo not in permitidos:
        opciones = ", ".join(sorted(permitidos)) or "ninguno (estado final)"
        raise TransicionInvalida(f"No se permite pasar de {cita.estado_actual} a {estado_nuevo}. Permitidos: {opciones}")


def aplicar(db: Session, cita: Cita, estado_nuevo: str, *, usuario: Usuario, ip: str, motivo: str | None,
            antes: dict, extra_despues: dict | None = None, registrar_auditoria: bool = True) -> None:
    validar(cita, estado_nuevo)
    anterior = cita.estado_actual
    cita.estado_actual = estado_nuevo
    if estado_nuevo in ESTADOS_DESENLACE:
        cita.target_no_show = ESTADOS_DESENLACE[estado_nuevo]
    db.add(HistorialEstadoCita(id_cita=cita.id_cita, id_usuario_actor=usuario.id_usuario,
        estado_anterior=anterior, estado_nuevo=estado_nuevo, motivo_cambio=motivo))
    if registrar_auditoria:
        # Nombre histórico del parámetro; append siempre por el contrato público.
        from app.modules.auditoria.public import registrar_evento as append
        append(db, modulo="CITAS", accion="UPDATE", entidad_afectada="citas", direccion_ip=ip,
            id_usuario=usuario.id_usuario, id_entidad=cita.id_cita, datos_before=antes,
            datos_after={**foto(cita), **(extra_despues or {})})
