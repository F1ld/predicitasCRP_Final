import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { useConsulta } from "../../nucleo/api/useConsulta";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta } from "../../nucleo/formato/formato";
import { resolverRetorno } from "../../nucleo/navegacion/retorno";
import { fechaPanel, numeroPanel, porcentajePanel } from "./formato";
import {
  esReporteDiario, leerFiltrosReporte, parametrosReporte, RIESGOS, validarFiltrosReporte,
  type FiltrosReporte, type ReporteDiarioOut,
} from "./contratoReporteDiario";
import { ESPECIALIDADES } from "./tipos";
import "./panel.css";
import "./reporte-diario.css";

export default function ReporteDiario() {
  const { state } = useLocation();
  const [parametros, setParametros] = useSearchParams();
  const filtros = leerFiltrosReporte(parametros);
  const error = validarFiltrosReporte(filtros);
  const actual = parametros.toString();
  const normalizada = parametrosReporte(filtros).toString();
  useEffect(() => {
    if (!error && actual !== normalizada) setParametros(normalizada, { replace: true, state });
  }, [actual, error, normalizada, setParametros, state]);

  return <div className="panel-vista reporte-diario-vista">
    <div className="pagina-titulo">
      <div><p className="sobretitulo">RECEPCIÓN · JORNADA OPERATIVA</p><h1>Reporte diario</h1></div>
      <Link className="boton-secundario" to={resolverRetorno(state, "/panel", ["/panel"])}>Volver al panel operativo</Link>
    </div>
    <Formulario key={normalizada} filtros={filtros} aplicar={siguientes => setParametros(parametrosReporte(siguientes), { state })} />
    {error ? <Mensaje>{error}</Mensaje>
      : actual !== normalizada ? <Cargando texto="Preparando el reporte…" />
        : <Contenido filtros={filtros} consulta={normalizada} />}
  </div>;
}

function Formulario({ filtros, aplicar }: { filtros: FiltrosReporte; aplicar: (filtros: FiltrosReporte) => void }) {
  const [error, setError] = useState("");
  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const datos = new FormData(evento.currentTarget);
    const siguientes = {
      fecha: String(datos.get("fecha") ?? ""),
      especialidad: String(datos.get("especialidad") ?? ""),
      nivel_riesgo: String(datos.get("nivel_riesgo") ?? ""),
    };
    const mensaje = validarFiltrosReporte(siguientes);
    setError(mensaje);
    if (!mensaje) aplicar(siguientes);
  }
  return <form className="tarjeta panel-filtros reporte-diario-filtros" aria-label="Filtrar reporte diario" onSubmit={enviar} noValidate>
    <div><label htmlFor="rep01-fecha">Fecha de la jornada</label><input id="rep01-fecha" type="date" name="fecha" defaultValue={filtros.fecha} required /></div>
    <div><label htmlFor="rep01-especialidad">Especialidad</label><select id="rep01-especialidad" name="especialidad" defaultValue={filtros.especialidad}>
      <option value="">Todas las especialidades</option>
      {ESPECIALIDADES.map(valor => <option key={valor} value={valor}>{etiqueta(valor)}</option>)}
    </select></div>
    <div><label htmlFor="rep01-riesgo">Nivel de riesgo</label><select id="rep01-riesgo" name="nivel_riesgo" defaultValue={filtros.nivel_riesgo}>
      <option value="">Todos los riesgos</option>
      {RIESGOS.map(valor => <option key={valor} value={valor}>{valor}</option>)}
    </select></div>
    <div className="panel-acciones"><button className="boton" type="submit">Aplicar filtros</button></div>
    {error && <p className="panel-error" role="alert">{error}</p>}
  </form>;
}

function Contenido({ filtros, consulta }: { filtros: FiltrosReporte; consulta: string }) {
  const { datos, cargando, error, reintentar } = useConsulta<unknown>(`/reportes/rep-01?${consulta}`);
  return <section className="reporte-diario-resultados" aria-label="Resultados del reporte" aria-busy={cargando}>
    <p><strong>{fechaPanel(filtros.fecha)}</strong> · Lima · {filtros.especialidad ? etiqueta(filtros.especialidad) : "Todas las especialidades"} · {filtros.nivel_riesgo || "Todos los riesgos"}</p>
    {cargando ? <Cargando texto="Cargando reporte diario…" />
      : esReporteDiario(datos, filtros) ? <Tablas reporte={datos} />
        : <div className="panel-error-bloque">
          <Mensaje>{error || "El servidor no devolvió un reporte válido para estos filtros."}</Mensaje>
          <button type="button" className="boton-secundario" onClick={reintentar}>Reintentar reporte</button>
        </div>}
  </section>;
}

function Tablas({ reporte }: { reporte: ReporteDiarioOut }) {
  return <>
    <p role="status"><strong>Total de citas: {numeroPanel(reporte.total)}</strong>{reporte.total === 0 && " · No hay citas para los filtros aplicados."}</p>
    {reporte.grupos.map(grupo => {
      const nombre = `${etiqueta(grupo.especialidad)} · ${etiqueta(grupo.franja_horaria)}`;
      return <div key={nombre} className="tarjeta reporte-diario-tabla" role="region" aria-label={nombre} tabIndex={0}>
        <table>
          <caption>{nombre} · Subtotal: {numeroPanel(grupo.subtotal)}</caption>
          <thead><tr>{["Hora", "ID externo", "Especialidad", "Médico", "Días de antelación", "Probabilidad de inasistencia", "Riesgo", "Estado de intervención", "Respuesta del paciente"].map(columna =>
            <th scope="col" key={columna}>{columna}</th>)}</tr></thead>
          <tbody>{grupo.filas.map(fila => <tr key={fila.id_cita_externa}>
            <td>{fila.hora.slice(0, 5)}</td><th scope="row">{fila.id_cita_externa}</th>
            <td>{etiqueta(fila.especialidad)}</td><td>{fila.medico}</td><td>{fila.antelacion_dias}</td>
            <td>{fila.probabilidad_no_show === null ? "—" : porcentajePanel(fila.probabilidad_no_show * 100)}</td>
            <td>{fila.nivel_riesgo ?? "Sin evaluación"}</td>
            <td>{fila.estado_intervencion ? etiqueta(fila.estado_intervencion) : "Sin intervención"}</td>
            <td>{fila.estado_intervencion === null ? "—" : fila.respuesta_paciente === null || fila.respuesta_paciente === "SIN_RESPUESTA" ? "Sin respuesta" : etiqueta(fila.respuesta_paciente)}</td>
          </tr>)}</tbody>
        </table>
      </div>;
    })}
  </>;
}
