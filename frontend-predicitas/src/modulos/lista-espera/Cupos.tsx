import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Pagina } from "../../nucleo/api/tipos";
import { useConsulta } from "../../nucleo/api/useConsulta";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import Icono from "../../nucleo/componentes/Icono";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta, formatearFechaHora } from "../../nucleo/formato/formato";
import { ESPECIALIDADES, ESTADOS_CUPO, ROLES_ESCRITURA, type CupoOut } from "./tipos";
import "./lista-espera.css";

const ETIQUETAS_ESTADO = { DISPONIBLE: "Disponible", EN_OFERTA: "En oferta", REASIGNADO: "Reasignado", EXPIRADO: "Expirado" };
const FILTROS = ["estado_cupo", "especialidad", "desde", "hasta"] as const;
const LIMITE = 20;

// RF-003, RF-073, RF-080: la protección local evita consultas si se monta
// directamente; la ranura aplica además los permisos globales del contrato.
export default function Cupos() {
  const { tieneRol } = useAuth();
  return tieneRol(...ROLES_ESCRITURA) ? <ListadoCupos /> : <Mensaje>No tienes permiso para consultar los cupos liberados.</Mensaje>;
}

function ListadoCupos() {
  const [busqueda, setBusqueda] = useSearchParams();
  const [errorFiltros, setErrorFiltros] = useState("");
  const offset = Number(busqueda.get("desplazamiento") || 0);
  const desplazamiento = Number.isSafeInteger(offset) && offset >= 0 ? offset : 0;
  const consulta = new URLSearchParams({ limite: String(LIMITE), desplazamiento: String(desplazamiento) });
  for (const nombre of FILTROS) {
    const valor = busqueda.get(nombre);
    if (valor) consulta.set(nombre, valor);
  }
  const { datos, error, cargando, reintentar } = useConsulta<Pagina<CupoOut>>(`/cupos?${consulta}`);
  const volver = `/cupos?${busqueda}`;

  function aplicar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const campos = new FormData(evento.currentTarget);
    const filtros = Object.fromEntries(FILTROS.map(nombre => [nombre, String(campos.get(nombre) || "")]));
    if (filtros.desde && filtros.hasta && filtros.desde > filtros.hasta) {
      setErrorFiltros("La fecha inicial no puede ser posterior a la fecha final.");
      return;
    }
    setErrorFiltros("");
    setBusqueda(Object.fromEntries(Object.entries(filtros).filter(([, valor]) => valor)));
  }
  function paginar(valor: number) {
    const siguientes = new URLSearchParams(busqueda);
    siguientes.set("desplazamiento", String(valor));
    setBusqueda(siguientes);
  }

  return <div className="m06-vista space-y-6">
    <div className="pagina-titulo"><div><p className="sobretitulo">REASIGNACIÓN ASISTIDA</p><h1>Cupos liberados</h1><p>Consulta los cupos disponibles y continúa su reasignación.</p></div><span className="contexto-horario"><Icono nombre="reloj" />Hora de Lima</span></div>
    <p className="m06-aviso">Solo se muestran cupos liberados formalmente. La confirmación de una reasignación requiere intervención humana.</p>
    <form className="tarjeta" onSubmit={aplicar} key={busqueda.toString()} aria-label="Filtrar cupos">
      <div className="seccion-cabecera"><h2><Icono nombre="filtro" />Buscar un cupo</h2><p>Las fechas corresponden al horario del cupo en Lima.</p></div>
      <fieldset className="m06-formulario" disabled={cargando}>
        <legend className="sr-only">Filtros de cupos</legend>
        <div><label htmlFor="cupo-estado">Estado del cupo</label><select id="cupo-estado" name="estado_cupo" defaultValue={busqueda.get("estado_cupo") || ""}><option value="">Todos</option>{ESTADOS_CUPO.map(estado => <option key={estado} value={estado}>{ETIQUETAS_ESTADO[estado]}</option>)}</select></div>
        <div><label htmlFor="cupo-especialidad">Especialidad</label><select id="cupo-especialidad" name="especialidad" defaultValue={busqueda.get("especialidad") || ""}><option value="">Todas</option>{ESPECIALIDADES.map(especialidad => <option key={especialidad} value={especialidad}>{etiqueta(especialidad)}</option>)}</select></div>
        <div><label htmlFor="cupo-desde">Desde</label><input id="cupo-desde" name="desde" type="date" defaultValue={busqueda.get("desde") || ""} /></div>
        <div><label htmlFor="cupo-hasta">Hasta</label><input id="cupo-hasta" name="hasta" type="date" defaultValue={busqueda.get("hasta") || ""} /></div>
        <div className="m06-acciones"><button type="submit" className="boton">Aplicar filtros</button><button type="button" className="boton-secundario" onClick={evento => { evento.currentTarget.form?.reset(); setErrorFiltros(""); setBusqueda({}); }}>Limpiar</button></div>
      </fieldset>
    </form>
    {errorFiltros && <Mensaje>{errorFiltros}</Mensaje>}
    {cargando ? <Cargando texto="Cargando cupos…" /> : error ? <div className="space-y-3"><Mensaje>{error}</Mensaje><button type="button" className="boton-secundario" onClick={reintentar}>Reintentar</button></div> : (() => {
      const listaCupos = Array.isArray(datos) ? datos : (datos?.items ?? []);
      const totalCupos = typeof datos?.total === "number" ? datos.total : listaCupos.length;
      return <>
      <div className="resultados-cabecera"><h2>Cupos encontrados <span className="contador-citas">{totalCupos}</span></h2><p>Abre un cupo para consultar sus candidatos y ofertas.</p></div>
      {listaCupos.length === 0 ? <div className="tarjeta estado-vacio"><Icono nombre="calendario" /><p>No hay cupos con esos filtros.</p><span>Amplía las fechas o utiliza «Limpiar».</span></div> : <div className="tabla-contenedor" role="region" aria-label="Cupos encontrados" tabIndex={0}><table><caption className="sr-only">Cupos liberados ordenados por su fecha y hora</caption><thead><tr>{["Cupo", "Fecha y hora", "Especialidad", "Médico", "Franja", "Estado", "Cita de origen", "Acción"].map(nombre => <th scope="col" key={nombre}>{nombre}</th>)}</tr></thead><tbody>{listaCupos.map(cupo => <tr key={cupo.id_cupo_liberado}>
        <td>#{cupo.id_cupo_liberado}</td><td>{formatearFechaHora(cupo.fecha_hora_cupo)}</td><td>{etiqueta(cupo.especialidad)}</td><td>{cupo.medico}</td><td>{etiqueta(cupo.franja_horaria)}</td><td><span className="m06-estado">{ETIQUETAS_ESTADO[cupo.estado_cupo]}</span></td><td>{cupo.id_cita_externa_origen}</td><td><Link className="enlace-detalle" to={`/cupos/${cupo.id_cupo_liberado}`} state={{ volver }}>Ver cupo<Icono nombre="flecha" /></Link></td>
      </tr>)}</tbody></table></div>}
      <div className="paginacion"><p>Página {Math.floor(desplazamiento / LIMITE) + 1} de {Math.max(1, Math.ceil(totalCupos / LIMITE))}</p><div className="m06-acciones"><button type="button" className="boton-secundario" disabled={desplazamiento === 0} onClick={() => paginar(Math.max(0, desplazamiento - LIMITE))}>Anterior</button><button type="button" className="boton-secundario" disabled={desplazamiento + LIMITE >= totalCupos} onClick={() => paginar(desplazamiento + LIMITE)}>Siguiente</button></div></div>
    </>;
    })()}
  </div>;
}
