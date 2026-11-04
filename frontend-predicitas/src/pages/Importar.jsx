import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import Mensaje from "../components/Mensaje";
import Icono from "../components/Icono";

const MAX_BYTES = 2 * 1024 * 1024;

export default function Importar() {
  const [archivo, setArchivo] = useState(null);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState(null);

  function seleccionar(evento) {
    const elegido = evento.target.files?.[0];
    setResultado(null); setArchivo(null); setError("");
    if (!elegido) return;
    if (!/\.csv$/i.test(elegido.name)) { setError("Selecciona un archivo con extensión .csv."); return; }
    if (elegido.size > MAX_BYTES) { setError("El archivo supera los 2 MB permitidos."); return; }
    if (elegido.size === 0) { setError("El archivo está vacío."); return; }
    setArchivo(elegido);
  }

  async function importar(evento) {
    evento.preventDefault();
    if (!archivo || enviando) return;
    const formulario = evento.currentTarget;
    const datos = new FormData();
    datos.append("archivo", archivo);
    setEnviando(true); setError(""); setResultado(null);
    try {
      setResultado(await api("/citas/importar", { metodo: "POST", archivo: datos }));
      setArchivo(null); formulario.reset();
    } catch (fallo) { setError(fallo.message); }
    finally { setEnviando(false); }
  }

  return <>
    <div className="pagina-titulo"><div><p className="sobretitulo">RECEPCIÓN Y CARGA DE PROGRAMACIÓN MÉDICA</p><h1>Importar citas</h1><p>Carga un archivo con la programación de citas médicas que deseas incorporar al seguimiento.</p></div><span className="contexto-horario"><Icono nombre="archivo" />Formato CSV</span></div>
    {error && <Mensaje>{error}</Mensaje>}
    <div className="importacion-layout">
      <section className="tarjeta importacion-principal"><div className="seccion-cabecera"><h2>Selecciona tu archivo</h2><p>Revisa que sea el archivo correcto antes de enviarlo.</p></div>
        <form onSubmit={importar}><fieldset disabled={enviando} className="space-y-5">
          <div className="selector-archivo"><span className="archivo-ilustracion"><Icono nombre="importar" /></span><label htmlFor="archivo">Archivo CSV</label><p>Hasta 2 MB · Máximo 5.000 filas · UTF-8</p><input id="archivo" type="file" accept=".csv,text/csv" onChange={seleccionar} />{archivo && <span className="archivo-seleccionado"><Icono nombre="check" />{archivo.name}</span>}</div>
          <div className="importacion-envio"><p>Las citas válidas se incorporarán automáticamente a la agenda de seguimiento.</p><button className="boton" type="submit" disabled={!archivo || enviando}><Icono nombre="importar" />{enviando ? "Importando…" : "Importar archivo"}</button></div>
        </fieldset></form>
      </section>
      <aside className="importacion-ayuda"><h2>Antes de importar</h2><ol><li><span>01</span><div><h3>Comprueba el formato</h3><p>CSV codificado en UTF-8, con un máximo de 2 MB y 5.000 filas.</p></div></li><li><span>02</span><div><h3>Validación automática</h3><p>El sistema verifica cada cita y descarta las duplicadas o fuera de las especialidades de la sede.</p></div></li><li><span>03</span><div><h3>Consulta el resultado</h3><p>Verás cuántas citas se incorporaron y el motivo detallado de cualquier observación.</p></div></li></ol>
        <details className="columnas-csv"><summary>Ver columnas admitidas</summary><p><strong>Obligatorias:</strong> id_cita_externa, paciente_anon_id, sede, especialidad, medico, fecha_hora_cita, fecha_registro_cita, tipo_paciente, canal_origen.<br /><strong>Historial del paciente (opcionales):</strong> inasistencias_previas, reprogramaciones_prev, asistencias_previas, estado_actual.</p></details>
      </aside>
    </div>
    {resultado && <section className="tarjeta space-y-5"><h2>Resultado de la importación</h2>
      <dl className="grid gap-3 sm:grid-cols-3">{[["Recibidas", resultado.recibidas, "bg-slate-100"], ["Aceptadas", resultado.aceptadas, "bg-emerald-50 text-emerald-800"], ["Rechazadas", resultado.rechazadas, "bg-rose-50 text-rose-800"]].map(([nombre, valor, estilo]) => <div key={nombre} className={`rounded-lg p-4 ${estilo}`}><dt className="text-sm">{nombre}</dt><dd className="mt-1 text-2xl font-bold">{valor}</dd></div>)}</dl>
      {resultado.detalle_rechazos.length > 0 && <div className="overflow-x-auto"><table className="w-full"><caption className="mb-2 text-left text-sm font-semibold">Filas observadas (numeradas desde la primera fila de datos)</caption><thead className="bg-slate-100"><tr><th>Fila</th><th>Identificador</th><th>Motivos</th></tr></thead>
        <tbody className="divide-y divide-slate-100">{resultado.detalle_rechazos.map((rechazo) => <tr key={rechazo.fila}><td>{rechazo.fila}</td><td>{rechazo.id_cita_externa || "—"}</td><td className="min-w-56">{rechazo.motivos.join("; ")}</td></tr>)}</tbody>
      </table></div>}
      <Link className="boton-secundario" to="/citas?desde=">Ver citas importadas</Link>
    </section>}
  </>;
}
