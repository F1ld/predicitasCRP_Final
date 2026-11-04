import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, esCancelacion } from "../../nucleo/api/cliente";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import Icono from "../../nucleo/componentes/Icono";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta, formatearFechaHora } from "../../nucleo/formato/formato";
import { mensajeErrorM06 } from "./errores";
import { descargarRep03, type FiltrosRep03, type FormatoExportacion } from "./exportar";
import { ESPECIALIDADES, ROLES_ESCRITURA, type Rep03Out } from "./tipos";
import "./lista-espera.css";

const CAMPOS = ["desde", "hasta", "especialidad", "id_operador"] as const;
const numero = new Intl.NumberFormat("es-PE", { maximumFractionDigits: 2 });
const porcentaje = new Intl.NumberFormat("es-PE", { style: "percent", maximumFractionDigits: 1 });
const ESTADOS: Record<string, string> = { DISPONIBLE: "Disponible", EN_OFERTA: "En oferta", REASIGNADO: "Reasignado", EXPIRADO: "Expirado" };

function validar(filtros: FiltrosRep03) {
  for (const campo of ["desde", "hasta"] as const) {
    const valor = filtros[campo];
    if (valor && (!/^\d{4}-\d{2}-\d{2}$/.test(valor) || !Number.isFinite(Date.parse(`${valor}T12:00:00Z`)) || new Date(`${valor}T12:00:00Z`).toISOString().slice(0, 10) !== valor)) {
      return "Indica fechas válidas en los filtros del reporte.";
    }
  }
  if (filtros.desde && filtros.hasta && filtros.desde > filtros.hasta) return "La fecha inicial no puede ser posterior a la fecha final.";
  if (filtros.especialidad && !ESPECIALIDADES.some((valor) => valor === filtros.especialidad)) return "Selecciona una especialidad del piloto.";
  if (filtros.id_operador && (!/^\d+$/.test(filtros.id_operador) || !Number.isSafeInteger(Number(filtros.id_operador)) || Number(filtros.id_operador) < 1)) return "El ID del operador debe ser un número entero mayor que 0.";
  return "";
}

function ReportePermitido() {
  const [busqueda, setBusqueda] = useSearchParams();
  const [errorFiltro, setErrorFiltro] = useState("");
  const filtros: FiltrosRep03 = Object.fromEntries(CAMPOS.map((campo) => [campo, busqueda.get(campo) || ""]));
  const errorUrl = validar(filtros);
  const consulta = new URLSearchParams({ formato: "json" });
  CAMPOS.forEach((campo) => { if (filtros[campo]) consulta.set(campo, filtros[campo]); });

  function aplicar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const datos = new FormData(evento.currentTarget);
    const nuevos: FiltrosRep03 = Object.fromEntries(CAMPOS.map((campo) => [campo, String(datos.get(campo) || "").trim()]));
    const fallo = validar(nuevos);
    setErrorFiltro(fallo);
    if (fallo) return;
    setBusqueda(Object.fromEntries(Object.entries(nuevos).filter(([, valor]) => valor !== "")));
  }

  return <div className="m06-reporte space-y-6">
    <div className="pagina-titulo"><div><p className="sobretitulo">REP-03 · REASIGNACIÓN ASISTIDA</p><h1>Reporte de reasignaciones</h1><p>Consulta la recuperación de cupos y el tiempo hasta su reasignación.</p></div><span className="contexto-horario"><Icono nombre="reloj" />Hora de Lima</span></div>
    <form key={busqueda.toString()} onSubmit={aplicar} noValidate className="tarjeta filtros-citas m06-no-imprimir" aria-label="Filtros del reporte">
      <div className="seccion-cabecera"><h2><Icono nombre="filtro" />Filtrar el reporte</h2><p>Las fechas son inclusivas en hora de Lima.</p></div>
      <fieldset className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><legend className="sr-only">Filtros de reasignaciones</legend>
        <div><label htmlFor="rep03-desde">Desde</label><input id="rep03-desde" name="desde" type="date" defaultValue={filtros.desde} /></div>
        <div><label htmlFor="rep03-hasta">Hasta</label><input id="rep03-hasta" name="hasta" type="date" defaultValue={filtros.hasta} /></div>
        <div><label htmlFor="rep03-especialidad">Especialidad</label><select id="rep03-especialidad" name="especialidad" defaultValue={filtros.especialidad}><option value="">Todas</option>{ESPECIALIDADES.map((valor) => <option key={valor} value={valor}>{etiqueta(valor)}</option>)}</select></div>
        <div><label htmlFor="rep03-operador">ID del operador</label><input id="rep03-operador" name="id_operador" inputMode="numeric" defaultValue={filtros.id_operador} aria-describedby="rep03-operador-ayuda" /><p id="rep03-operador-ayuda" className="ayuda-seccion">Identificador del operador que confirmó.</p></div>
        <div className="flex flex-wrap gap-2 sm:col-span-2 lg:col-span-4"><button className="boton" type="submit">Aplicar filtros</button><button className="boton-secundario" type="button" onClick={() => { setErrorFiltro(""); setBusqueda({}); }}>Limpiar</button><Link className="boton-secundario" to="/cupos">Ver cupos liberados</Link></div>
      </fieldset>
    </form>
    {(errorFiltro || errorUrl) && <Mensaje>{errorFiltro || errorUrl}</Mensaje>}
    {!errorUrl && <DatosReporte key={consulta.toString()} consulta={consulta.toString()} filtros={filtros} />}
  </div>;
}

