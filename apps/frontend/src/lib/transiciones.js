// Refleja backend/app/modules/citas/reglas.py; el servidor valida la operación.
export const TRANSICIONES = {
  RECIBIDA: ["CONFIRMADA", "REPROGRAMADA", "CANCELADA", "ATENDIDA", "NO_SHOW"],
  CONFIRMADA: ["REPROGRAMADA", "CANCELADA", "ATENDIDA", "NO_SHOW"],
  REPROGRAMADA: ["CONFIRMADA", "CANCELADA", "ATENDIDA", "NO_SHOW"],
  CANCELADA: [], LIBERADA: [], ATENDIDA: [], NO_SHOW: [],
};
export const ESTADOS = Object.keys(TRANSICIONES);
export const ROLES_ESCRITURA = ["ADMINISTRADOR", "RECEPCION"];
