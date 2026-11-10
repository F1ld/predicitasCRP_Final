import { Link } from "react-router-dom";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta } from "../../nucleo/formato/formato";
import { fechaHoraPanel, horaPanel, numeroPanel, porcentajePanel } from "./formato";
import { CATEGORIAS, ETIQUETAS, TIPOS, type ItemPendiente, type PanelPendientesOut, type PanelResumenOut, type TipoPendiente } from "./tipos";

interface Props { tipo: TipoPendiente; resumen: PanelResumenOut | null; datos: PanelPendientesOut | null; cargando: boolean; error: string; volver: string; seleccionar: (tipo: TipoPendiente) => void; paginar: (offset: number) => void; reintentar: () => void }
function Fila({ item, volver }: { item: ItemPendiente; volver: string }) {
  if (item.tipo === "OFERTAS_EN_CURSO") return <tr><th scope="row">#{item.id_cupo_liberado}</th><td>{horaPanel(item.fecha_hora_cupo)}</td><td>{etiqueta(item.especialidad)}</td><td>{item.medico}</td><td>{ETIQUETAS[item.estado_cupo]}</td><td><Link className="enlace-detalle" to={`/cupos/${item.id_cupo_liberado}`} state={{ volver }}>Ver cupo</Link></td></tr>;
  if (item.tipo === "INTERVENCIONES_SIN_RESPUESTA") return <tr><td>{horaPanel(item.fecha_hora_cita)}</td><th scope="row">{item.id_cita_externa}</th><td>{etiqueta(item.especialidad)}</td><td>{ETIQUETAS[item.canal_contacto]}</td><td>{ETIQUETAS[item.estado_intervencion]}</td><td>{fechaHoraPanel(item.fecha_hora_envio)}</td><td><Link className="enlace-detalle" to={`/intervenciones/${item.id_intervencion}`} state={{ volver }}>Ver seguimiento</Link></td></tr>;
  return <tr><td>{horaPanel(item.fecha_hora_cita)}</td><th scope="row">{item.id_cita_externa}</th><td>{etiqueta(item.especialidad)}</td><td>{item.medico}</td><td><span className={`panel-riesgo panel-riesgo-${item.nivel_riesgo.toLowerCase()}`}>{ETIQUETAS[item.nivel_riesgo]}</span><span className="panel-probabilidad">{porcentajePanel(item.probabilidad_no_show * 100)}</span></td><td><Link className="enlace-detalle" to={`/citas/${item.id_cita}`} state={{ volver }}>Ver cita</Link></td></tr>;
}
const columnas: Record<TipoPendiente, string[]> = {
  CITAS_SIN_INTERVENCION: ["Hora", "Cita", "Especialidad", "Médico", "Riesgo de inasistencia", "Acción"],
  INTERVENCIONES_SIN_RESPUESTA: ["Hora de cita", "Cita", "Especialidad", "Canal", "Estado", "Envío registrado", "Acción"],
  OFERTAS_EN_CURSO: ["Cupo", "Hora", "Especialidad", "Médico", "Estado", "Acción"],
};
export default function PendientesPanel({ tipo, resumen, datos, cargando, error, volver, seleccionar, paginar, reintentar }: Props) {
  const categoria = CATEGORIAS[tipo];
  const diferente = datos && resumen && datos.total !== resumen.pendientes[categoria.contador];
  return <section className="panel-pendientes" aria-labelledby="panel-pendientes-titulo">
    <div className="panel-seccion"><div><p className="sobretitulo">PRÓXIMAS TAREAS</p><h2 id="panel-pendientes-titulo">Pendientes de atención</h2></div></div>
    <div className="panel-categorias" role="group" aria-label="Categoría de pendientes">{TIPOS.map(t => <button key={t} type="button" aria-pressed={tipo === t} onClick={() => seleccionar(t)}>{CATEGORIAS[t].titulo}<span>{resumen ? numeroPanel(resumen.pendientes[CATEGORIAS[t].contador]) : "—"}</span></button>)}</div>
    <div className="tarjeta panel-listado"><h3>{categoria.titulo}</h3><p className="panel-ayuda">{categoria.ayuda}</p>
      {cargando ? <Cargando texto="Cargando pendientes…" /> : error ? <div className="panel-error-bloque"><Mensaje>{error}</Mensaje><button type="button" className="boton-secundario" onClick={reintentar}>Reintentar pendientes</button></div> : datos && <>
        <div className="panel-resultados"><p><strong>{numeroPanel(datos.total)}</strong> pendientes</p><p className="panel-ayuda">Listado consultado a las {horaPanel(datos.generado_en)} · Lima</p></div>
        {diferente && <Mensaje tipo="info">Los datos pueden haber cambiado. Actualiza el panel para consultar el resumen nuevamente.</Mensaje>}
        {datos.total === 0 ? <p className="panel-vacio" role="status">{categoria.vacio}</p> : datos.items.length === 0 ? <div className="panel-vacio"><p role="status">Esta página ya no tiene resultados.</p><button type="button" className="boton-secundario" onClick={() => paginar(0)}>Ir a la primera página</button></div> : <>
          <div className="panel-tabla" role="region" aria-label={categoria.titulo} tabIndex={0}><table><caption className="sr-only">{categoria.titulo}, en el orden de atención propuesto por el servidor</caption><thead><tr>{columnas[tipo].map(c => <th scope="col" key={c}>{c}</th>)}</tr></thead><tbody>{datos.items.map(item => <Fila key={item.tipo === "OFERTAS_EN_CURSO" ? item.id_cupo_liberado : item.tipo === "INTERVENCIONES_SIN_RESPUESTA" ? item.id_intervencion : item.id_cita} item={item} volver={volver} />)}</tbody></table></div>
          <div className="panel-paginacion"><p>Mostrando {numeroPanel(datos.desplazamiento + 1)}–{numeroPanel(datos.desplazamiento + datos.items.length)} de {numeroPanel(datos.total)}</p><div className="panel-acciones"><button type="button" className="boton-secundario" disabled={datos.desplazamiento === 0} onClick={() => paginar(Math.max(0, datos.desplazamiento - datos.limite))}>Anterior</button><button type="button" className="boton-secundario" disabled={datos.desplazamiento + datos.limite >= datos.total} onClick={() => paginar(datos.desplazamiento + datos.limite)}>Siguiente</button></div></div>
        </>}
      </>}
    </div>
  </section>;
}
