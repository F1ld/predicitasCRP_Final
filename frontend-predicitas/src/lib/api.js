const API_URL = (import.meta.env.VITE_API_URL?.trim() || "http://127.0.0.1:8000").replace(/\/+$/, "");
export const SESION_EXPIRADA = "predicitas:sesion-expirada";
const CLAVE_TOKEN = "predicitas_token";

export const token = {
  leer: () => sessionStorage.getItem(CLAVE_TOKEN),
  guardar: (valor) => sessionStorage.setItem(CLAVE_TOKEN, valor),
  borrar: () => sessionStorage.removeItem(CLAVE_TOKEN),
};

export class ApiError extends Error {
  constructor(status, detalle) {
    const crudo = Array.isArray(detalle)
      ? detalle.map((error) => `${(error.loc || []).slice(1).join(" / ")}: ${error.msg}`).join("; ")
      : typeof detalle === "string" ? detalle : "No se pudo completar la solicitud.";
    const mensaje = crudo.replace(/\s*\((?:RF|RN|RNF)[^)]*\)/gi, "").trim();
    super(mensaje);
    this.status = status;
  }
}

export async function api(ruta, { metodo = "GET", params, json, form, archivo, signal } = {}) {
  const url = new URL(API_URL + ruta);
  Object.entries(params || {}).forEach(([clave, valor]) => {
    if (valor !== "" && valor !== null && valor !== undefined) url.searchParams.set(clave, valor);
  });
  const credencial = token.leer();
  const headers = credencial ? { Authorization: `Bearer ${credencial}` } : {};
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(form);
  } else if (archivo) {
    body = archivo; // El navegador establece el boundary de multipart/form-data.
  }
  let respuesta;
  try {
    respuesta = await fetch(url, { method: metodo, headers, body, signal });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(0, "No se pudo conectar con el servidor. Comprueba que el backend está encendido.");
  }
  if (respuesta.status === 401 && ruta !== "/auth/login" && token.leer() === credencial) {
    token.borrar();
    window.dispatchEvent(new Event(SESION_EXPIRADA));
  }
  if (!respuesta.ok) {
    let detalle = "No se pudo completar la solicitud.";
    try {
      const datos = await respuesta.json();
      detalle = datos.detalle ?? datos.detail ?? detalle;
    } catch { /* Una respuesta no JSON también debe convertirse en un error legible. */ }
    throw new ApiError(respuesta.status, detalle);
  }
  return respuesta.status === 204 ? null : respuesta.json();
}