function DatosReporte({ consulta, filtros }: { consulta: string; filtros: FiltrosRep03 }) {
  const [intento, setIntento] = useState(0);
  const [resultado, setResultado] = useState<{ intento: number; datos: Rep03Out | null; error: string } | null>(null);
  const [exportando, setExportando] = useState<FormatoExportacion | null>(null);
  const [errorExportacion, setErrorExportacion] = useState("");
  const [exitoExportacion, setExitoExportacion] = useState("");
  const descarga = useRef<AbortController | null>(null);
  useEffect(() => {
    const controlador = new AbortController();
    api<Rep03Out>(`/reportes/rep-03?${consulta}`, { signal: controlador.signal }).then(
      (datos) => { if (!controlador.signal.aborted) setResultado({ intento, datos, error: datos ? "" : "El servidor no devolvió el reporte." }); },
      (fallo: unknown) => { if (!controlador.signal.aborted && !esCancelacion(fallo)) setResultado({ intento, datos: null, error: mensajeErrorM06(fallo) }); },
    );
    return () => controlador.abort();
  }, [consulta, intento]);
  useEffect(() => () => descarga.current?.abort(), []);
  const cargando = resultado?.intento !== intento;
  const datos = cargando ? null : resultado?.datos;

  async function exportar(formato: FormatoExportacion) {
    if (descarga.current) return;
    const controlador = new AbortController(); descarga.current = controlador;
    setExportando(formato); setErrorExportacion(""); setExitoExportacion("");
    try {
      const nombre = await descargarRep03(formato, filtros, controlador.signal);
      if (!controlador.signal.aborted) setExitoExportacion(`Descarga preparada: ${nombre}`);
    } catch (fallo: unknown) {
      if (!controlador.signal.aborted && !esCancelacion(fallo)) setErrorExportacion(mensajeErrorM06(fallo));
    } finally { if (!controlador.signal.aborted) setExportando(null); descarga.current = null; }
  }

  if (cargando) return <Cargando texto="Cargando reporte de reasignaciones…" />;
  if (resultado?.error) return <div className="space-y-3"><Mensaje>{resultado.error}</Mensaje><button type="button" className="boton-secundario m06-no-imprimir" onClick={() => setIntento((actual) => actual + 1)}>Reintentar</button></div>;
  if (!datos) return null;
  return <>
    <p className="ayuda-seccion">Filtros aplicados: desde {filtros.desde || "sin límite"} · hasta {filtros.hasta || "sin límite"} · {filtros.especialidad ? etiqueta(filtros.especialidad) : "todas las especialidades"} · {filtros.id_operador ? `operador ${filtros.id_operador}` : "todos los operadores"}.</p>
    <div className="m06-reporte-resumen grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Resumen del reporte">
      <dl className="tarjeta"><dt>Cupos liberados</dt><dd className="mt-3 text-2xl font-semibold">{numero.format(datos.resumen.cupos_liberados)}</dd></dl>
      <dl className="tarjeta"><dt>Cupos reasignados</dt><dd className="mt-3 text-2xl font-semibold">{numero.format(datos.resumen.cupos_reasignados)}</dd></dl>
      <dl className="tarjeta"><dt>Tasa de recuperación</dt><dd className="mt-3 text-2xl font-semibold">{porcentaje.format(datos.resumen.tasa_recuperacion)}</dd></dl>
      <dl className="tarjeta"><dt>Horas promedio de matching</dt><dd className="mt-3 text-2xl font-semibold">{datos.resumen.horas_promedio_matching === null ? "Sin reasignaciones" : `${numero.format(datos.resumen.horas_promedio_matching)} h`}</dd></dl>
    </div>
    <section className="tarjeta m06-reporte-especialidades" aria-labelledby="rep03-especialidades"><div className="seccion-cabecera"><h2 id="rep03-especialidades">Recuperación por especialidad</h2><p>Cupos reasignados del total liberado.</p></div>
      {datos.por_especialidad.length === 0 ? <p className="ayuda-seccion">Sin cupos por especialidad en este periodo.</p> : <ul className="grid gap-5 sm:grid-cols-3">{datos.por_especialidad.map((grupo) => <li key={grupo.especialidad} className="space-y-2"><p className="font-semibold">{etiqueta(grupo.especialidad)}</p><p className="text-sm">{grupo.reasignados} de {grupo.liberados} cupos · {porcentaje.format(grupo.liberados === 0 ? 0 : grupo.reasignados / grupo.liberados)}</p><progress className="m06-reporte-progreso" max={grupo.liberados || 1} value={grupo.reasignados} aria-label={`Recuperación en ${etiqueta(grupo.especialidad)}`} aria-valuetext={`${grupo.reasignados} de ${grupo.liberados} cupos reasignados`} /></li>)}</ul>}
    </section>
    <div className="flex flex-wrap items-center justify-between gap-4 m06-no-imprimir"><h2>Detalle de cupos</h2><div className="flex flex-wrap gap-2"><button className="boton-secundario" type="button" disabled={!!exportando} onClick={() => void exportar("csv")}>{exportando === "csv" ? "Exportando CSV…" : "Exportar CSV"}</button><button className="boton-secundario" type="button" disabled={!!exportando} onClick={() => void exportar("xlsx")}>{exportando === "xlsx" ? "Exportando Excel…" : "Exportar Excel"}</button><button type="button" className="boton-secundario" disabled={!!exportando} onClick={() => window.print()}>Imprimir</button></div></div>
    {exportando && <p role="status" className="m06-no-imprimir">Preparando la exportación…</p>}{errorExportacion && <Mensaje>{errorExportacion}</Mensaje>}{exitoExportacion && <Mensaje tipo="exito">{exitoExportacion}</Mensaje>}
    {datos.filas.length === 0 ? <div className="tarjeta estado-vacio" role="status"><Icono nombre="calendario" /><p>No hay cupos en el reporte con esos filtros.</p><span>Amplía el periodo o limpia los filtros para volver a consultar.</span></div> : <div className="tabla-contenedor" role="region" aria-label="Detalle del reporte de reasignaciones" tabIndex={0}><table className="w-full"><caption className="sr-only">REP-03: cupos liberados y su reasignación; fechas en hora de Lima.</caption><thead><tr><th scope="col">Cupo</th><th scope="col">Fecha y hora del cupo</th><th scope="col">Especialidad</th><th scope="col">Médico</th><th scope="col">Horas disponible</th><th scope="col">Paciente asignado</th><th scope="col">Operador confirma</th><th scope="col">Estado</th></tr></thead><tbody>{datos.filas.map((fila) => <tr key={fila.id_cupo_liberado}><td><Link to={`/cupos/${fila.id_cupo_liberado}`} className="enlace-detalle">Cupo {fila.id_cupo_liberado}</Link></td><td className="whitespace-nowrap">{formatearFechaHora(fila.fecha_hora_cupo)}</td><td>{etiqueta(fila.especialidad)}</td><td>{fila.medico}</td><td>{numero.format(fila.horas_disponible)} h</td><td>{fila.paciente_anon_id_asignado ?? "Sin asignar"}</td><td>{fila.id_operador_confirma ?? "Sin confirmación"}</td><td>{ESTADOS[fila.estado_cupo] || fila.estado_cupo}</td></tr>)}</tbody></table></div>}
  </>;
}

// RF-094/REP-03, RNF-007/RNF-016: reporte operativo con datos seudonimizados y acceso restringido.
export default function Reporte() {
  const { tieneRol } = useAuth();
  return tieneRol(...ROLES_ESCRITURA) ? <ReportePermitido /> : <Mensaje tipo="info">Tu rol no tiene permiso para consultar el reporte de reasignaciones.</Mensaje>;
}
