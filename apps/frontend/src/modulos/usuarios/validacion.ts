import { ApiError } from "../../nucleo/api/cliente";

// RF-004, RF-008: la clave se valida en vivo sin almacenarla fuera del formulario.
export function politicaClave(clave: string) {
  return {
    longitud: clave.length >= 8 && clave.length <= 128,
    letra: /\p{L}/u.test(clave),
    numero: /[0-9]/.test(clave),
  };
}

export function errorNombre(nombre: string): string {
  return nombre.length < 2 || nombre.length > 120 || nombre !== nombre.trim()
    ? "Usa entre 2 y 120 caracteres, sin espacios al inicio ni al final." : "";
}

export function errorCorreo(correo: string): string {
  return correo.length > 100 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correo)
    ? "Escribe un correo válido de hasta 100 caracteres." : "";
}

const CONFLICTOS: Record<string, string> = {
  CORREO_DUPLICADO: "Ya existe un usuario con ese correo institucional, incluso si cambia las mayúsculas.",
  ULTIMO_ADMINISTRADOR: "Debe quedar al menos un administrador activo. Activa o asigna a otro administrador antes de continuar.",
  AUTODESACTIVACION: "No puedes desactivar tu propia cuenta. Pide a otro administrador que gestione el cambio.",
  AUTOMODIFICACION_ROL: "No puedes cambiar tu propio rol. Pide a otro administrador que gestione el cambio.",
};

// RF-005, RF-006, RNF-001: se explican los conflictos conservando la regla del servidor.
export function mensajeError(error: unknown): string {
  if (error instanceof ApiError) return CONFLICTOS[error.codigo] ?? error.mensaje;
  return error instanceof Error ? error.message : "No se pudo completar la solicitud.";
}

export function camposError(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  return Object.fromEntries(Object.entries(error.campos).map(([campo, mensaje]) => [campo.replace(/^body\./, ""), mensaje]));
}
