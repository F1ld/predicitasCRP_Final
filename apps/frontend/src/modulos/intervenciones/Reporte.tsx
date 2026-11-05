import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "../../nucleo/api/cliente";
import { useConsulta } from "../../nucleo/api/useConsulta";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import NivelRiesgoBadge from "../../nucleo/componentes/NivelRiesgoBadge";
import RotuloSimulado from "../../nucleo/componentes/RotuloSimulado";
import { descargarReporte } from "./descargas";
import { mensajeError } from "./errores";
import { rotulo } from "./presentacion";
import { CANALES, ESPECIALIDADES, NIVELES, type Rep02Out } from "./tipos";
import "./reporte.css";

const FILTROS = ["desde", "hasta", "canal_contacto", "nivel_riesgo", "especialidad"] as const;
const formatearPorcentaje = (valor: number) => `${new Intl.NumberFormat("es-PE", { maximumFractionDigits: 1 }).format(valor * 100)} %`;

function Barras({ titulo, valores }: { titulo: string; valores: [string, number][] }) {
  const maximo = Math.max(1, ...valores.map(([, cantidad]) => cantidad));
  return <section className="tarjeta m05-grafico" aria-label={titulo}>
    <h2>{titulo}</h2>
    {valores.length === 0 ? <p className="m05-ayuda">Sin registros para esta distribución.</p> : <ul>
      {valores.map(([nombre, cantidad]) => <li key={nombre}>
        <div className="m05-barra-etiqueta"><span>{nombre}</span><strong>{cantidad}</strong></div>
        <div className="m05-barra-pista" aria-hidden="true"><span style={{ width: `${cantidad / maximo * 100}%` }} /></div>
      </li>)}
    </ul>}
  </section>;
}

function distribuir(datos: Rep02Out, campo: "canal_contacto" | "respuesta_paciente"): [string, number][] {
  const grupos = new Map<string, number>();
  datos.por_canal.forEach((fila) => {
    const clave = fila[campo] === null ? "Sin respuesta registrada" : rotulo(fila[campo]);
    grupos.set(clave, (grupos.get(clave) ?? 0) + fila.cantidad);
  });
  return [...grupos];
}

// REP-02, RF-003: el técnico no consulta ni exporta el reporte, incluso al montar la vista directamente.
export default function Reporte() {
  const { tieneRol } = useAuth();
  return tieneRol("ADMINISTRADOR", "RECEPCION") ? <ReportePermitido /> : <Mensaje>No tienes permiso para consultar el reporte de intervenciones.</Mensaje>;
}

/** M05-V04 / REP-02, RF-056, RN16 y RNF-016: filtros del contrato, cuatro estados,
 * métricas con rótulo de simulación, barras con valores textuales y hoja de impresión.
 */
