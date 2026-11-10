import { hoyLima } from "./formato";
import { ESPECIALIDADES, TIPOS, type Especialidad, type TipoPendiente } from "./tipos";

export const LIMITE_PANEL = 20;
export interface ConsultaPanel { fecha: string; especialidad: string; tipo: TipoPendiente; desplazamiento: number }
export function validarFiltros(fecha: string, especialidad: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(fecha) || fecha < "0001-01-01" || fecha >= "9999-12-31") return "Selecciona una fecha válida para la jornada.";
  const instante = new Date(`${fecha}T12:00:00Z`);
  if (!Number.isFinite(instante.getTime()) || instante.toISOString().slice(0, 10) !== fecha) return "Selecciona una fecha válida para la jornada.";
  if (especialidad !== "" && !ESPECIALIDADES.includes(especialidad as Especialidad)) return "Selecciona una especialidad del catálogo o Todas las especialidades.";
  return "";
}
export function parametrosPanel(consulta: ConsultaPanel): URLSearchParams {
  const p = new URLSearchParams({ fecha: consulta.fecha });
  if (consulta.especialidad) p.set("especialidad", consulta.especialidad);
  p.set("tipo", consulta.tipo);
  p.set("desplazamiento", String(consulta.desplazamiento));
  return p;
}
export const rutaPanel = (consulta: ConsultaPanel) => `/panel?${parametrosPanel(consulta)}`;
export function leerConsulta(parametros: URLSearchParams, ahora = new Date()) {
  const tipo = parametros.get("tipo");
  const offset = parametros.get("desplazamiento") ?? "0";
  const numero = Number(offset);
  const consulta: ConsultaPanel = {
    fecha: parametros.get("fecha") ?? hoyLima(ahora), especialidad: parametros.get("especialidad") ?? "",
    tipo: TIPOS.includes(tipo as TipoPendiente) ? tipo as TipoPendiente : TIPOS[0],
    desplazamiento: /^\d+$/.test(offset) && Number.isSafeInteger(numero) && numero % LIMITE_PANEL === 0 ? numero : 0,
  };
  return { consulta, error: validarFiltros(consulta.fecha, consulta.especialidad), normalizada: parametrosPanel(consulta).toString() };
}
export function rutasApi(consulta: ConsultaPanel) {
  const p = new URLSearchParams({ fecha: consulta.fecha });
  if (consulta.especialidad) p.set("especialidad", consulta.especialidad);
  const resumen = `/panel/resumen?${p}`;
  p.set("tipo", consulta.tipo); p.set("limite", String(LIMITE_PANEL)); p.set("desplazamiento", String(consulta.desplazamiento));
  return { resumen, pendientes: `/panel/pendientes?${p}` };
}
