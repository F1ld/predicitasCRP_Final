import { ApiError } from "../../nucleo/api/cliente";

// RF-010, RF-020 a RF-024, RF-104 y RF-103: explica los conflictos M02/M09
// con una acción comprensible, aunque la respuesta no incluya detalle adicional.
const MENSAJES: Readonly<Record<string, string>> = {
  DESENLACE_ANTICIPADO: "No se puede registrar el desenlace de una cita futura. Espera hasta la fecha de la cita en Lima.",
  CHECK_IN_REGISTRADO: "La cita tiene una llegada registrada y no puede marcarse como No asistió.",
  TRANSICION_INVALIDA: "La cita ya no admite ese cambio. Revisa su estado actualizado.",
  CITA_PASADA: "No se puede liberar el cupo de una cita pasada.",
  CHECK_IN_DUPLICADO: "La llegada (check-in) ya fue registrada para esta cita.",
  FUERA_DE_FECHA: "El check-in solo se puede registrar el día de la cita, según la hora de Lima.",
  ESTADO_FINAL: "Esta cita tiene un estado final y no admite check-in.",
  MOTOR_IA_NO_DISPONIBLE: "Motor de IA no disponible. Inténtalo de nuevo más tarde.",
  CITA_NO_ELEGIBLE: "Cita no elegible. El cálculo de riesgo requiere una cita futura en Recibida, Confirmada o Reprogramada.",
  MODELO_NO_HABILITADO: "Modelo no habilitado. Consulta al responsable del piloto.",
  CITA_DUPLICADA: "Ya existe una cita con ese identificador externo. Revisa el ID de cita.",
  FECHAS_INCONSISTENTES: "La fecha de registro no puede ser posterior a la fecha de la cita.",
  FUERA_DE_PERIMETRO: "Revisa el perímetro del piloto: sede San Isidro, especialidades autorizadas y citas de lunes a sábado.",
  SIN_PERMISO: "Tu rol no tiene permiso para realizar esta acción.",
  NO_ENCONTRADO: "No se encontró la cita.",
};

export function mensajeErrorCitas(fallo: unknown): string {
  if (fallo instanceof ApiError) return MENSAJES[fallo.codigo] ?? fallo.message;
  return fallo instanceof Error ? fallo.message : "No se pudo completar la solicitud.";
}
