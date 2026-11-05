import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import type { Pagina } from "../../nucleo/api/tipos";
import { useConsulta } from "../../nucleo/api/useConsulta";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import EstadoBadge from "../../nucleo/componentes/EstadoBadge";
import Icono from "../../nucleo/componentes/Icono";
import Mensaje from "../../nucleo/componentes/Mensaje";
import NivelRiesgoBadge from "../../nucleo/componentes/NivelRiesgoBadge";
import RotuloSimulado from "../../nucleo/componentes/RotuloSimulado";
import { etiqueta, formatearFechaHora } from "../../nucleo/formato/formato";
import type { CatalogosOut, CitaResumenOut } from "./tipos";
import { ROLES_ESCRITURA } from "./transiciones";
import "./citas.css";

const FILTROS = ["desde", "hasta", "especialidad", "medico", "estado", "nivel_riesgo", "con_intervencion", "q"] as const;
const LIMITE = 20;
const INTERVENCIONES = { PENDIENTE: "Pendiente", ENVIADA: "Enviada", ENTREGADA: "Entregada", RESPONDIDA: "Respondida", FALLIDA: "Fallida" };
const RESPUESTAS = { CONFIRMA: "Confirma", SOLICITA_LIBERACION: "Solicita liberación", SOLICITA_REPROG: "Solicita reprogramación", SIN_RESPUESTA: "Sin respuesta" };

