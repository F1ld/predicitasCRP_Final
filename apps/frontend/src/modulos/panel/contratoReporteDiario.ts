import { validarFiltros } from "./consulta";
import { hoyLima } from "./formato";
import { ESPECIALIDADES } from "./tipos";

export const RUTA_REPORTE_DIARIO = "/panel/reporte-diario";
export const RIESGOS = ["BAJO", "MEDIO", "ALTO"] as const;

export interface FiltrosReporte {
  fecha: string;
  especialidad: string;
  nivel_riesgo: string;
}

interface FilaReporte {
  hora: string;
  id_cita_externa: string;
  especialidad: string;
  medico: string;
  antelacion_dias: number;
  probabilidad_no_show: number | null;
  nivel_riesgo: string | null;
  estado_intervencion: string | null;
  respuesta_paciente: string | null;
}

interface GrupoReporte {
  especialidad: string;
  franja_horaria: "MANANA" | "TARDE";
  subtotal: number;
  filas: FilaReporte[];
}

export interface ReporteDiarioOut {
  fecha: string;
  filtros: { especialidad: string | null; nivel_riesgo: string | null };
  total: number;
  grupos: GrupoReporte[];
}

export function leerFiltrosReporte(parametros: URLSearchParams): FiltrosReporte {
  return {
    fecha: parametros.get("fecha") ?? hoyLima(),
    especialidad: parametros.get("especialidad") ?? "",
    nivel_riesgo: parametros.get("nivel_riesgo") ?? "",
  };
}

export function validarFiltrosReporte({ fecha, especialidad, nivel_riesgo }: FiltrosReporte): string {
  return validarFiltros(fecha, especialidad) ||
    (nivel_riesgo && !RIESGOS.some(riesgo => riesgo === nivel_riesgo) ? "Selecciona un nivel de riesgo válido." : "");
}

export function parametrosReporte({ fecha, especialidad, nivel_riesgo }: FiltrosReporte) {
  const parametros = new URLSearchParams({ fecha });
  if (especialidad) parametros.set("especialidad", especialidad);
  if (nivel_riesgo) parametros.set("nivel_riesgo", nivel_riesgo);
  return parametros;
}

function objeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

function textoONulo(valor: unknown) {
  return valor === null || typeof valor === "string";
}

function esFila(valor: unknown, especialidad: string): valor is FilaReporte {
  if (!objeto(valor)) return false;
  const { hora, probabilidad_no_show: probabilidad, nivel_riesgo: riesgo } = valor;
  return typeof hora === "string" && /^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?$/.test(hora) &&
    typeof valor.id_cita_externa === "string" && valor.especialidad === especialidad &&
    typeof valor.medico === "string" && typeof valor.antelacion_dias === "number" &&
    Number.isSafeInteger(valor.antelacion_dias) && valor.antelacion_dias >= 0 &&
    (probabilidad === null || (typeof probabilidad === "number" && probabilidad >= 0 && probabilidad <= 1)) &&
    (riesgo === null || RIESGOS.some(nivel => nivel === riesgo)) &&
    textoONulo(valor.estado_intervencion) && textoONulo(valor.respuesta_paciente);
}

export function esReporteDiario(valor: unknown, filtros: FiltrosReporte): valor is ReporteDiarioOut {
  if (!objeto(valor) || !objeto(valor.filtros) || !Array.isArray(valor.grupos)) return false;
  if (valor.fecha !== filtros.fecha || valor.filtros.especialidad !== (filtros.especialidad || null) ||
      valor.filtros.nivel_riesgo !== (filtros.nivel_riesgo || null)) return false;
  let total = 0;
  const grupos = new Set<string>();
  for (const grupo of valor.grupos as unknown[]) {
    if (!objeto(grupo) || typeof grupo.especialidad !== "string" ||
        !ESPECIALIDADES.some(especialidad => especialidad === grupo.especialidad) ||
        (grupo.franja_horaria !== "MANANA" && grupo.franja_horaria !== "TARDE") ||
        !Array.isArray(grupo.filas) || grupo.filas.length === 0 || grupo.subtotal !== grupo.filas.length) return false;
    const { especialidad, franja_horaria } = grupo;
    const clave = `${especialidad}/${franja_horaria}`;
    if (grupos.has(clave) || !grupo.filas.every(fila => esFila(fila, especialidad))) return false;
    grupos.add(clave);
    total += grupo.filas.length;
  }
  return total === valor.total;
}
