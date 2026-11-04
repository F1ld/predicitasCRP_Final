import type { Rol } from "../../nucleo/api/tipos";
import type { EstadoCita, EstadoDestino } from "./tipos";

// RF-019 a RF-024, RN01: F-06 permite otra reprogramación desde REPROGRAMADA;
// el servidor valida fecha, check-in y atomicidad del cambio.
export const TRANSICIONES: Readonly<Record<EstadoCita, readonly EstadoDestino[]>> = {
  RECIBIDA: ["CONFIRMADA", "REPROGRAMADA", "CANCELADA", "ATENDIDA", "NO_SHOW"],
  CONFIRMADA: ["REPROGRAMADA", "CANCELADA", "ATENDIDA", "NO_SHOW"],
  REPROGRAMADA: ["CONFIRMADA", "REPROGRAMADA", "CANCELADA", "ATENDIDA", "NO_SHOW"],
  CANCELADA: [], LIBERADA: [], ATENDIDA: [], NO_SHOW: [],
};
export const ESTADOS = Object.keys(TRANSICIONES) as EstadoCita[];
export const ROLES_ESCRITURA: Rol[] = ["ADMINISTRADOR", "RECEPCION"];
