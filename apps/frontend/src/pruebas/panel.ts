// Datos sintéticos compartidos por las pruebas del panel, no un caso ejecutable.
import type { ItemPendiente, PanelPendientesOut, PanelResumenOut, TipoPendiente } from "../modulos/panel/tipos";

export const CONTEXTO = { fecha: "2026-11-09", especialidad: null, zona_horaria: "America/Lima", generado_en: "2026-11-09T09:00:00-05:00" } as const;
export function resumenPrueba(): PanelResumenOut {
  return { ...CONTEXTO,
    citas: { total: 10, por_estado: { RECIBIDA: 4, CONFIRMADA: 2, REPROGRAMADA: 1, CANCELADA: 1, LIBERADA: 1, ATENDIDA: 1, NO_SHOW: 0 }, por_riesgo: { ALTO: 3, MEDIO: 2, BAJO: 3, SIN_PREDICCION: 2 } },
    intervenciones: { total: 4, citas_con_intervencion: 3, por_estado: { PENDIENTE: 0, ENVIADA: 1, ENTREGADA: 1, RESPONDIDA: 1, FALLIDA: 1 } },
    cupos: { total_liberados: 4, por_estado: { DISPONIBLE: 1, EN_OFERTA: 1, REASIGNADO: 1, EXPIRADO: 1 }, disponibles_para_ofrecer: 1, ofertas_en_curso: 1, reasignados_confirmados: 1, tasa_recuperacion_pct: 25 },
    pendientes: { citas_sin_intervencion: 2, intervenciones_sin_respuesta: 1, ofertas_en_curso: 1 },
  };
}
export const citaPrueba: ItemPendiente = { tipo: "CITAS_SIN_INTERVENCION", id_cita: 101, id_cita_externa: "CITA-DEMO-101", paciente_anon_id: "PAC-DEMO-01", fecha_hora_cita: "2026-11-09T14:00:00-05:00", especialidad: "CARDIOLOGIA", medico: "Profesional sintético", estado_cita: "RECIBIDA", id_prediccion: 501, nivel_riesgo: "ALTO", probabilidad_no_show: 0.7 };
export const intervencionPrueba: ItemPendiente = { tipo: "INTERVENCIONES_SIN_RESPUESTA", id_cita: 102, id_cita_externa: "CITA-DEMO-102", paciente_anon_id: "PAC-DEMO-02", fecha_hora_cita: "2026-11-09T15:00:00-05:00", especialidad: "PEDIATRIA", medico: "Profesional sintético", estado_cita: "CONFIRMADA", id_intervencion: 17, canal_contacto: "WHATSAPP", estado_intervencion: "ENVIADA", fecha_hora_envio: null };
export const ofertaPrueba: ItemPendiente = { tipo: "OFERTAS_EN_CURSO", id_cupo_liberado: 42, id_cita_origen: 103, fecha_hora_cupo: "2026-11-09T16:00:00-05:00", especialidad: "CARDIOLOGIA", medico: "Profesional sintético", estado_cupo: "EN_OFERTA", origen_liberacion: "CANCELACION_EXTERNA" };
export function paginaPrueba(tipo: TipoPendiente = "CITAS_SIN_INTERVENCION"): PanelPendientesOut {
  const item = tipo === "CITAS_SIN_INTERVENCION" ? citaPrueba : tipo === "INTERVENCIONES_SIN_RESPUESTA" ? intervencionPrueba : ofertaPrueba;
  return { ...CONTEXTO, tipo, total: 1, limite: 20, desplazamiento: 0, items: [item] };
}
export function respuestaPrueba(datos: unknown, status = 200) { return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } }); }
