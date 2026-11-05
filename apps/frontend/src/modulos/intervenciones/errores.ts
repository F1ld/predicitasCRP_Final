import { ApiError } from "../../nucleo/api/cliente";

// RF-058, RF-063 a RF-068, RN07, RN13: explicar el rechazo sin eludir al servidor.
const CONFLICTOS: Record<string, string> = {
  MODO_SOMBRA: "El modo sombra está activo. No se pueden crear intervenciones mientras esté habilitado.",
  OPTOUT_VIGENTE: "El paciente solicitó no recibir comunicaciones. Ninguna de sus citas admite nuevas intervenciones.",
  LIMITE_INTERVENCION: "La cita alcanzó el límite de intervenciones: una que llegue al paciente y un único reintento tras un fallo.",
  NO_ELEGIBLE: "Esta cita ya no es elegible. Debe ser futura, estar en un estado no final y tener riesgo alto o medio.",
  CONSENTIMIENTO_REQUERIDO: "Debes confirmar que el paciente tiene consentimiento para recibir comunicaciones.",
  TRANSICION_INVALIDA: "La acción no está permitida en el estado actual. Actualiza el seguimiento antes de continuar.",
  SIN_SOLICITUD_LIBERACION: "Solo puedes liberar un cupo si el paciente solicitó su liberación.",
  CITA_PASADA: "No se puede liberar el cupo de una cita que ya pasó.",
  CUPO_YA_LIBERADO: "El cupo de esta cita ya fue liberado. Actualiza el seguimiento para consultar su estado.",
  FORMATO_NO_DISPONIBLE: "El formato solicitado no está disponible. Prueba otra opción de exportación.",
};
export function mensajeError(error: unknown): string {
  if (error instanceof ApiError) return CONFLICTOS[error.codigo] ?? error.mensaje;
  return error instanceof Error ? error.message : "No se pudo completar la solicitud.";
}
export function camposError(error: unknown): Record<string, string> {
  return error instanceof ApiError ? Object.fromEntries(Object.entries(error.campos).map(([campo, mensaje]) => [campo.replace(/^body\./, ""), mensaje])) : {};
}