function ReportePermitido() {
  const [busqueda, setBusqueda] = useSearchParams();
  const [errorFiltro, setErrorFiltro] = useState("");
  const [errorDescarga, setErrorDescarga] = useState("");
  const [camposDescarga, setCamposDescarga] = useState<Record<string, string>>({});
  const [descargando, setDescargando] = useState<"csv" | "xlsx" | null>(null);
  const filtros = new URLSearchParams();
  FILTROS.forEach((nombre) => { const valor = busqueda.get(nombre); if (valor) filtros.set(nombre, valor); });
  const { datos, error, cargando, reintentar } = useConsulta<Rep02Out>(`/reportes/rep-02?${filtros}`);

  function aplicar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const formulario = new FormData(evento.currentTarget);
    const siguientes = new URLSearchParams();
    FILTROS.forEach((nombre) => { const valor = String(formulario.get(nombre) ?? ""); if (valor) siguientes.set(nombre, valor); });
    if (siguientes.get("desde") && siguientes.get("hasta") && siguientes.get("desde")! > siguientes.get("hasta")!) {
      setErrorFiltro("La fecha inicial no puede ser posterior a la fecha final.");
      return;
    }
    setErrorFiltro("");
    setErrorDescarga("");
    setCamposDescarga({});
    setBusqueda(siguientes);
  }

  async function exportar(formato: "csv" | "xlsx") {
    setDescargando(formato);
    setErrorDescarga("");
    setCamposDescarga({});
    try { await descargarReporte(filtros, formato); }
    catch (fallo: unknown) {
      setErrorDescarga(mensajeError(fallo));
      if (fallo instanceof ApiError) setCamposDescarga(fallo.campos);
    } finally { setDescargando(null); }
  }

  const sinFilas = !datos || datos.filas.length === 0;
  return <div className="m05-reporte">
    <div className="pagina-titulo"><div><p className="sobretitulo">REP-02 · SEGUIMIENTO DE INTERVENCIONES</p><h1>Efectividad de intervenciones</h1><p>Consulta las comunicaciones registradas y las respuestas de los pacientes.</p></div><Link className="boton-secundario m05-no-imprimir" to="/intervenciones">Ver intervenciones</Link></div>
    <form key={busqueda.toString()} className="tarjeta m05-formulario m05-no-imprimir" onSubmit={aplicar}>
      <h2>Filtrar el reporte</h2><p className="m05-ayuda">Fechas inclusivas, en hora de Lima.</p>
      <fieldset disabled={cargando || descargando !== null} className="m05-reporte-filtros"><legend className="sr-only">Filtros del reporte</legend>
        <div><label htmlFor="rep-desde">Desde</label><input type="date" id="rep-desde" name="desde" defaultValue={busqueda.get("desde") || ""} /></div>
        <div><label htmlFor="rep-hasta">Hasta</label><input type="date" id="rep-hasta" name="hasta" defaultValue={busqueda.get("hasta") || ""} /></div>
        <div><label htmlFor="rep-canal">Canal de contacto</label><select id="rep-canal" name="canal_contacto" defaultValue={busqueda.get("canal_contacto") || ""}><option value="">Todos</option>{CANALES.map((valor) => <option key={valor} value={valor}>{rotulo(valor)}</option>)}</select></div>
        <div><label htmlFor="rep-riesgo">Nivel de riesgo</label><select id="rep-riesgo" name="nivel_riesgo" defaultValue={busqueda.get("nivel_riesgo") || ""}><option value="">Todos</option>{NIVELES.map((valor) => <option key={valor} value={valor}>{rotulo(valor)}</option>)}</select></div>
        <div><label htmlFor="rep-especialidad">Especialidad</label><select id="rep-especialidad" name="especialidad" defaultValue={busqueda.get("especialidad") || ""}><option value="">Todas</option>{ESPECIALIDADES.map((valor) => <option key={valor} value={valor}>{rotulo(valor)}</option>)}</select></div>
        <div className="m05-acciones"><button className="boton" type="submit">Aplicar filtros</button><button className="boton-secundario" type="button" onClick={(evento) => { evento.currentTarget.form?.reset(); setErrorFiltro(""); setErrorDescarga(""); setCamposDescarga({}); setBusqueda({}); }}>Limpiar</button></div>
      </fieldset>
    </form>
    {errorFiltro && <Mensaje>{errorFiltro}</Mensaje>}
    {cargando ? <Cargando texto="Cargando reporte…" /> : error ? <div className="space-y-3"><Mensaje>{error}</Mensaje><button className="boton-secundario" onClick={reintentar}>Reintentar</button></div> : <>
      <div className="m05-acciones m05-no-imprimir m05-reporte-exportaciones" aria-label="Exportar reporte">
        <button className="boton-secundario" disabled={sinFilas || descargando !== null} onClick={() => { void exportar("csv"); }}>{descargando === "csv" ? "Descargando CSV…" : "Exportar CSV"}</button>
        <button className="boton-secundario" disabled={sinFilas || descargando !== null} onClick={() => { void exportar("xlsx"); }}>{descargando === "xlsx" ? "Descargando Excel…" : "Exportar Excel"}</button>
        <button className="boton-secundario" disabled={sinFilas || descargando !== null} onClick={() => window.print()}>Imprimir / Guardar PDF</button>
      </div>
      {errorDescarga && <Mensaje>{errorDescarga}{Object.entries(camposDescarga).length > 0 && <ul>{Object.entries(camposDescarga).map(([campo, motivo]) => <li key={campo}>{campo}: {motivo}</li>)}</ul>}</Mensaje>}
      {sinFilas ? <div className="tarjeta estado-vacio"><h2>No hay intervenciones con esos filtros.</h2><p>Amplía las fechas o utiliza «Limpiar» para consultar más registros.</p></div> : datos && <>
        {datos.resultado_simulado && <RotuloSimulado />}
        <dl className="m05-indicadores" aria-label="Indicadores de intervenciones">
          <div><dt>Enviadas</dt><dd>{datos.resumen.enviadas}</dd></div><div><dt>Entregadas</dt><dd>{datos.resumen.entregadas}</dd></div><div><dt>Respondidas</dt><dd>{datos.resumen.respondidas}</dd></div><div><dt>Confirmaciones</dt><dd>{datos.resumen.confirmaciones}</dd></div><div><dt>Liberaciones</dt><dd>{datos.resumen.liberaciones}</dd></div><div><dt>Tasa de respuesta</dt><dd>{formatearPorcentaje(datos.resumen.tasa_respuesta)}</dd></div>
        </dl>
        <div className="m05-reporte-graficos"><Barras titulo="Intervenciones por canal" valores={distribuir(datos, "canal_contacto")} /><Barras titulo="Intervenciones por respuesta" valores={distribuir(datos, "respuesta_paciente")} /></div>
        <p className="m05-ayuda">El riesgo estima inasistencia para orientar el acompañamiento; no es una decisión clínica.</p>
        <div className="tabla-contenedor" role="region" aria-label="Filas del reporte de intervenciones" tabIndex={0}><table className="m05-tabla m05-reporte-tabla"><caption>Intervenciones que cumplen los filtros aplicados</caption><thead><tr><th scope="col">Intervención</th><th scope="col">Cita</th><th scope="col">Especialidad</th><th scope="col">Riesgo</th><th scope="col">Canal</th><th scope="col">Estado</th><th scope="col">Respuesta</th><th scope="col">Tiempo de respuesta</th><th scope="col">Cupo liberado</th></tr></thead><tbody>
          {datos.filas.map((fila) => <tr key={fila.id_intervencion}><td><Link to={`/intervenciones/${fila.id_intervencion}`}>#{fila.id_intervencion}</Link></td><td>{fila.id_cita_externa}</td><td>{rotulo(fila.especialidad)}</td><td>{fila.nivel_riesgo ? <NivelRiesgoBadge nivel={fila.nivel_riesgo} /> : "Sin predicción"}</td><td>{rotulo(fila.canal_contacto)}</td><td>{rotulo(fila.estado_intervencion)}</td><td>{fila.respuesta_paciente ? rotulo(fila.respuesta_paciente) : "Sin respuesta registrada"}</td><td>{fila.tiempo_respuesta_minutos === null ? "Sin respuesta registrada" : `${fila.tiempo_respuesta_minutos} min`}</td><td>{fila.cupo_liberado ? "Sí" : "No"}</td></tr>)}
        </tbody></table></div>
      </>}
    </>}
  </div>;
}
