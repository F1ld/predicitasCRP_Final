import type { ErrorApi } from "./tipos";

const API_URL = (import.meta.env.VITE_API_URL?.trim() || "http://127.0.0.1:8000").replace(/\/+$/, "");
export const SESION_EXPIRADA = "predicitas:sesion-expirada";
const CLAVE_TOKEN = "predicitas_token";
const MENSAJE_GENERICO = "No se pudo completar la solicitud.";

// RNF-004: la credencial dura solo lo que dura esta pestaña.
export const token = {
  leer: (): string | null => sessionStorage.getItem(CLAVE_TOKEN),
  guardar: (valor: string): void => sessionStorage.setItem(CLAVE_TOKEN, valor),
  borrar: (): void => sessionStorage.removeItem(CLAVE_TOKEN),
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly codigo: string,
    public readonly mensaje: string = MENSAJE_GENERICO,
    public readonly campos: Record<string, string> = {},
  ) {
    super(mensaje);
    this.name = "ApiError";
  }
}

function esRegistro(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

// RNF-004: DOMException puede pertenecer a otro contexto del navegador/jsdom.
export function esCancelacion(error: unknown): boolean {
  return esRegistro(error) && error.name === "AbortError";
}

function leerError(valor: unknown): ErrorApi["error"] | null {
  if (!esRegistro(valor) || !esRegistro(valor.error)) return null;
  const { codigo, mensaje, campos } = valor.error;
  if (typeof codigo !== "string" || typeof mensaje !== "string") return null;
  if (campos !== undefined && (!esRegistro(campos) || !Object.values(campos).every((v) => typeof v === "string"))) return null;
  return { codigo, mensaje, campos: campos as Record<string, string> | undefined };
}

export interface OpcionesApi {
  metodo?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  params?: Record<string, string | number | boolean | null | undefined>;
  json?: unknown;
  form?: Record<string, string>;
  archivo?: FormData;
  signal?: AbortSignal;
}

// D-017 y RNF-004: formato único de errores y protección de sesiones nuevas
// frente a respuestas 401 atrasadas de una credencial anterior.
export async function api<T = unknown>(ruta: string, { metodo = "GET", params, json, form, archivo, signal }: OpcionesApi = {}): Promise<T | null> {
  const url = new URL(API_URL + ruta);
  Object.entries(params || {}).forEach(([clave, valor]) => {
    if (valor !== "" && valor !== null && valor !== undefined) url.searchParams.set(clave, String(valor));
  });
  const credencial = token.leer();
  const headers: Record<string, string> = credencial ? { Authorization: `Bearer ${credencial}` } : {};
  let body: BodyInit | undefined;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(form);
  } else if (archivo) {
    body = archivo; // El navegador establece el boundary de multipart/form-data.
  }
  let respuesta: Response;
  try {
    respuesta = await fetch(url, { method: metodo, headers, body, signal });
  } catch (error: unknown) {
    if (esCancelacion(error)) throw error;
    throw new ApiError(0, "ERROR_CONEXION", "No se pudo conectar con el servidor. Comprueba que el backend está encendido.");
  }
  if (!respuesta.ok) {
    let detalle: ErrorApi["error"] | null = null;
    try { detalle = leerError(await respuesta.json()); }
    catch { /* Errores no JSON se presentan con el mensaje genérico del contrato. */ }
    if ((respuesta.status === 401 || detalle?.codigo === "SESION_INVALIDA") && ruta !== "/auth/login" && token.leer() === credencial) {
      token.borrar();
      window.dispatchEvent(new Event(SESION_EXPIRADA));
    }
    throw new ApiError(respuesta.status, detalle?.codigo ?? "ERROR_DESCONOCIDO", detalle?.mensaje ?? MENSAJE_GENERICO, detalle?.campos);
  }
  return respuesta.status === 204 ? null : respuesta.json() as Promise<T>;
}
