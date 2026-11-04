// RF-009, RF-018 y RNF-007: nombres del contrato M02 y seudónimo de paciente.
export type EstadoCita = "RECIBIDA" | "CONFIRMADA" | "REPROGRAMADA" | "CANCELADA" | "LIBERADA" | "ATENDIDA" | "NO_SHOW";
export type EstadoDestino = Exclude<EstadoCita, "RECIBIDA" | "LIBERADA">;
export type Especialidad = "CARDIOLOGIA" | "TRAUMATOLOGIA" | "PEDIATRIA";
export type NivelRiesgo = "BAJO" | "MEDIO" | "ALTO";

export interface CitaOut {
  id_cita: number;
  id_cita_externa: string;
  paciente_anon_id: string;
  sede: "SAN_ISIDRO";
  especialidad: Especialidad;
  medico: string;
  fecha_hora_cita: string;
  fecha_registro_cita: string;
  antelacion_dias: number;
  tipo_paciente: "NUEVO" | "CONTINUADOR";
  canal_origen: "WEB" | "CALL_CENTER" | "PRESENCIAL";
  franja_horaria: "MANANA" | "TARDE";
  dia_semana: "LUNES" | "MARTES" | "MIERCOLES" | "JUEVES" | "VIERNES" | "SABADO";
  inasistencias_previas: number;
  reprogramaciones_prev: number;
  asistencias_previas: number;
  estado_actual: EstadoCita;
  target_no_show: 0 | 1 | null;
}

export interface RiesgoResumen {
  id_prediccion: number;
  probabilidad_no_show: number;
  nivel_riesgo: NivelRiesgo;
  version_modelo: string;
  fecha_hora_inferencia: string;
  resultado_simulado: boolean;
}

export interface CitaResumenOut extends CitaOut {
  riesgo: RiesgoResumen | null;
  estado_intervencion: "PENDIENTE" | "ENVIADA" | "ENTREGADA" | "RESPONDIDA" | "FALLIDA" | null;
  respuesta_paciente: "CONFIRMA" | "SOLICITA_LIBERACION" | "SOLICITA_REPROG" | "SIN_RESPUESTA" | null;
  tiene_check_in: boolean;
}

export interface HistorialOut {
  id_historial: number;
  id_usuario_actor: number | null;
  estado_anterior: EstadoCita | null;
  estado_nuevo: EstadoCita;
  motivo_cambio: string | null;
  fecha_hora_evento: string;
}

// RF-010, RF-014, RN03 y RN17: la fuente declara los contadores; omitirlos permite
// que el servidor calcule solo los antecedentes conocidos al registrar la cita.
export interface CitaRegistroIn {
  id_cita_externa: string;
  paciente_anon_id: string;
  sede: CitaOut["sede"];
  especialidad: Especialidad;
  medico: string;
  fecha_hora_cita: string;
  fecha_registro_cita: string;
  tipo_paciente: CitaOut["tipo_paciente"];
  canal_origen: CitaOut["canal_origen"];
  inasistencias_previas?: number;
  asistencias_previas?: number;
  reprogramaciones_prev?: number;
}

export interface CatalogosOut {
  especialidades: string[];
  estados: string[];
  niveles_riesgo: string[];
  medicos: string[];
  canales_origen: string[];
  tipos_paciente: string[];
}

export interface CheckInOut {
  fecha_hora_check_in: string;
  id_usuario: number;
}

// RF-052 a RF-056, RN16, RN17: M09 conserva el snapshot del momento de inferencia.
export interface PrediccionOut {
  id_prediccion: number;
  id_cita: number;
  version_modelo: string;
  probabilidad_no_show: number;
  nivel_riesgo: NivelRiesgo;
  umbral_aplicado: number;
  features_snapshot: Record<string, unknown>;
  explicabilidad_resumen: string | null;
  fecha_hora_inferencia: string;
  resultado_simulado: boolean;
  ya_existia: boolean;
}

export type EstadoIntervencion = NonNullable<CitaResumenOut["estado_intervencion"]>;
export type RespuestaPaciente = NonNullable<CitaResumenOut["respuesta_paciente"]>;
export interface IntervencionOut {
  id_intervencion: number;
  id_cita: number;
  id_cita_externa: string;
  id_operador: number | null;
  canal_contacto: "WHATSAPP" | "SMS" | "LLAMADA_TELEFONICA";
  plantilla_mensaje: string;
  consentimiento_optout: boolean;
  estado_intervencion: EstadoIntervencion;
  respuesta_paciente: RespuestaPaciente | null;
  fecha_hora_envio: string;
  fecha_hora_respuesta: string | null;
  acciones_disponibles: ("REGISTRAR_ENVIO" | "REGISTRAR_ENTREGA" | "REGISTRAR_FALLO" | "REGISTRAR_RESPUESTA" | "REGISTRAR_OPTOUT" | "CONFIRMAR_CITA" | "LIBERAR_CUPO")[];
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
  franja_horaria: CitaOut["franja_horaria"];
  estado_cupo: "DISPONIBLE" | "EN_OFERTA" | "REASIGNADO" | "EXPIRADO";
  origen_liberacion: "INTERVENCION_VOLUNTARIA" | "CANCELACION_EXTERNA";
  liberado_en: string;
  oferta_vigente: OfertaOut | null;
}

export interface ReasignacionOut {
  id_reasignacion: number;
  id_cupo_liberado: number;
  id_candidato: number;
  paciente_anon_id: string;
  id_operador_confirma: number;
  confirmacion_humana: true;
  medio_confirmacion: "LLAMADA_CONFIRMADA" | "PRESENCIAL";
  observaciones: string | null;
  fecha_hora_reasigna: string;
}

// RF-018, RF-025 y RF-104: detalle completo M02 con formas M05, M06 y M09.
export interface CitaDetalleOut extends CitaOut {
  historial: HistorialOut[];
  check_in: CheckInOut | null;
  predicciones: PrediccionOut[];
  intervenciones: IntervencionOut[];
  cupo_liberado: CupoOut | null;
  reasignacion: ReasignacionOut | null;
}

export interface RechazoOut {
  fila: number;
  id_cita_externa: string;
  motivos: string[];
}

export interface ResultadoImportacionOut {
  recibidas: number;
  aceptadas: number;
  rechazadas: number;
  detalle_rechazos: RechazoOut[];
}
