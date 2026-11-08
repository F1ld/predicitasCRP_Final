import { apiArchivo } from "../../nucleo/api/cliente";

export interface FiltrosRep03 {
  desde?: string;
  hasta?: string;
  especialidad?: string;
  id_operador?: string;
}
export type FormatoExportacion = "csv" | "xlsx";
// RF-094/REP-03: el servidor genera el archivo y audita EXPORT; el navegador solo lo descarga.
export async function descargarRep03(formato: FormatoExportacion, filtros: FiltrosRep03, signal?: AbortSignal): Promise<string> {
  const { desde, hasta, especialidad, id_operador } = filtros;
  const { archivo } = await apiArchivo("/reportes/rep-03", {
    params: { desde, hasta, especialidad, id_operador, formato }, signal,
  });
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
