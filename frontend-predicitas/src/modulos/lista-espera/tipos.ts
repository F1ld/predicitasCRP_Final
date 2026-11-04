import type { Rol } from "../../nucleo/api/tipos";

// RF-069 a RF-082, RN05: catálogos cerrados del diccionario; sin urgencia ni score.
export const ESPECIALIDADES = ["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"] as const;
export const FRANJAS = ["MANANA", "TARDE", "INDIFERENTE"] as const;
export const ESTADOS_CANDIDATO = ["ACTIVO", "CONTACTADO", "ASIGNADO", "DESISTIDO"] as const;
export const ESTADOS_CUPO = ["DISPONIBLE", "EN_OFERTA", "REASIGNADO", "EXPIRADO"] as const;
export const MEDIOS_CONFIRMACION = ["LLAMADA_CONFIRMADA", "PRESENCIAL"] as const;
export const ROLES_ESCRITURA: Rol[] = ["ADMINISTRADOR", "RECEPCION"];
export type Especialidad = typeof ESPECIALIDADES[number];
export type FranjaPreferida = typeof FRANJAS[number];
export type EstadoCandidato = typeof ESTADOS_CANDIDATO[number];
export type EstadoCupo = typeof ESTADOS_CUPO[number];
export type MedioConfirmacion = typeof MEDIOS_CONFIRMACION[number];

export interface CandidatoOut {
  id_candidato: number;
  paciente_anon_id: string;
  especialidad_req: Especialidad;
  franja_preferida: FranjaPreferida;
  estado_candidato: EstadoCandidato;
  prioridad_registro: number;
  fecha_registro: string;
}
export interface CandidatoRegistroIn {
  paciente_anon_id: string;
  especialidad_req: Especialidad;
  franja_preferida: FranjaPreferida;
}
export interface CandidatoCambioIn {
  franja_preferida?: FranjaPreferida;
  estado_candidato?: "DESISTIDO";
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
  franja_horaria: "MANANA" | "TARDE";
  estado_cupo: EstadoCupo;
  origen_liberacion: "INTERVENCION_VOLUNTARIA" | "CANCELACION_EXTERNA";
  liberado_en: string;
  oferta_vigente: OfertaOut | null;
}
// RF-079, RF-081, RF-082, RN11, RNF-029: el valor true es obligatorio
// tanto en el cuerpo explícito de confirmación como en el registro devuelto.
export interface ReasignacionOut {
  id_reasignacion: number;
  id_cupo_liberado: number;
  id_candidato: number;
  paciente_anon_id: string;
  id_operador_confirma: number;
  confirmacion_humana: true;
  medio_confirmacion: MedioConfirmacion;
  observaciones: string | null;
  fecha_hora_reasigna: string;
}
export interface HistorialOfertaOut {
  id_candidato: number;
  fecha_hora_oferta: string;
  cierre: "RECHAZA" | "SIN_RESPUESTA" | "REASIGNADO" | null;
}
export interface CupoDetalleOut extends CupoOut {
  reasignacion: ReasignacionOut | null;
  historial_ofertas: HistorialOfertaOut[];
}
export interface OfertaIn { id_candidato: number }
export interface CierreOfertaIn { respuesta: "RECHAZA" | "SIN_RESPUESTA" }
export interface ReasignacionIn {
  id_candidato: number;
  confirmacion_humana: true;
  medio_confirmacion: MedioConfirmacion;
  observaciones?: string;
}

// REP-03, RF-094: métricas operativas del servidor, sin reconstruir datos ni score.
export interface Rep03Fila {
  id_cupo_liberado: number;
  fecha_hora_cupo: string;
  especialidad: Especialidad;
  medico: string;
  horas_disponible: number;
  paciente_anon_id_asignado: string | null;
  id_operador_confirma: number | null;
  estado_cupo: EstadoCupo;
}
export interface Rep03Out {
  resumen: {
    cupos_liberados: number;
    cupos_reasignados: number;
    tasa_recuperacion: number;
    horas_promedio_matching: number | null;
  };
  por_especialidad: { especialidad: Especialidad; liberados: number; reasignados: number }[];
  filas: Rep03Fila[];
}
