// RNF-016: todas las fechas visibles se presentan en America/Lima.
export function formatearFechaHora(valor: string | null | undefined): string {
  if (!valor) return "—";
  return new Intl.DateTimeFormat("es-PE", {
    timeZone: "America/Lima", dateStyle: "short", timeStyle: "short",
  }).format(new Date(valor));
}
export const ETIQUETAS: Record<string, string> = {
  RECIBIDA: "Recibida", CONFIRMADA: "Confirmada", REPROGRAMADA: "Reprogramada",
  CANCELADA: "Cancelada", LIBERADA: "Liberada", ATENDIDA: "Atendida", NO_SHOW: "No asistió",
  CARDIOLOGIA: "Cardiología", TRAUMATOLOGIA: "Traumatología", PEDIATRIA: "Pediatría",
  ADMINISTRADOR: "Administrador", RECEPCION: "Recepción", TECNICO_IA: "Técnico IA",
  SAN_ISIDRO: "San Isidro", MANANA: "Mañana", TARDE: "Tarde",
};
export const etiqueta = (valor: string | null | undefined): string => valor ? ETIQUETAS[valor] || valor : "—";
