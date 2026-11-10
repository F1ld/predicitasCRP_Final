import { etiqueta } from "../../nucleo/formato/formato";
import RotuloSimulado from "../../nucleo/componentes/RotuloSimulado";
import { numeroPanel, porcentajePanel } from "./formato";
import { ESTADOS_CITA, ESTADOS_INTERVENCION, ETIQUETAS, RIESGOS, type PanelResumenOut } from "./tipos";

export function TarjetasPanel({ datos }: { datos: PanelResumenOut }) {
  return <section className="panel-tarjetas" aria-label="Indicadores de la jornada">
    <article className="tarjeta panel-indicador"><h2>Citas de la jornada</h2><p className="panel-cifra">{numeroPanel(datos.citas.total)}</p><p>Programadas para la fecha seleccionada</p></article>
    <article className="tarjeta panel-indicador"><h2>Riesgo de inasistencia</h2><div className="panel-riesgos"><p><span className="panel-riesgo panel-riesgo-alto">Alto</span><strong>{numeroPanel(datos.citas.por_riesgo.ALTO)}</strong></p><p><span className="panel-riesgo panel-riesgo-medio">Medio</span><strong>{numeroPanel(datos.citas.por_riesgo.MEDIO)}</strong></p></div><RotuloSimulado /></article>
    <article className="tarjeta panel-indicador"><h2>Cupos disponibles</h2><p className="panel-cifra">{numeroPanel(datos.cupos.disponibles_para_ofrecer)}</p><p>Con horario futuro y disponibles para ofrecer</p></article>
    <article className="tarjeta panel-indicador"><h2>Recuperación de cupos</h2>{datos.cupos.tasa_recuperacion_pct === null ? <p className="panel-sin-base">Sin cupos liberados</p> : <><p className="panel-cifra">{porcentajePanel(datos.cupos.tasa_recuperacion_pct)}</p><p>{numeroPanel(datos.cupos.reasignados_confirmados)} de {numeroPanel(datos.cupos.total_liberados)} cupos recuperados</p></>}</article>
  </section>;
}
export function DesglosesPanel({ datos }: { datos: PanelResumenOut }) {
  const bloques = [
    { titulo: "Citas por estado", claves: ESTADOS_CITA, valores: datos.citas.por_estado },
    { titulo: "Distribución de riesgo", claves: RIESGOS, valores: datos.citas.por_riesgo },
    { titulo: "Intervenciones por estado", claves: ESTADOS_INTERVENCION, valores: datos.intervenciones.por_estado },
  ];
  return <section className="panel-desgloses" aria-label="Desgloses de la jornada">{bloques.map(b => <section key={b.titulo} className="tarjeta" aria-label={b.titulo}>
    <h2>{b.titulo}</h2>{b.titulo === "Intervenciones por estado" && <p className="panel-ayuda">{numeroPanel(datos.intervenciones.total)} intervenciones · {numeroPanel(datos.intervenciones.citas_con_intervencion)} citas distintas</p>}
    <dl>{b.claves.map(clave => <div key={clave}><dt>{ETIQUETAS[clave] || etiqueta(clave)}</dt><dd>{numeroPanel((b.valores as Record<string, number>)[clave])}</dd></div>)}</dl>
    {b.titulo === "Distribución de riesgo" && <p className="panel-ayuda">Último riesgo registrado de toda la jornada; no equivale a pendientes de intervención.</p>}
    {b.titulo === "Intervenciones por estado" && <p className="panel-ayuda">Estados actuales; no representan envíos históricos acumulados.</p>}
  </section>)}</section>;
}
