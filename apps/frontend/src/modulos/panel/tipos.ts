import type { Especialidad, EstadoCita, NivelRiesgo } from "../citas/tipos";
import type { EstadoCupo } from "../lista-espera/tipos";

export type { Especialidad };
export const ESPECIALIDADES = ["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"] as const;
export const ESTADOS_CITA: EstadoCita[] = ["RECIBIDA", "CONFIRMADA", "REPROGRAMADA", "CANCELADA", "LIBERADA", "ATENDIDA", "NO_SHOW"];
export const RIESGOS = ["ALTO", "MEDIO", "BAJO", "SIN_PREDICCION"] as const;
export const ESTADOS_INTERVENCION = ["PENDIENTE", "ENVIADA", "ENTREGADA", "RESPONDIDA", "FALLIDA"] as const;
export const TIPOS = ["CITAS_SIN_INTERVENCION", "INTERVENCIONES_SIN_RESPUESTA", "OFERTAS_EN_CURSO"] as const;
export type TipoPendiente = typeof TIPOS[number];
export const CATEGORIAS: Record<TipoPendiente, { titulo: string; ayuda: string; contador: keyof PanelResumenOut["pendientes"]; vacio: string }> = {
  CITAS_SIN_INTERVENCION: { titulo: "Citas sin intervención", contador: "citas_sin_intervencion", ayuda: "Citas recibidas de riesgo alto o medio, con horario futuro, sin intervención registrada y sin oposición de contacto.", vacio: "No hay citas sin intervención con estos filtros." },
  INTERVENCIONES_SIN_RESPUESTA: { titulo: "Intervenciones sin respuesta", contador: "intervenciones_sin_respuesta", ayuda: "Intervenciones enviadas o entregadas que siguen sin respuesta, asociadas a citas activas con horario futuro.", vacio: "No hay intervenciones pendientes de respuesta con estos filtros." },
  OFERTAS_EN_CURSO: { titulo: "Ofertas en curso", contador: "ofertas_en_curso", ayuda: "Cupos con una oferta en curso, horario futuro y sin reasignación confirmada.", vacio: "No hay ofertas en curso con estos filtros." },
};
export const ETIQUETAS: Record<string, string> = { ALTO: "Alto", MEDIO: "Medio", BAJO: "Bajo", SIN_PREDICCION: "Sin predicción", PENDIENTE: "Pendiente", ENVIADA: "Enviada", ENTREGADA: "Entregada", RESPONDIDA: "Respondida", FALLIDA: "Fallida", WHATSAPP: "WhatsApp", SMS: "SMS", LLAMADA_TELEFONICA: "Llamada telefónica", EN_OFERTA: "En oferta" };

export interface ContextoPanel { fecha: string; especialidad: Especialidad | null; zona_horaria: "America/Lima"; generado_en: string }
export interface PanelResumenOut extends ContextoPanel {
  citas: { total: number; por_estado: Record<EstadoCita, number>; por_riesgo: Record<typeof RIESGOS[number], number> };
  intervenciones: { total: number; citas_con_intervencion: number; por_estado: Record<typeof ESTADOS_INTERVENCION[number], number> };
  cupos: { total_liberados: number; por_estado: Record<EstadoCupo, number>; disponibles_para_ofrecer: number; ofertas_en_curso: number; reasignados_confirmados: number; tasa_recuperacion_pct: number | null };
  pendientes: { citas_sin_intervencion: number; intervenciones_sin_respuesta: number; ofertas_en_curso: number };
}
interface CitaPendiente { id_cita: number; id_cita_externa: string; paciente_anon_id: string; fecha_hora_cita: string; especialidad: Especialidad; medico: string; estado_cita: EstadoCita }
export interface CitaSinIntervencionOut extends CitaPendiente { tipo: "CITAS_SIN_INTERVENCION"; id_prediccion: number; nivel_riesgo: Exclude<NivelRiesgo, "BAJO">; probabilidad_no_show: number }
export interface IntervencionSinRespuestaOut extends CitaPendiente { tipo: "INTERVENCIONES_SIN_RESPUESTA"; id_intervencion: number; canal_contacto: "WHATSAPP" | "SMS" | "LLAMADA_TELEFONICA"; estado_intervencion: "ENVIADA" | "ENTREGADA"; fecha_hora_envio: string | null }
export interface OfertaEnCursoOut { tipo: "OFERTAS_EN_CURSO"; id_cupo_liberado: number; id_cita_origen: number; fecha_hora_cupo: string; especialidad: Especialidad; medico: string; estado_cupo: "EN_OFERTA"; origen_liberacion: string }
export type ItemPendiente = CitaSinIntervencionOut | IntervencionSinRespuestaOut | OfertaEnCursoOut;
export interface PanelPendientesOut extends ContextoPanel { tipo: TipoPendiente; total: number; limite: number; desplazamiento: number; items: ItemPendiente[] }
