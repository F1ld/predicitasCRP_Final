const ZONA = "America/Lima";
export const numeroPanel = (valor: number) => new Intl.NumberFormat("es-PE").format(valor);
export const porcentajePanel = (valor: number) => `${new Intl.NumberFormat("es-PE", { maximumFractionDigits: 2 }).format(valor)} %`;

export function hoyLima(ahora = new Date()): string {
  const partes = new Intl.DateTimeFormat("es-PE", { timeZone: ZONA, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(ahora);
  const parte = (tipo: Intl.DateTimeFormatPartTypes) => partes.find(p => p.type === tipo)?.value;
  return `${parte("year")}-${parte("month")}-${parte("day")}`;
}
export function fechaPanel(fecha: string): string {
  // La jornada es una fecha de calendario, sin conversión desde medianoche UTC.
  const [ano, mes, dia] = fecha.split("-");
  return `${dia}/${mes}/${ano}`;
}
export function horaPanel(valor: string): string {
  return new Intl.DateTimeFormat("es-PE", { timeZone: ZONA, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(valor));
}
export function fechaHoraPanel(valor: string | null): string {
  if (valor === null) return "—";
  return new Intl.DateTimeFormat("es-PE", { timeZone: ZONA, dateStyle: "short", timeStyle: "short", hourCycle: "h23" }).format(new Date(valor));
}
