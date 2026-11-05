import { useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../../nucleo/api/cliente";
import Icono from "../../nucleo/componentes/Icono";
import Mensaje from "../../nucleo/componentes/Mensaje";
import type { ResultadoImportacionOut } from "./tipos";
import "./citas.css";

const MAX_BYTES = 2 * 1024 * 1024;

function formatearTamano(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

// RF-011, RF-012 y RNF-007: importación CSV de citas seudonimizadas con soporte Drag & Drop
export default function Importar() {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<ResultadoImportacionOut | null>(null);
  const [arrastrando, setArrastrando] = useState(false);
  const importacionEnCurso = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function procesarArchivo(elegido?: File | null) {
    setResultado(null);
    setArchivo(null);
    setError("");

    if (!elegido) return;
    if (!/\.csv$/i.test(elegido.name)) {
      setError("Formato no válido: selecciona un archivo con extensión .csv.");
      return;
    }
    if (elegido.size > MAX_BYTES) {
      setError("El archivo supera el límite de 2 MB permitido.");
      return;
    }
    if (elegido.size === 0) {
      setError("El archivo seleccionado está vacío.");
      return;
    }
    setArchivo(elegido);
  }

  function seleccionar(evento: ChangeEvent<HTMLInputElement>) {
    const elegido = evento.target.files?.[0];
    procesarArchivo(elegido);
  }

  function manejarDragOver(evento: DragEvent<HTMLDivElement>) {
    evento.preventDefault();
    evento.stopPropagation();
    if (!enviando) {
      setArrastrando(true);
    }
  }

  function manejarDragEnter(evento: DragEvent<HTMLDivElement>) {
    evento.preventDefault();
    evento.stopPropagation();
    if (!enviando) {
      setArrastrando(true);
    }
  }

  function manejarDragLeave(evento: DragEvent<HTMLDivElement>) {
    evento.preventDefault();
    evento.stopPropagation();
    setArrastrando(false);
  }

  function manejarDrop(evento: DragEvent<HTMLDivElement>) {
    evento.preventDefault();
    evento.stopPropagation();
    setArrastrando(false);
    if (enviando) return;

    const archivos = evento.dataTransfer.files;
    if (archivos && archivos.length > 0) {
      procesarArchivo(archivos[0]);
    }
  }

  function limpiarArchivo() {
    setArchivo(null);
    setError("");
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  async function importar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!archivo || importacionEnCurso.current) return;
    const formulario = evento.currentTarget;
    const datos = new FormData();
    datos.append("archivo", archivo);
    importacionEnCurso.current = true;
    setEnviando(true);
    setError("");
    setResultado(null);
    try {
      const resp = await api<ResultadoImportacionOut>("/citas/importar", { metodo: "POST", archivo: datos });
      setResultado(resp);
      setArchivo(null);
      formulario.reset();
      if (inputRef.current) inputRef.current.value = "";
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "No se pudo completar la solicitud de importación.");
    } finally {
      importacionEnCurso.current = false;
      setEnviando(false);
    }
  }

  const resumen: [string, number, string][] = resultado
    ? [
        ["Recibidas", resultado.recibidas, "bg-slate-100 text-slate-800"],
        ["Aceptadas", resultado.aceptadas, "bg-emerald-50 text-emerald-800 border border-emerald-200"],
        ["Rechazadas", resultado.rechazadas, "bg-rose-50 text-rose-800 border border-rose-200"],
      ]
    : [];

  return (
    <>
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">INCORPORACIÓN AL PILOTO</p>
          <h1>Importar citas</h1>
          <p>Carga un archivo con las citas que quieres incorporar al seguimiento asistencial.</p>
        </div>
        <span className="contexto-horario">
          <Icono nombre="archivo" /> Formato CSV
        </span>
      </div>

      {error && <Mensaje>{error}</Mensaje>}

      <div className="importacion-layout">
        <section className="tarjeta importacion-principal">
          <div className="seccion-cabecera">
            <h2>Selecciona o arrastra tu archivo</h2>
            <p>Puedes arrastrar el archivo CSV directamente aquí o hacer clic para buscarlo.</p>
          </div>

          <form onSubmit={importar}>
            <fieldset disabled={enviando} className="space-y-5">
              {/* ZONA DE ARRASTRAR Y SOLTAR (DROPZONE) */}
              <div
                className={`selector-archivo selector-archivo-dropzone ${arrastrando ? "arrastrando" : ""}`}
                onDragOver={manejarDragOver}
                onDragEnter={manejarDragEnter}
                onDragLeave={manejarDragLeave}
                onDrop={manejarDrop}
                onClick={(e) => {
                  // Si no hizo clic directo en el botón de quitar, activa el input
                  if ((e.target as HTMLElement).tagName !== "BUTTON" && !(e.target as HTMLElement).closest("button")) {
                    inputRef.current?.click();
                  }
                }}
              >
                <span className={`archivo-ilustracion ${arrastrando ? "scale-110 bg-teal-100" : ""}`}>
                  <Icono nombre="importar" />
                </span>

                <div>
                  <label htmlFor="archivo" className="cursor-pointer font-bold text-slate-800 block text-center">
                    {arrastrando ? "¡Suelta tu archivo CSV aquí!" : "Arrastra y suelta tu archivo CSV aquí"}
                  </label>
                  <p className="text-xs text-slate-500 mt-1">
                    o haz clic en esta área para seleccionarlo desde tu equipo
                  </p>
                </div>

                <p className="text-xs text-slate-400">
                  Límite: Hasta 2 MB · Máximo 5.000 filas · Codificación UTF-8
                </p>

                {/* Input oculto/estilizado accesible */}
                <input
                  ref={inputRef}
                  id="archivo"
                  type="file"
                  accept=".csv,text/csv"
                  onChange={seleccionar}
                  className="sr-only"
                />

                {/* TARJETA DE ARCHIVO CARGADO */}
                {archivo && (
                  <div
                    className="archivo-seleccionado-card mt-2"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="flex items-center gap-2 overflow-hidden text-left">
                      <span className="w-2 h-2 rounded-full bg-teal-600 flex-shrink-0" />
                      <div className="truncate">
                        <p className="font-semibold text-slate-800 truncate text-xs">{archivo.name}</p>
                        <p className="text-[11px] text-slate-500">{formatearTamano(archivo.size)} · Listo para importar</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={limpiarArchivo}
                      className="ml-3 px-2 py-1 text-xs text-rose-600 hover:text-rose-800 hover:bg-rose-50 rounded transition-colors"
                      title="Quitar archivo seleccionado"
                    >
                      Quitar
                    </button>
                  </div>
                )}
              </div>

              <div className="importacion-envio">
                <p>Las filas válidas se validarán e incorporarán de inmediato a la base de datos.</p>
                <button className="boton" type="submit" disabled={!archivo || enviando}>
                  <Icono nombre="importar" />
                  {enviando ? "Procesando importación…" : "Importar archivo"}
                </button>
              </div>
            </fieldset>
          </form>
        </section>

        <aside className="importacion-ayuda">
          <h2>Antes de importar</h2>
          <ol>
            <li>
              <span>01</span>
              <div>
                <h3>Comprueba el formato</h3>
                <p>CSV codificado en UTF-8, con un máximo de 2 MB y 5.000 filas.</p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <h3>Revisa los datos</h3>
                <p>El servidor valida cada fila y rechaza duplicadas o registros fuera del piloto de San Isidro.</p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <h3>Consulta el resultado</h3>
                <p>Verás cuántas citas se incorporaron y el motivo detallado de cada rechazo si existieran.</p>
              </div>
            </li>
          </ol>

          <details className="columnas-csv mt-4">
            <summary className="cursor-pointer text-xs font-semibold text-teal-800 hover:underline">
              Ver columnas obligatorias del CSV
            </summary>
            <p className="mt-2 text-xs text-slate-600 leading-relaxed font-mono bg-slate-50 p-2.5 rounded border border-slate-200">
              id_cita_externa, paciente_anon_id, sede, especialidad, medico, fecha_hora_cita,
              fecha_registro_cita, tipo_paciente, canal_origen, inasistencias_previas,
              reprogramaciones_prev, asistencias_previas, estado_actual
            </p>
          </details>
        </aside>
      </div>

      {resultado && (
        <section className="tarjeta space-y-5 mt-6">
          <div className="seccion-cabecera border-b border-slate-100 pb-3">
            <h2 className="text-lg font-bold text-slate-900">Resultado de la Importación</h2>
            <p className="text-xs text-slate-500">Resumen de registros procesados por el servidor.</p>
          </div>

          <dl className="grid gap-3 sm:grid-cols-3">
            {resumen.map(([nombre, valor, estilo]) => (
              <div key={nombre} className={`rounded-lg p-4 ${estilo}`}>
                <dt className="text-xs font-semibold uppercase">{nombre}</dt>
                <dd className="mt-1 text-2xl font-bold">{valor}</dd>
              </div>
            ))}
          </dl>

          {resultado.detalle_rechazos.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <caption className="mb-2 text-left text-sm font-semibold text-slate-800">
                  Filas con observaciones o rechazadas ({resultado.detalle_rechazos.length})
                </caption>
                <thead className="bg-slate-100 text-slate-700">
                  <tr>
                    <th className="p-2 text-left">Fila</th>
                    <th className="p-2 text-left">Identificador</th>
                    <th className="p-2 text-left">Motivos</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {resultado.detalle_rechazos.map((rechazo) => (
                    <tr key={rechazo.fila}>
                      <td className="p-2 font-mono">{rechazo.fila}</td>
                      <td className="p-2 font-mono font-medium">{rechazo.id_cita_externa || "—"}</td>
                      <td className="p-2 text-rose-700">{rechazo.motivos.join("; ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="pt-3 border-t border-slate-100 flex gap-3">
            <Link className="boton" to="/citas">
              Ver citas en la bandeja asistencial →
            </Link>
          </div>
        </section>
      )}
    </>
  );
}
