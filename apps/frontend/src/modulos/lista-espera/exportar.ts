import { ApiError, esCancelacion, SESION_EXPIRADA, token } from "../../nucleo/api/cliente";

export interface FiltrosRep03 {
  desde?: string;
  hasta?: string;
  especialidad?: string;
  id_operador?: string;
}
export type FormatoExportacion = "csv" | "xlsx";
const API_URL = (import.meta.env.VITE_API_URL?.trim() || "http://127.0.0.1:8000").replace(/\/+$/, "");
const MENSAJE_GENERICO = "No se pudo completar la solicitud.";

function registro(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

async function errorRespuesta(respuesta: Response, credencial: string | null): Promise<never> {
  let codigo = "ERROR_DESCONOCIDO";
  let mensaje = MENSAJE_GENERICO;
  let campos: Record<string, string> = {};
  try {
    const datos: unknown = await respuesta.json();
    if (registro(datos) && registro(datos.error) && typeof datos.error.codigo === "string" && typeof datos.error.mensaje === "string") {
      const adicionales = datos.error.campos;
      if (adicionales === undefined || (registro(adicionales) && Object.values(adicionales).every((valor) => typeof valor === "string"))) {
        codigo = datos.error.codigo; mensaje = datos.error.mensaje;
        campos = (adicionales as Record<string, string> | undefined) ?? {};
      }
    }
  } catch { /* El formato común conserva un mensaje genérico para errores sin JSON. */ }
  // RNF-004: una exportación antigua no invalida una sesión más reciente.
  if ((respuesta.status === 401 || codigo === "SESION_INVALIDA") && token.leer() === credencial) {
    token.borrar(); window.dispatchEvent(new Event(SESION_EXPIRADA));
  }
  throw new ApiError(respuesta.status, codigo, mensaje, campos);
}

// RF-094/REP-03: el servidor genera el archivo y audita EXPORT; el navegador solo lo descarga.
export async function descargarRep03(formato: FormatoExportacion, filtros: FiltrosRep03, signal?: AbortSignal): Promise<string> {
  const url = new URL(`${API_URL}/reportes/rep-03`);
  for (const nombre of ["desde", "hasta", "especialidad", "id_operador"] as const) {
    const valor = filtros[nombre];
    if (valor) url.searchParams.set(nombre, valor);
  }
  url.searchParams.set("formato", formato);
  const credencial = token.leer();
  let respuesta: Response;
  try {
    respuesta = await fetch(url, { method: "GET", headers: credencial ? { Authorization: `Bearer ${credencial}` } : {}, signal });
  } catch (fallo: unknown) {
    if (esCancelacion(fallo)) throw fallo;
    throw new ApiError(0, "ERROR_CONEXION", "No se pudo conectar con el servidor. Comprueba que el backend está encendido.");
  }
  if (!respuesta.ok) return errorRespuesta(respuesta, credencial);
  const archivo = await respuesta.blob();
  if (signal?.aborted) throw new DOMException("Solicitud cancelada", "AbortError");
  // Nombre fijo por formato: ningún nombre remoto puede introducir rutas o extensiones distintas.
  const nombre = `rep-03_reasignaciones.${formato}`;
  const recurso = URL.createObjectURL(archivo);
  const enlace = document.createElement("a");
  try {
    enlace.href = recurso; enlace.download = nombre;
    document.body.append(enlace); enlace.click();
  } finally {
    enlace.remove(); URL.revokeObjectURL(recurso);
  }
  return nombre;
}
