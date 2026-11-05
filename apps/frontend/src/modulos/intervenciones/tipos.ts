// RF-057 a RF-068, REP-02: enums y tipos exactos de contratos y diccionario-de-datos.json.
export type Especialidad = "CARDIOLOGIA" | "TRAUMATOLOGIA" | "PEDIATRIA";
export type EstadoCita = "RECIBIDA" | "CONFIRMADA" | "REPROGRAMADA" | "CANCELADA" | "LIBERADA" | "ATENDIDA" | "NO_SHOW";
export type NivelRiesgo = "BAJO" | "MEDIO" | "ALTO";
export type FranjaHoraria = "MANANA" | "TARDE";
export type EstadoCupo = "DISPONIBLE" | "EN_OFERTA" | "REASIGNADO" | "EXPIRADO";
export type OrigenLiberacion = "INTERVENCION_VOLUNTARIA" | "CANCELACION_EXTERNA";

export interface RiesgoResumen {
  id_prediccion: number;
  probabilidad_no_show: number;
  nivel_riesgo: NivelRiesgo;
  version_modelo: string;
  fecha_hora_inferencia: string;
  resultado_simulado: boolean;
}

export interface OfertaOut {
  id_candidato: number;
  paciente_anon_id: string;
  id_operador: number;
  fecha_hora_oferta: string;
}

export interface CupoOut {
  id_cupo_liberado: number;
  id_cita_origen: number;
  id_cita_externa_origen: string;
  especialidad: Especialidad;
  medico: string;
  fecha_hora_cupo: string;
  franja_horaria: FranjaHoraria;
  estado_cupo: EstadoCupo;
  origen_liberacion: OrigenLiberacion;
  liberado_en: string;
  oferta_vigente: OfertaOut | null;
}

export type CanalContacto = "WHATSAPP" | "SMS" | "LLAMADA_TELEFONICA";
export type EstadoIntervencion = "PENDIENTE" | "ENVIADA" | "ENTREGADA" | "RESPONDIDA" | "FALLIDA";
export type RespuestaPaciente = "CONFIRMA" | "SOLICITA_LIBERACION" | "SOLICITA_REPROG" | "SIN_RESPUESTA";
export type AccionIntervencion = "REGISTRAR_ENVIO" | "REGISTRAR_ENTREGA" | "REGISTRAR_FALLO" | "REGISTRAR_RESPUESTA" | "REGISTRAR_OPTOUT" | "CONFIRMAR_CITA" | "LIBERAR_CUPO";
export interface IntervencionOut {
  id_intervencion: number;
  id_cita: number;
  id_cita_externa: string;
  id_operador: number | null;
  canal_contacto: CanalContacto;
  plantilla_mensaje: string;
  consentimiento_optout: boolean;
  estado_intervencion: EstadoIntervencion;
  respuesta_paciente: RespuestaPaciente | null;
  fecha_hora_envio: string;
  fecha_hora_respuesta: string | null;
  acciones_disponibles: AccionIntervencion[];
}
export interface ElegibleOut {
  id_cita: number;
  id_cita_externa: string;
  paciente_anon_id: string;
  especialidad: Especialidad;
  medico: string;
  fecha_hora_cita: string;
  estado_actual: EstadoCita;
  riesgo: RiesgoResumen;
  intervenciones_previas: number;
}
export interface PlantillaOut {
  id: string;
  canal_contacto: CanalContacto;
  descripcion: string;
  contenido: string;
}
export interface Rep02Fila {
  id_intervencion: number;
  id_cita_externa: string;
  especialidad: Especialidad;
  nivel_riesgo: NivelRiesgo | null;
  canal_contacto: CanalContacto;
  estado_intervencion: EstadoIntervencion;
  respuesta_paciente: RespuestaPaciente | null;
  tiempo_respuesta_minutos: number | null;
  cupo_liberado: boolean;
}
export interface Rep02Out {
  resumen: { enviadas: number; entregadas: number; respondidas: number; confirmaciones: number; liberaciones: number; tasa_respuesta: number };
  por_canal: { canal_contacto: CanalContacto; respuesta_paciente: RespuestaPaciente | null; cantidad: number }[];
  filas: Rep02Fila[];
  resultado_simulado: boolean;
}
export const CANALES: readonly CanalContacto[] = ["WHATSAPP", "SMS", "LLAMADA_TELEFONICA"];
export const ESTADOS: readonly EstadoIntervencion[] = ["PENDIENTE", "ENVIADA", "ENTREGADA", "RESPONDIDA", "FALLIDA"];
export const RESPUESTAS: readonly RespuestaPaciente[] = ["CONFIRMA", "SOLICITA_LIBERACION", "SOLICITA_REPROG", "SIN_RESPUESTA"];
export const ESPECIALIDADES: readonly Especialidad[] = ["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"];
export const NIVELES: readonly NivelRiesgo[] = ["ALTO", "MEDIO", "BAJO"];
