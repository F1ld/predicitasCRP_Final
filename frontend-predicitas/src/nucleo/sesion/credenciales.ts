import { token } from "../api/cliente";
import type { TokenOut } from "../api/tipos";

export const TOKEN_RENOVADO = "predicitas:token-renovado";
export const RENOVACION_SUSPENDIDA = "predicitas:renovacion-suspendida";
export const MENSAJE_INACTIVIDAD = "Tu sesión expiró por inactividad";
const CLAVE_MOTIVO = "predicitas_motivo_sesion";
const cambiosClave = new Set<{ credencial: string }>();

/** RF-008, RNF-004: el cambio de clave tiene prioridad sobre la renovación del mismo JWT. */
export function renovacionSuspendida(): boolean {
  const actual = token.leer();
  return [...cambiosClave].some(({ credencial }) => credencial === actual);
}

/** RF-008: cancela renovaciones locales y bloquea la adopción de JWT de otras pestañas durante el POST. */
export function suspenderRenovacion(credencial: string): () => void {
  const cambio = { credencial };
  cambiosClave.add(cambio);
  window.dispatchEvent(new Event(RENOVACION_SUSPENDIDA));
  return () => { cambiosClave.delete(cambio); };
}

/** RF-002, RNF-004: una respuesta anterior nunca recupera una sesión cerrada. */
export function guardarTokenRenovado(datos: TokenOut, credencialAnterior: string | null): boolean {
  if (!credencialAnterior || token.leer() !== credencialAnterior || !datos.access_token) return false;
  token.guardar(datos.access_token);
  window.dispatchEvent(new CustomEvent(TOKEN_RENOVADO, { detail: { anterior: credencialAnterior, datos } }));
  return true;
}

/** RF-002: la lectura no consume el aviso, incluso con React.StrictMode. */
export function leerMotivoSesion(): string {
  return sessionStorage.getItem(CLAVE_MOTIVO) ?? "";
}

export function limpiarMotivoSesion(): void {
  sessionStorage.removeItem(CLAVE_MOTIVO);
}

export function guardarMotivoInactividad(): void {
  sessionStorage.setItem(CLAVE_MOTIVO, MENSAJE_INACTIVIDAD);
}