// RF-009, RF-015 a RF-017, RF-084 y RNF-016: filtros del contrato en URL,
// catálogos de la API, cuatro estados y acciones por rol (M02-V01).
export default function Bandeja() {
  const [busqueda, setBusqueda] = useSearchParams();
  const { tieneRol } = useAuth();
  const puedeEscribir = tieneRol(...ROLES_ESCRITURA);
  const navigate = useNavigate();
  const [errorFiltro, setErrorFiltro] = useState("");
  const offset = Number(busqueda.get("desplazamiento") || 0);
  const desplazamiento = Number.isSafeInteger(offset) && offset >= 0 ? offset : 0;
  const limiteSolicitado = Number(busqueda.get("limite") || LIMITE);
  const limite = Number.isSafeInteger(limiteSolicitado) && limiteSolicitado >= 1 && limiteSolicitado <= 200 ? limiteSolicitado : LIMITE;
  const consulta = new URLSearchParams({ limite: String(limite), desplazamiento: String(desplazamiento) });
  FILTROS.forEach((nombre) => {
    const valor = busqueda.get(nombre);
    if (valor) consulta.set(nombre, valor);
  });
  const { datos, error, cargando, reintentar } = useConsulta<Pagina<CitaResumenOut>>(`/citas?${consulta}`);
  const catalogos = useConsulta<CatalogosOut>("/citas/catalogos");
  const volver = `/citas?${busqueda}`;

  function aplicar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const campos = new FormData(evento.currentTarget);
    const filtros = Object.fromEntries(FILTROS.map((nombre) => [nombre, String(campos.get(nombre) || "").trim()]));
    if (filtros.desde && filtros.hasta && filtros.desde > filtros.hasta) {
      setErrorFiltro("La fecha inicial no puede ser posterior a la fecha final.");
      return;
    }
    setErrorFiltro("");
    const siguientes = new URLSearchParams(Object.fromEntries(Object.entries(filtros).filter(([, valor]) => valor !== "")));
    if (busqueda.has("limite")) siguientes.set("limite", String(limite));
    setBusqueda(siguientes);
  }

  function cambiarPagina(nuevo: number) {
    const siguientes = new URLSearchParams(busqueda);
    siguientes.set("desplazamiento", String(nuevo));
    setBusqueda(siguientes);
  }

  return <>
    <div className="pagina-titulo"><div><p className="sobretitulo">SEGUIMIENTO DEL PACIENTE</p><h1>Bandeja de citas</h1><p>Encuentra una cita y continúa su seguimiento.</p></div><div className="flex flex-wrap items-center gap-2"><span className="contexto-horario"><Icono nombre="reloj" />Hora de Lima</span>{puedeEscribir && <><Link className="boton" to="/citas/nueva">Registrar cita</Link><Link className="boton-secundario" to="/citas/importar"><Icono nombre="importar" />Importar</Link></>}</div></div>
    {catalogos.error && <div className="space-y-3"><Mensaje>No se pudieron cargar los filtros: {catalogos.error}</Mensaje><button className="boton-secundario" onClick={catalogos.reintentar}>Reintentar catálogos</button></div>}
    <form key={`${busqueda}:${catalogos.cargando}`} onSubmit={aplicar} className="tarjeta filtros-citas">
      <div className="seccion-cabecera"><h2><Icono nombre="filtro" />Buscar una cita</h2><p>Combina los filtros que necesites.</p></div>
      {catalogos.cargando && <Cargando texto="Cargando filtros…" />}
      <fieldset disabled={cargando || catalogos.cargando || !!catalogos.error} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <legend className="sr-only">Filtros de citas</legend>
        <div><label htmlFor="q">Identificador de cita</label><div className="campo-icono"><Icono nombre="buscar" /><input id="q" name="q" aria-describedby="ayuda-busqueda" defaultValue={busqueda.get("q") || ""} placeholder="Por ejemplo, CIT-SIM-000324" /></div><p id="ayuda-busqueda" className="ayuda-seccion">ID de cita, paciente o médico</p></div>
        <div><label htmlFor="desde">Desde</label><input id="desde" name="desde" type="date" defaultValue={busqueda.get("desde") || ""} /></div>
        <div><label htmlFor="hasta">Hasta</label><input id="hasta" name="hasta" type="date" defaultValue={busqueda.get("hasta") || ""} /></div>
        <div><label htmlFor="especialidad">Especialidad</label><select id="especialidad" name="especialidad" defaultValue={busqueda.get("especialidad") || ""}>
          <option value="">Todas</option>{catalogos.datos?.especialidades.map((valor) => <option key={valor} value={valor}>{etiqueta(valor)}</option>)}
        </select></div>
        <div><label htmlFor="medico">Médico</label><select id="medico" name="medico" defaultValue={busqueda.get("medico") || ""}>
          <option value="">Todos</option>{catalogos.datos?.medicos.map((valor) => <option key={valor} value={valor}>{valor}</option>)}
        </select></div>
        <div><label htmlFor="estado">Estado</label><select id="estado" name="estado" defaultValue={busqueda.get("estado") || ""}>
          <option value="">Todos</option>{catalogos.datos?.estados.map((valor) => <option key={valor} value={valor}>{etiqueta(valor)}</option>)}
        </select></div>
        <div><label htmlFor="nivel_riesgo">Nivel de riesgo</label><select id="nivel_riesgo" name="nivel_riesgo" defaultValue={busqueda.get("nivel_riesgo") || ""}>
          <option value="">Todos</option>{catalogos.datos?.niveles_riesgo.map((valor) => <option key={valor} value={valor}>{valor === "BAJO" ? "Bajo" : valor === "MEDIO" ? "Medio" : "Alto"}</option>)}<option value="SIN_PREDICCION">Sin predicción</option>
        </select></div>
        <div><label htmlFor="con_intervencion">Intervención</label><select id="con_intervencion" name="con_intervencion" defaultValue={busqueda.get("con_intervencion") || ""}>
          <option value="">Todas</option><option value="true">Con intervención</option><option value="false">Sin intervención</option>
        </select></div>
        <div className="flex flex-wrap items-end gap-2">
          <button type="submit" className="boton"><Icono nombre="buscar" />Aplicar filtros</button>
          <button type="button" className="boton-secundario" onClick={(evento) => { evento.currentTarget.form?.reset(); setErrorFiltro(""); setBusqueda({}); }}>Limpiar</button>
        </div>
      </fieldset>
    </form>
    {errorFiltro && <Mensaje>{errorFiltro}</Mensaje>}
    {cargando ? <Cargando texto="Cargando citas…" /> : error ? <div className="space-y-3"><Mensaje>{error}</Mensaje><button className="boton-secundario" onClick={reintentar}>Reintentar</button></div> : datos && <>
      <div className="resultados-cabecera"><h2>Citas encontradas <span className="contador-citas">{datos.total}</span></h2><p>Abre el detalle para ver el historial y las acciones disponibles.</p></div>
      <p className="ayuda-seccion">El riesgo estima inasistencia para orientar el acompañamiento; no es una decisión clínica.</p>
      <div className="tabla-contenedor" role="region" aria-label="Resultados de citas" tabIndex={0}>
        <table className="w-full tabla-citas"><caption className="sr-only">Citas que cumplen los filtros aplicados</caption>
          <thead><tr>
            <th scope="col">Fecha y hora</th><th scope="col">Identificador</th><th scope="col">Especialidad</th><th scope="col">Médico</th><th scope="col">Estado</th><th scope="col">Riesgo</th><th scope="col">Intervención</th><th scope="col">Llegada</th><th scope="col">Acción</th>
          </tr></thead>
          <tbody className="divide-y divide-slate-100">
            {datos.items.length === 0 ? <tr><td colSpan={9}><div className="estado-vacio"><Icono nombre="calendario" /><p>No hay citas con esos filtros.</p><span>Prueba otra fecha o utiliza «Limpiar» para ampliar la búsqueda.</span></div></td></tr> : datos.items.map((cita) => <tr key={cita.id_cita} className="fila-cita cursor-pointer"
              onClick={(evento) => { if (!(evento.target instanceof Element) || !evento.target.closest("a")) navigate(`/citas/${cita.id_cita}`, { state: { volver } }); }}>
              <td className="whitespace-nowrap">{formatearFechaHora(cita.fecha_hora_cita)}</td>
              <td className="id-cita">{cita.id_cita_externa}<span className="mt-1 block text-xs font-normal">{cita.paciente_anon_id}</span></td><td>{etiqueta(cita.especialidad)}</td><td>{cita.medico}</td>
              <td><EstadoBadge estado={cita.estado_actual} /></td>
              {/* RF-056, RN16 y RNF-017: el riesgo se identifica y el simulado se rotula junto al dato. */}
              <td>{cita.riesgo ? <div className="space-y-1"><NivelRiesgoBadge nivel={cita.riesgo.nivel_riesgo} />{cita.riesgo.resultado_simulado && <RotuloSimulado />}</div> : "Sin predicción"}</td>
              <td>{cita.estado_intervencion ? <div>{INTERVENCIONES[cita.estado_intervencion]}{cita.respuesta_paciente && <span className="mt-1 block text-xs">{RESPUESTAS[cita.respuesta_paciente]}</span>}</div> : "Sin intervención"}</td>
              {/* RF-104: informa la llegada sin confundirla con el desenlace de la cita. */}
              <td>{cita.tiene_check_in ? <span className="inline-flex items-center gap-1 text-emerald-800"><Icono nombre="check" />Check-in registrado</span> : "Sin check-in"}</td>
              <td><Link className="enlace-detalle" to={`/citas/${cita.id_cita}`} state={{ volver }}>Ver detalle<Icono nombre="flecha" /></Link></td>
            </tr>)}
          </tbody>
        </table>
      </div>
      <div className="paginacion">
        <p>Página {Math.floor(desplazamiento / limite) + 1} de {Math.max(1, Math.ceil(datos.total / limite))}</p>
        <div className="flex gap-2">
          <button className="boton-secundario" disabled={desplazamiento === 0} onClick={() => cambiarPagina(Math.max(0, desplazamiento - limite))}>Anterior</button>
          <button className="boton-secundario" disabled={desplazamiento + limite >= datos.total} onClick={() => cambiarPagina(desplazamiento + limite)}>Siguiente</button>
        </div>
      </div>
    </>}
  </>;
}
