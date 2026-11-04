import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Pagina } from "../../nucleo/api/tipos";
import { useConsulta } from "../../nucleo/api/useConsulta";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import NivelRiesgoBadge from "../../nucleo/componentes/NivelRiesgoBadge";
import RotuloSimulado from "../../nucleo/componentes/RotuloSimulado";
import EstadoBadge from "../../nucleo/componentes/EstadoBadge";
import { etiqueta, formatearFechaHora } from "../../nucleo/formato/formato";
import NuevaIntervencion from "./NuevaIntervencion";
import { idPositivo, rotulo } from "./presentacion";
import { CANALES, ESTADOS, ESPECIALIDADES, RESPUESTAS, type ElegibleOut, type IntervencionOut } from "./tipos";
import "./intervenciones.css";

// M05-V01, RF-003, RF-057, RF-093: Técnico IA consulta solo las intervenciones registradas.
export default function Intervenciones() {
  const { usuario, cargando } = useAuth();
  if (cargando) return <Cargando texto="Verificando sesión…" />;
  if (!usuario) return <Mensaje>No tienes una sesión disponible.</Mensaje>;
  return <Contenido puedeEscribir={usuario.rol === "ADMINISTRADOR" || usuario.rol === "RECEPCION"} />;
}

function Contenido({ puedeEscribir }: { puedeEscribir: boolean }) {
  const [busqueda, setBusqueda] = useSearchParams();
  const [seleccion, setSeleccion] = useState<{ idCita: number; referenciaCita?: string } | null>(null);
  const [creada, setCreada] = useState<IntervencionOut | null>(null);
  const elegibles = puedeEscribir && busqueda.get("pestana") !== "registradas";
  const directo = puedeEscribir ? idPositivo(busqueda.get("id_cita")) : null;
  const activa = seleccion ?? (directo ? { idCita: directo } : null);
  const pestanas = useRef<(HTMLButtonElement | null)[]>([]);
  function cambiarPestana(registradas: boolean) {
    const nuevos = new URLSearchParams();
    if (registradas) nuevos.set("pestana", "registradas");
    setBusqueda(nuevos); setCreada(null);
  }
  function teclado(evento: KeyboardEvent<HTMLButtonElement>, indice: number) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(evento.key)) return;
    evento.preventDefault();
    const siguiente = evento.key === "Home" ? 0 : evento.key === "End" ? 1 : 1 - indice;
    cambiarPestana(siguiente === 1); pestanas.current[siguiente]?.focus();
  }
  function cerrar() {
    setSeleccion(null);
    if (busqueda.has("id_cita")) { const nuevos = new URLSearchParams(busqueda); nuevos.delete("id_cita"); setBusqueda(nuevos, { replace: true }); }
  }
  return <>
    <div className="pagina-titulo"><div><p className="sobretitulo">ACOMPAÑAMIENTO DE CITAS</p><h1>Intervenciones</h1><p>Registra las comunicaciones y da seguimiento a la respuesta del paciente.</p></div>{puedeEscribir && <Link className="boton-secundario" to="/reportes/intervenciones">Ver reporte REP-02</Link>}</div>
    <p className="m05-ayuda">El riesgo de inasistencia orienta el acompañamiento. No representa una decisión clínica ni cambia la prioridad de atención.</p>
    {busqueda.has("id_cita") && !puedeEscribir && <Mensaje tipo="info">Tu rol permite consultar intervenciones. La creación corresponde a Recepción o al Administrador.</Mensaje>}
    {puedeEscribir && busqueda.has("id_cita") && !directo && <Mensaje>El identificador de cita debe ser un entero positivo.</Mensaje>}
    {creada && <Mensaje tipo="exito">Intervención creada correctamente. <Link className="underline" to={`/intervenciones/${creada.id_intervencion}`}>Abrir seguimiento #{creada.id_intervencion}</Link></Mensaje>}
    {puedeEscribir ? <div role="tablist" aria-label="Listas de intervenciones" className="m05-pestanas">
      {["Elegibles", "Registradas"].map((nombre, indice) => <button ref={(elemento) => { pestanas.current[indice] = elemento; }} id={`m05-tab-${indice}`} key={nombre} role="tab" aria-selected={elegibles === (indice === 0)} aria-controls="m05-panel" tabIndex={elegibles === (indice === 0) ? 0 : -1} className="boton-secundario" onClick={() => cambiarPestana(indice === 1)} onKeyDown={(evento) => teclado(evento, indice)}>{nombre}</button>)}
    </div> : <h2>Intervenciones registradas</h2>}
    <div id="m05-panel" role={puedeEscribir ? "tabpanel" : undefined} aria-labelledby={puedeEscribir ? `m05-tab-${elegibles ? 0 : 1}` : undefined}>
      <Listado key={`${elegibles ? "elegibles" : "registradas"}:${creada?.id_intervencion ?? ""}`} elegibles={elegibles} intervenir={(cita) => setSeleccion({ idCita: cita.id_cita, referenciaCita: cita.id_cita_externa })} />
    </div>
    {activa && puedeEscribir && <NuevaIntervencion {...activa} cerrar={cerrar} completado={(datos) => { cerrar(); setCreada(datos); }} />}
  </>;
}

