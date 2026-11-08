import { apiArchivo } from "../../nucleo/api/cliente";

// REP-02: el servidor genera y audita la descarga.
export async function descargarReporte(params: URLSearchParams, formato: "csv" | "xlsx"): Promise<void> {
  const filtros = Object.fromEntries([...params].filter(([, valor]) => valor));
  const { archivo, cabeceras } = await apiArchivo("/reportes/rep-02", { params: { ...filtros, formato } });
  const nombreServidor = cabeceras.get("Content-Disposition")?.match(/filename\s*=\s*"?([^";]+)"?/i)?.[1]?.trim();
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
