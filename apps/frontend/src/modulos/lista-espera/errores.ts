import { ApiError } from "../../nucleo/api/cliente";

// RF-069, RF-071, RF-077 a RF-082 y REP-03: conflictos M06 y siguiente paso.
const MENSAJES: Readonly<Record<string, string>> = {
  CANDIDATO_DUPLICADO: "El paciente ya está activo o contactado en la lista de espera de esa especialidad.",
  CANDIDATO_CON_OFERTA: "El candidato tiene una oferta vigente. Cierra la oferta antes de continuar.",
  CANDIDATO_ASIGNADO: "El candidato ya está asignado y no admite ese cambio.",
  CANDIDATO_NO_COMPATIBLE: "El candidato ya no es compatible con el cupo. Revisa las propuestas actualizadas.",
  CUPO_NO_DISPONIBLE: "El cupo ya no está disponible para ofrecerlo. Revisa su estado actualizado.",
  CUPO_EXPIRADO: "El cupo está vencido: no admite ofertas ni reasignación.",
  CUPO_REASIGNADO: "El cupo ya fue reasignado. No se puede confirmar otra reasignación.",
  SIN_OFERTA_VIGENTE: "No hay una oferta vigente para este candidato. Actualiza el cupo antes de continuar.",
  CONFIRMACION_REQUERIDA: "Debes confirmar explícitamente la reasignación con el paciente antes de registrarla.",
  FORMATO_NO_DISPONIBLE: "El formato de exportación no está disponible. Prueba otro formato.",
  SIN_PERMISO: "Tu rol no tiene permiso para gestionar la lista de espera y la reasignación.",
  NO_ENCONTRADO: "No se encontró el registro solicitado. Actualiza la vista para consultar los datos vigentes.",
};
export function mensajeErrorM06(fallo: unknown): string {
  if (fallo instanceof ApiError) return MENSAJES[fallo.codigo] ?? fallo.message;
  return fallo instanceof Error ? fallo.message : "No se pudo completar la solicitud.";
}
