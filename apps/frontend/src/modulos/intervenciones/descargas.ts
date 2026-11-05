import { ApiError, esCancelacion, SESION_EXPIRADA, token } from "../../nucleo/api/cliente";

const API_URL = (import.meta.env.VITE_API_URL?.trim() || "http://127.0.0.1:8000").replace(/\/+$/, "");
const MENSAJE_GENERICO = "No se pudo completar la solicitud.";

function esRegistro(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

function detalleError(valor: unknown) {
  if (!esRegistro(valor) || !esRegistro(valor.error)) return null;
  const { codigo, mensaje, campos } = valor.error;
  if (typeof codigo !== "string" || typeof mensaje !== "string") return null;
  if (campos !== undefined && (!esRegistro(campos) || !Object.values(campos).every((campo) => typeof campo === "string"))) return null;
  return { codigo, mensaje, campos: campos as Record<string, string> | undefined };
}

/** REP-02, RNF-004: descarga el archivo auditado por el servidor con la sesión vigente.
 * api<T> procesa JSON; este adaptador local conserva sus errores y protección ante 401 atrasados.
 */
export async function descargarReporte(params: URLSearchParams, formato: "csv" | "xlsx"): Promise<void> {
  const url = new URL(`${API_URL}/reportes/rep-02`);
  params.forEach((valor, clave) => { if (valor) url.searchParams.set(clave, valor); });
  url.searchParams.set("formato", formato);
  const credencial = token.leer();
  let respuesta: Response;
  try {
    respuesta = await fetch(url, { method: "GET", headers: credencial ? { Authorization: `Bearer ${credencial}` } : {} });
  } catch (error: unknown) {
    if (esCancelacion(error)) throw error;
    throw new ApiError(0, "ERROR_CONEXION", "No se pudo conectar con el servidor. Comprueba que el backend está encendido.");
  }
  if (!respuesta.ok) {
    let detalle: ReturnType<typeof detalleError> = null;
    try { detalle = detalleError(await respuesta.json()); }
    catch { /* El servidor puede devolver una respuesta no JSON. */ }
    if ((respuesta.status === 401 || detalle?.codigo === "SESION_INVALIDA") && token.leer() === credencial) {
      token.borrar();
      window.dispatchEvent(new Event(SESION_EXPIRADA));
    }
    throw new ApiError(respuesta.status, detalle?.codigo ?? "ERROR_DESCONOCIDO", detalle?.mensaje ?? MENSAJE_GENERICO, detalle?.campos);
  }
  const archivo = await respuesta.blob();
  const nombreServidor = respuesta.headers.get("Content-Disposition")?.match(/filename\s*=\s*"?([^";]+)"?/i)?.[1]?.trim();
  // RNF-007: solo el archivo generado por REP-02; no se reconstruyen datos en el navegador.
  const nombre = nombreServidor?.split(/[\\/]/).at(-1) || `rep-02.${formato}`;
  const enlace = document.createElement("a");
  const objeto = URL.createObjectURL(archivo);
  try {
    enlace.href = objeto;
    enlace.download = nombre;
    document.body.append(enlace);
    enlace.click();
  } finally {
    enlace.remove();
    URL.revokeObjectURL(objeto);
  }
}
