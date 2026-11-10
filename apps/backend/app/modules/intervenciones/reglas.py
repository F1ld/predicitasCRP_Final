"""Reglas puras de M05 · Intervención inteligente (reglas-de-negocio F-09, D-013).

Sin acceso a base de datos: se prueban solas y las usan el servicio y el repositorio.
"""
from app.modules.citas.public import ESTADOS_ACTIVOS

# Riesgo que habilita el acompañamiento (RF-057). Nunca prioriza ni restringe la atención (RN12).
NIVELES_ELEGIBLES = ("ALTO", "MEDIO")

# Envío simulado (RF-059, RF-061): contratos/modulo-05.json → M05-E05.transiciones.
TRANSICIONES_ENVIO = {
    "PENDIENTE": {"ENVIADA", "FALLIDA"},
    "ENVIADA": {"ENTREGADA", "FALLIDA"},
}

# Límite de mensajes (RN07, RNF-032, RF-066): una intervención que llegue al paciente
# y un único reintento tras FALLIDA. Mientras haya una no fallida, no se crea otra.
MAX_FALLIDAS = 2

# Catálogo fijo (diccionario → catalogos.plantilla_mensaje). Textos de previsualización por canal.
PLANTILLAS = (
    ("RECORDATORIO_CONFIRMACION_V1", "Recordatorio de la cita con pedido de confirmación", {
        "WHATSAPP": "Hola, te contactamos desde Clínica Ricardo Palma para recordarte tu próxima cita. "
                    "Por favor, responde a este mensaje para confirmar si podrás asistir. Gracias.",
        "SMS": "Clínica Ricardo Palma: confirma si podrás asistir a tu próxima cita.",
    }),
    ("RECORDATORIO_LIBERACION_V1", "Recordatorio con la opción de ceder el cupo", {
        "WHATSAPP": "Hola, te contactamos desde Clínica Ricardo Palma por tu próxima cita. Si sabes que no podrás "
                    "asistir y deseas liberar el cupo, responde a este mensaje para solicitarlo. Gracias.",
        "SMS": "Clínica Ricardo Palma: si no asistirás, solicita liberar tu cupo.",
    }),
    ("LLAMADA_GUION_V1", "Guion de llamada de recordatorio y confirmación", {
        "LLAMADA_TELEFONICA": "Saluda e identifícate como personal de Clínica Ricardo Palma. Verifica que estás hablando "
                              "con la persona correcta antes de mencionar la cita. Recuérdale su próxima cita y pregunta "
                              "si podrá asistir. Si no puede, consulta si desea solicitar una reprogramación o liberar "
                              "el cupo. Agradece su tiempo y registra la respuesta.",
    }),
)


def canales_de(plantilla: str) -> tuple[str, ...]:
    for nombre, _, contenidos in PLANTILLAS:
        if nombre == plantilla:
            return tuple(contenidos)
    return ()


def obtener_catalogo_plantillas() -> list[dict]:
    """Genera el catálogo de plantillas disponible para el frontend (M05-E09, M05-V02)."""
    items = []
    for id_plantilla, descripcion, contenidos in PLANTILLAS:
        for canal, contenido in contenidos.items():
            items.append({
                "id": id_plantilla,
                "canal_contacto": canal,
                "descripcion": f"{descripcion} ({canal})",
                "contenido": contenido,
            })
    return items


def puede_crear_otra(estados_previos: list[str]) -> bool:
    """RF-066: True si la cita admite una intervención nueva."""
    if any(estado != "FALLIDA" for estado in estados_previos):
        return False
    return len(estados_previos) < MAX_FALLIDAS


def admite_respuesta(estado: str, canal: str) -> bool:
    """RF-062: desde ENTREGADA, o desde ENVIADA en una llamada telefónica."""
    return estado == "ENTREGADA" or (estado == "ENVIADA" and canal == "LLAMADA_TELEFONICA")


def acciones_disponibles(estado: str, canal: str, respuesta: str | None, optout: bool,
                         estado_cita: str) -> list[str]:
    """Botones de la vista de seguimiento (M05-V03), en el orden del contrato."""
    acciones = []
    if estado == "PENDIENTE":
        acciones.append("REGISTRAR_ENVIO")
    if estado in TRANSICIONES_ENVIO and "ENTREGADA" in TRANSICIONES_ENVIO[estado]:
        acciones.append("REGISTRAR_ENTREGA")
    if estado in TRANSICIONES_ENVIO:
        acciones.append("REGISTRAR_FALLO")
    if admite_respuesta(estado, canal):
        acciones.append("REGISTRAR_RESPUESTA")
    if estado == "RESPONDIDA" and not optout:
        acciones.append("REGISTRAR_OPTOUT")
    if estado == "RESPONDIDA" and estado_cita in ESTADOS_ACTIVOS:
        if respuesta == "CONFIRMA" and estado_cita != "CONFIRMADA":
            acciones.append("CONFIRMAR_CITA")
        if respuesta == "SOLICITA_LIBERACION":
            acciones.append("LIBERAR_CUPO")
    return acciones