function Listado({ elegibles, intervenir }: { elegibles: boolean; intervenir: (cita: ElegibleOut) => void }) {
  const [busqueda, setBusqueda] = useSearchParams();
  const [errorFechas, setErrorFechas] = useState("");
  const valorLimite = Number(busqueda.get("limite") ?? 50);
  const limite = Number.isSafeInteger(valorLimite) && valorLimite >= 1 && valorLimite <= 200 ? valorLimite : 50;
  const valorDesplazamiento = Number(busqueda.get("desplazamiento") ?? 0);
  const desplazamiento = Number.isSafeInteger(valorDesplazamiento) && valorDesplazamiento >= 0 ? valorDesplazamiento : 0;
  const parametros = new URLSearchParams({ limite: String(limite), desplazamiento: String(desplazamiento) });
  const campos = elegibles ? ["desde", "hasta", "especialidad", "nivel_riesgo"] : ["desde", "hasta", "estado_intervencion", "canal_contacto", "respuesta_paciente", "id_cita"];
  campos.forEach((campo) => { const valor = busqueda.get(campo); if (valor && (campo !== "id_cita" || idPositivo(valor))) parametros.set(campo, valor); });
  const { datos, cargando, error, reintentar } = useConsulta<any>(`${elegibles ? "/intervenciones/elegibles" : "/intervenciones"}?${parametros}`);
  const itemsLista = Array.isArray(datos) ? datos : (datos?.items ?? datos?.historial_intervenciones ?? datos?.citas_sugeridas ?? []);
  const totalRegistros = typeof datos?.total === "number" ? datos.total : (typeof datos?.total_intervenciones === "number" ? datos.total_intervenciones : itemsLista.length);
  function aplicar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault(); const valores = new FormData(evento.currentTarget);
    const desde = String(valores.get("desde") ?? ""); const hasta = String(valores.get("hasta") ?? "");
    if (desde && hasta && desde > hasta) { setErrorFechas("La fecha inicial no puede ser posterior a la final."); return; }
    setErrorFechas("");
    const nuevos = new URLSearchParams(); if (!elegibles) nuevos.set("pestana", "registradas");
    [...campos, "limite"].forEach((campo) => { const valor = String(valores.get(campo) ?? "").trim(); if (valor) nuevos.set(campo, valor); }); setBusqueda(nuevos);
  }
  function pagina(desplazamientoNuevo: number) { const nuevos = new URLSearchParams(busqueda); nuevos.set("desplazamiento", String(desplazamientoNuevo)); setBusqueda(nuevos); }
  return <>
    <form key={`${elegibles}:${busqueda}`} className="tarjeta m05-filtros" onSubmit={aplicar}>
      <h2>{elegibles ? "Buscar citas elegibles" : "Buscar intervenciones registradas"}</h2>
      <div className="m05-grid">
        <div><label htmlFor="m05-desde">Desde</label><input id="m05-desde" type="date" name="desde" defaultValue={busqueda.get("desde") ?? ""} /></div>
        <div><label htmlFor="m05-hasta">Hasta</label><input id="m05-hasta" type="date" name="hasta" defaultValue={busqueda.get("hasta") ?? ""} /></div>
        {elegibles ? <><div><label htmlFor="m05-especialidad">Especialidad</label><select id="m05-especialidad" name="especialidad" defaultValue={busqueda.get("especialidad") ?? ""}><option value="">Todas las especialidades</option>{ESPECIALIDADES.map((valor) => <option key={valor} value={valor}>{etiqueta(valor)}</option>)}</select></div>
          <div><label htmlFor="m05-riesgo">Nivel de riesgo</label><select id="m05-riesgo" name="nivel_riesgo" defaultValue={busqueda.get("nivel_riesgo") ?? ""}><option value="">Alto y medio</option><option value="ALTO">Alto</option><option value="MEDIO">Medio</option></select></div></> : <>
          <div><label htmlFor="m05-estado">Estado</label><select id="m05-estado" name="estado_intervencion" defaultValue={busqueda.get("estado_intervencion") ?? ""}><option value="">Todos los estados</option>{ESTADOS.map((valor) => <option key={valor} value={valor}>{rotulo(valor)}</option>)}</select></div>
          <div><label htmlFor="m05-canal">Canal</label><select id="m05-canal" name="canal_contacto" defaultValue={busqueda.get("canal_contacto") ?? ""}><option value="">Todos los canales</option>{CANALES.map((valor) => <option key={valor} value={valor}>{rotulo(valor)}</option>)}</select></div>
          <div><label htmlFor="m05-respuesta">Respuesta</label><select id="m05-respuesta" name="respuesta_paciente" defaultValue={busqueda.get("respuesta_paciente") ?? ""}><option value="">Todas las respuestas</option>{RESPUESTAS.map((valor) => <option key={valor} value={valor}>{rotulo(valor)}</option>)}</select></div>
          <div><label htmlFor="m05-id-cita">ID de cita</label><input id="m05-id-cita" name="id_cita" type="number" min="1" step="1" defaultValue={busqueda.get("id_cita") ?? ""} /></div>
        </>}
        <div><label htmlFor="m05-limite">Por página</label><select id="m05-limite" name="limite" defaultValue={limite}>{Array.from(new Set([10, 20, 50, 100, 200, limite])).sort((a, b) => a - b).map((valor) => <option key={valor} value={valor}>{valor}</option>)}</select></div>
      </div>
      <Mensaje>{errorFechas}</Mensaje>
      <div className="m05-acciones"><button className="boton" type="submit">Aplicar filtros</button><button className="boton-secundario" type="button" onClick={() => { setErrorFechas(""); setBusqueda(elegibles ? {} : { pestana: "registradas" }); }}>Limpiar</button></div>
      {elegibles && <p className="m05-ayuda mt-3">Sin fechas se consultan hoy y los próximos siete días, según la API. La elegibilidad y el orden por riesgo los determina el servidor.</p>}
    </form>
    {cargando ? <Cargando texto={elegibles ? "Cargando citas elegibles…" : "Cargando intervenciones…"} /> : error || !datos ? <><Mensaje>{error || "El servidor no devolvió la lista solicitada."}</Mensaje><button className="boton-secundario mt-3" onClick={reintentar}>Reintentar</button></>
      : <div className="m05-contenido"><div className="resultados-cabecera"><h2>{elegibles ? "Citas elegibles" : "Intervenciones encontradas"} <span className="contador-citas">{totalRegistros}</span></h2></div>
        {!itemsLista.length ? <div className="tarjeta estado-vacio"><p>{elegibles ? "No hay citas elegibles con esos filtros." : "No hay intervenciones registradas con esos filtros."}</p><span>Prueba otras fechas o utiliza «Limpiar».</span></div>
          : elegibles ? <Elegibles items={itemsLista as ElegibleOut[]} intervenir={intervenir} /> : <Registradas items={itemsLista as IntervencionOut[]} />}
        <div className="paginacion"><p>Página {Math.floor(desplazamiento / limite) + 1} de {Math.max(1, Math.ceil(totalRegistros / limite))} · {totalRegistros} registros</p><div className="m05-acciones"><button className="boton-secundario" disabled={desplazamiento === 0} onClick={() => pagina(Math.max(0, desplazamiento - limite))}>Anterior</button><button className="boton-secundario" disabled={desplazamiento + limite >= totalRegistros} onClick={() => pagina(desplazamiento + limite)}>Siguiente</button></div></div>
      </div>}
  </>;
}
function Elegibles({ items, intervenir }: { items: ElegibleOut[]; intervenir: (cita: ElegibleOut) => void }) {
  return <div className="tabla-contenedor" role="region" aria-label="Citas elegibles; tabla con desplazamiento horizontal" tabIndex={0}><table className="m05-tabla"><caption className="sr-only">Citas elegibles para intervención</caption><thead><tr><th scope="col">Cita y paciente</th><th scope="col">Atención programada</th><th scope="col">Riesgo de inasistencia</th><th scope="col">Acciones</th></tr></thead><tbody>{items.map((cita) => <tr key={cita.id_cita}>
    <th scope="row">{cita.id_cita_externa}<small>{cita.paciente_anon_id}</small><small>Intentos previos: {cita.intervenciones_previas}</small></th>
    <td>{etiqueta(cita.especialidad)}<small>{cita.medico}</small><small>{formatearFechaHora(cita.fecha_hora_cita)}</small><EstadoBadge estado={cita.estado_actual} /></td>
    <td><NivelRiesgoBadge nivel={cita.riesgo.nivel_riesgo} /><small>Probabilidad: {new Intl.NumberFormat("es-PE", { style: "percent", maximumFractionDigits: 1 }).format(cita.riesgo.probabilidad_no_show)}</small>{cita.riesgo.resultado_simulado && <RotuloSimulado />}</td>
    <td><div className="m05-acciones"><button className="boton" aria-label={`Intervenir en ${cita.id_cita_externa}`} onClick={() => intervenir(cita)}>Intervenir</button><Link className="boton-secundario" to={`/citas/${cita.id_cita}`}>Ir a la cita</Link></div></td>
  </tr>)}</tbody></table></div>;
}
function Registradas({ items }: { items: IntervencionOut[] }) {
  return <div className="tabla-contenedor" role="region" aria-label="Intervenciones registradas; tabla con desplazamiento horizontal" tabIndex={0}><table className="m05-tabla"><caption className="sr-only">Intervenciones registradas</caption><thead><tr><th scope="col">Intervención y cita</th><th scope="col">Canal y fecha</th><th scope="col">Estado y respuesta</th><th scope="col">Acciones</th></tr></thead><tbody>{items.map((item) => <tr key={item.id_intervencion}>
    <th scope="row">#{item.id_intervencion}<small>{item.id_cita_externa}</small></th><td>{rotulo(item.canal_contacto)}<small>{formatearFechaHora(item.fecha_hora_envio)}</small></td>
    <td>{rotulo(item.estado_intervencion)}<small>{rotulo(item.respuesta_paciente)}</small>{item.consentimiento_optout && <small>No desea comunicaciones</small>}</td><td><div className="m05-acciones"><Link className="boton-secundario" to={`/intervenciones/${item.id_intervencion}`}>Ver seguimiento</Link><Link className="boton-secundario" to={`/citas/${item.id_cita}`}>Ir a la cita</Link></div></td>
  </tr>)}</tbody></table></div>;
}
