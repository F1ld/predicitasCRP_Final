"use strict";
// Comprobación estructural local: evita presentar respuestas incompletas como ceros.
import { ESPECIALIDADES, ESTADOS_CITA, ESTADOS_INTERVENCION, RIESGOS, TIPOS, type PanelPendientesOut, type PanelResumenOut } from "./tipos";

function registro(v: unknown): v is Record<string, unknown> { return typeof v === "object" && v !== null && !Array.isArray(v); }
const entero = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const id = (v: unknown) => entero(v) && v > 0;
const texto = (v: unknown) => typeof v === "string";
const timestamp = (v: unknown) => typeof v === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v));
const especialidad = (v: unknown) => ESPECIALIDADES.some(e => e === v);
const campos = (v: unknown, claves: readonly string[]) => registro(v) && claves.every(c => entero(v[c]));
function contexto(v: Record<string, unknown>): boolean {
  return typeof v.fecha === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v.fecha) && (v.especialidad === null || especialidad(v.especialidad)) && v.zona_horaria === "America/Lima" && timestamp(v.generado_en);
}
export function esResumenPanel(v: unknown): v is PanelResumenOut {
  if (!registro(v) || !contexto(v) || !registro(v.citas) || !registro(v.intervenciones) || !registro(v.cupos)) return false;
  const { citas: c, intervenciones: i, cupos: u } = v;
  return entero(c.total) && campos(c.por_estado, ESTADOS_CITA) && campos(c.por_riesgo, RIESGOS)
    && entero(i.total) && entero(i.citas_con_intervencion) && campos(i.por_estado, ESTADOS_INTERVENCION)
    && campos(u, ["total_liberados", "disponibles_para_ofrecer", "ofertas_en_curso", "reasignados_confirmados"])
    && campos(u.por_estado, ["DISPONIBLE", "EN_OFERTA", "REASIGNADO", "EXPIRADO"])
    && (u.tasa_recuperacion_pct === null || (typeof u.tasa_recuperacion_pct === "number" && Number.isFinite(u.tasa_recuperacion_pct) && u.tasa_recuperacion_pct >= 0 && u.tasa_recuperacion_pct <= 100))
    && campos(v.pendientes, ["citas_sin_intervencion", "intervenciones_sin_respuesta", "ofertas_en_curso"]);
}
export function esPaginaPanel(v: unknown): v is PanelPendientesOut {
  if (!registro(v) || !contexto(v) || !TIPOS.some(t => t === v.tipo) || !entero(v.total) || v.limite !== 20 || !entero(v.desplazamiento) || !Array.isArray(v.items)) return false;
  return v.items.every((item: unknown) => {
    if (!registro(item) || item.tipo !== v.tipo || !especialidad(item.especialidad) || !texto(item.medico)) return false;
    if (item.tipo === "OFERTAS_EN_CURSO") return id(item.id_cupo_liberado) && id(item.id_cita_origen) && timestamp(item.fecha_hora_cupo) && item.estado_cupo === "EN_OFERTA" && texto(item.origen_liberacion);
    if (!id(item.id_cita) || !texto(item.id_cita_externa) || !texto(item.paciente_anon_id) || !timestamp(item.fecha_hora_cita) || !ESTADOS_CITA.some(e => e === item.estado_cita)) return false;
    if (item.tipo === "CITAS_SIN_INTERVENCION") return id(item.id_prediccion) && (item.nivel_riesgo === "ALTO" || item.nivel_riesgo === "MEDIO") && typeof item.probabilidad_no_show === "number" && item.probabilidad_no_show >= 0 && item.probabilidad_no_show <= 1;
    return id(item.id_intervencion) && ["WHATSAPP", "SMS", "LLAMADA_TELEFONICA"].includes(String(item.canal_contacto)) && ["ENVIADA", "ENTREGADA"].includes(String(item.estado_intervencion)) && (item.fecha_hora_envio === null || timestamp(item.fecha_hora_envio));
  });
}
