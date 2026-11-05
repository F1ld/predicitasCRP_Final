import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, esCancelacion } from "../../nucleo/api/cliente";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta, formatearFechaHora } from "../../nucleo/formato/formato";
import { mensajeErrorM06 } from "./errores";
import { MEDIOS_CONFIRMACION, ROLES_ESCRITURA } from "./tipos";
import type { CandidatoOut, CierreOfertaIn, CupoDetalleOut, CupoOut, OfertaIn, ReasignacionIn, ReasignacionOut } from "./tipos";
import "./lista-espera.css";

interface ConsultaCupo { cupo: CupoDetalleOut | null; candidatos: CandidatoOut[]; errorCandidatos: string }
const AVISO_AGENDAMIENTO = "Agenda la cita en el sistema de la clínica: PrediCitas no agenda";
const etiquetasMedio: Record<string, string> = { LLAMADA_CONFIRMADA: "Llamada confirmada", PRESENCIAL: "Presencial" };

// RF-003: un acceso directo sin permiso tampoco consulta datos del módulo.
export default function DetalleCupo() {
  const { id = "" } = useParams();
  const { tieneRol } = useAuth();
  if (!tieneRol(...ROLES_ESCRITURA)) return <Mensaje>No tienes permiso para acceder a los cupos liberados.</Mensaje>;
  return <DetalleAutorizado key={id} id={id} />;
}

// RF-074 a RF-076, RN05: el servidor determina compatibilidad y orden de propuesta.
async function consultarCupo(id: string, signal: AbortSignal): Promise<ConsultaCupo> {
  let cupo = await api<CupoDetalleOut>(`/cupos/${id}`, { signal });
  if (!cupo || cupo.estado_cupo === "EXPIRADO" || cupo.estado_cupo === "REASIGNADO") return { cupo, candidatos: [], errorCandidatos: "" };
  try {
    const candidatos = await api<CandidatoOut[]>(`/cupos/${id}/candidatos`, { signal });
    if (!candidatos) throw new Error("El servidor no devolvió las propuestas de candidatos.");
    return { cupo, candidatos, errorCandidatos: "" };
  } catch (fallo) {
    if (esCancelacion(fallo)) throw fallo;
    // RF-081: entre las lecturas otro operador puede haber asignado el cupo.
    if (fallo instanceof ApiError && fallo.status === 409) cupo = await api<CupoDetalleOut>(`/cupos/${id}`, { signal });
    return { cupo, candidatos: [], errorCandidatos: mensajeErrorM06(fallo) };
  }
}

// RF-077 a RF-082, RN11, RNF-029: oferta y confirmación son acciones separadas.
function DetalleAutorizado({ id }: { id: string }) {
  const [consulta, setConsulta] = useState<ConsultaCupo | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [errorAccion, setErrorAccion] = useState("");
  const [exito, setExito] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [requiereRefresco, setRequiereRefresco] = useState(false);
  const [confirmada, setConfirmada] = useState(false);
  const [medio, setMedio] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [errorConfirmacion, setErrorConfirmacion] = useState("");
  const dialogo = useRef<HTMLDialogElement>(null);
  const controlador = useRef<AbortController | null>(null);
  const accionEnCurso = useRef(false);

  useEffect(() => {
    const vida = new AbortController(); controlador.current = vida;
    consultarCupo(id, vida.signal).then((datos) => {
      if (!vida.signal.aborted) { setConsulta(datos); setCargando(false); }
    }, (fallo: unknown) => {
      if (!vida.signal.aborted && !esCancelacion(fallo)) { setError(mensajeErrorM06(fallo)); setCargando(false); }
    });
    return () => { vida.abort(); };
  }, [id]);

  function limpiarConfirmacion() {
    setConfirmada(false); setMedio(""); setObservaciones(""); setErrorConfirmacion("");
  }
  function cerrarDialogo() { dialogo.current?.close(); limpiarConfirmacion(); }

  async function refrescar(): Promise<boolean> {
    const signal = controlador.current?.signal;
    if (!signal || signal.aborted) return false;
    const datos = await consultarCupo(id, signal);
    if (signal.aborted) return false;
    setConsulta(datos); setError(""); setCargando(false);
    setRequiereRefresco(Boolean(datos.errorCandidatos));
    if (datos.errorCandidatos) throw new Error(datos.errorCandidatos);
    return true;
  }

  async function reintentar() {
    if (accionEnCurso.current) return;
    accionEnCurso.current = true; setOcupado(true);
    try { await refrescar(); setErrorAccion(""); }
    catch (fallo) {
      if (!esCancelacion(fallo)) {
        if (consulta?.cupo) { setErrorAccion(`No se pudo refrescar el cupo: ${mensajeErrorM06(fallo)}`); setRequiereRefresco(true); }
        else { setError(mensajeErrorM06(fallo)); setCargando(false); }
      }
    } finally { accionEnCurso.current = false; setOcupado(false); }
  }

  async function mutar<T>(ruta: string, peticion: OfertaIn | CierreOfertaIn | ReasignacionIn, aplicar: (resultado: T) => CupoDetalleOut, mensaje: string) {
    if (accionEnCurso.current) return;
    const signal = controlador.current?.signal;
    if (!signal || signal.aborted) return;
    accionEnCurso.current = true; setOcupado(true); setErrorAccion(""); setExito("");
    try {
      const resultado = await api<T>(`/cupos/${id}/${ruta}`, { metodo: "POST", json: peticion, signal });
      if (!resultado) throw new Error("El servidor no devolvió el resultado de la acción.");
      if (signal.aborted) return;
      setConsulta((anterior) => ({ cupo: aplicar(resultado), candidatos: anterior?.candidatos ?? [], errorCandidatos: "" }));
      setExito(mensaje); cerrarDialogo();
      try { await refrescar(); }
      catch (fallo) {
        if (!signal.aborted && !esCancelacion(fallo)) { setErrorAccion(`La acción se guardó, pero no se pudo refrescar el detalle y sus propuestas: ${mensajeErrorM06(fallo)}`); setRequiereRefresco(true); }
      }
    } catch (fallo) {
      if (!signal.aborted && !esCancelacion(fallo)) {
        const mensajeFallo = mensajeErrorM06(fallo); setErrorAccion(mensajeFallo);
        if (fallo instanceof ApiError && fallo.status === 409) {
          cerrarDialogo(); setRequiereRefresco(true);
          try { await refrescar(); }
          catch (errorRefresco) { if (!esCancelacion(errorRefresco)) setErrorAccion(`${mensajeFallo} No se pudo refrescar el cupo: ${mensajeErrorM06(errorRefresco)}`); }
        }
      }
    } finally { accionEnCurso.current = false; if (!signal.aborted) setOcupado(false); }
  }

  const cupo = consulta?.cupo;
  const bloqueado = ocupado || requiereRefresco || Boolean(consulta?.errorCandidatos);
  const puedeOfrecer = cupo?.estado_cupo === "DISPONIBLE" && !cupo.oferta_vigente && !cupo.reasignacion;
  const puedeResolver = cupo?.estado_cupo === "EN_OFERTA" && Boolean(cupo.oferta_vigente) && !cupo.reasignacion;

  function ofrecer(candidato: CandidatoOut) {
    if (bloqueado || !puedeOfrecer || !cupo || !consulta?.candidatos.some((propuesto) => propuesto.id_candidato === candidato.id_candidato)) return;
    void mutar<CupoOut>("oferta", { id_candidato: candidato.id_candidato }, (resultado) => ({ ...cupo, ...resultado }), "Oferta registrada. Espera la respuesta del paciente antes de confirmar la reasignación.");
  }
  function cerrarOferta(respuesta: CierreOfertaIn["respuesta"]) {
    if (bloqueado || !puedeResolver || !cupo) return;
    void mutar<CupoOut>("oferta/cerrar", { respuesta }, (resultado) => ({ ...cupo, ...resultado }), respuesta === "RECHAZA" ? "Oferta cerrada: el paciente rechazó el cupo." : "Oferta cerrada: no hubo respuesta del paciente.");
  }
  function abrirConfirmacion() {
    if (bloqueado || !puedeResolver) return;
    limpiarConfirmacion(); dialogo.current?.showModal();
  }
  function confirmarReasignacion(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (bloqueado || !puedeResolver || !cupo?.oferta_vigente || accionEnCurso.current) return;
    const formulario = evento.currentTarget;
    const datos = new FormData(formulario);
    const control = formulario.elements.namedItem("confirmacion_humana");
    const medioEnviado = String(datos.get("medio_confirmacion") || "");
    // RN11: estado marcado, control marcado y valor literal deben coincidir.
    // Ni una respuesta API ni false/null/ausencia autorizan una reasignación.
    if (confirmada !== true || !(control instanceof HTMLInputElement) || control.checked !== true || datos.get("confirmacion_humana") !== "true") {
      setErrorConfirmacion("Marca la confirmación después de hablar con el paciente."); return;
    }
    if (!MEDIOS_CONFIRMACION.some((valor) => valor === medioEnviado) || medioEnviado !== medio) { setErrorConfirmacion("Selecciona el medio de confirmación."); return; }
    const texto = String(datos.get("observaciones") || "").trim();
    if (texto.length > 255 || !formulario.reportValidity()) { setErrorConfirmacion("Revisa las observaciones: el máximo es 255 caracteres."); return; }
    const peticion: ReasignacionIn = { id_candidato: cupo.oferta_vigente.id_candidato, confirmacion_humana: true, medio_confirmacion: medioEnviado as ReasignacionIn["medio_confirmacion"], ...(texto ? { observaciones: texto } : {}) };
    void mutar<ReasignacionOut>("reasignacion", peticion, (resultado) => ({ ...cupo, estado_cupo: "REASIGNADO", oferta_vigente: null, reasignacion: resultado }), AVISO_AGENDAMIENTO);
  }

  if (cargando) return <Cargando texto="Cargando cupo y propuestas…" />;
  if (error) return <div className="space-y-4"><Link className="enlace-volver" to="/cupos">← Volver a cupos liberados</Link><Mensaje>{error}</Mensaje><button className="boton-secundario" disabled={ocupado} onClick={() => void reintentar()}>Reintentar</button></div>;
  if (!cupo) return <div className="space-y-4"><Link className="enlace-volver" to="/cupos">← Volver a cupos liberados</Link><Mensaje>No se encontró el cupo liberado.</Mensaje></div>;
  return <>
    <Link className="enlace-volver" to="/cupos">← Volver a cupos liberados</Link>
    <div className="pagina-titulo"><div><p className="sobretitulo">REASIGNACIÓN ASISTIDA</p><h1>Cupo #{cupo.id_cupo_liberado}</h1><p>{etiqueta(cupo.especialidad)} · {formatearFechaHora(cupo.fecha_hora_cupo)}</p></div><span className="m06-estado">{cupo.estado_cupo}</span></div>
    {errorAccion && <Mensaje>{errorAccion}</Mensaje>}{exito && <Mensaje tipo="exito">{exito}</Mensaje>}
    {(requiereRefresco || consulta?.errorCandidatos) && <button className="boton-secundario" disabled={ocupado} onClick={() => void reintentar()}>Refrescar cupo y propuestas</button>}
    <section className="tarjeta" aria-labelledby="titulo-datos-cupo"><div className="seccion-cabecera"><h2 id="titulo-datos-cupo">Datos del cupo</h2><p>Proviene de una liberación formal de la cita de origen.</p></div><dl className="datos-cita">
      <div><dt>Cita de origen</dt><dd><Link className="text-teal-800 underline" to={`/citas/${cupo.id_cita_origen}`}>{cupo.id_cita_externa_origen}</Link></dd></div><div><dt>Médico</dt><dd>{cupo.medico}</dd></div>
      <div><dt>Especialidad</dt><dd>{etiqueta(cupo.especialidad)}</dd></div><div><dt>Franja</dt><dd>{etiqueta(cupo.franja_horaria)}</dd></div><div><dt>Fecha del cupo</dt><dd>{formatearFechaHora(cupo.fecha_hora_cupo)}</dd></div>
      <div><dt>Origen de liberación</dt><dd>{cupo.origen_liberacion}</dd></div><div><dt>Liberado el</dt><dd>{formatearFechaHora(cupo.liberado_en)}</dd></div>
    </dl></section>
    <section className="tarjeta" aria-labelledby="titulo-oferta"><div className="seccion-cabecera"><h2 id="titulo-oferta">Oferta vigente</h2></div>
      {cupo.oferta_vigente ? <><dl className="datos-cita"><div><dt>Paciente (seudónimo)</dt><dd>{cupo.oferta_vigente.paciente_anon_id}</dd></div><div><dt>Candidato</dt><dd>#{cupo.oferta_vigente.id_candidato}</dd></div><div><dt>Ofrecido el</dt><dd>{formatearFechaHora(cupo.oferta_vigente.fecha_hora_oferta)}</dd></div><div><dt>Operador de oferta</dt><dd>Usuario #{cupo.oferta_vigente.id_operador}</dd></div></dl>
        {puedeResolver && <div className="m06-acciones mt-4"><button className="boton-secundario" disabled={bloqueado} onClick={() => cerrarOferta("RECHAZA")}>Cerrar oferta: rechazó</button><button className="boton-secundario" disabled={bloqueado} onClick={() => cerrarOferta("SIN_RESPUESTA")}>Cerrar oferta: sin respuesta</button><button className="boton" disabled={bloqueado} onClick={abrirConfirmacion}>Confirmar reasignación</button></div>}
      </> : <p className="m06-aviso">No hay oferta vigente.</p>}
      {cupo.estado_cupo === "EXPIRADO" && <Mensaje tipo="info">El cupo expiró y no admite ofertas ni reasignación.</Mensaje>}
      {cupo.estado_cupo === "REASIGNADO" && <Mensaje tipo="info">El cupo ya fue reasignado y no admite una nueva asignación.</Mensaje>}
    </section>
    <section className="tarjeta" aria-labelledby="titulo-candidatos"><div className="seccion-cabecera"><h2 id="titulo-candidatos">Candidatos propuestos</h2><p>Compatibilidad por especialidad y franja; orden de inscripción definido por el sistema (RN05).</p></div>
      {consulta?.errorCandidatos && <Mensaje>{consulta.errorCandidatos}</Mensaje>}
      {cupo.estado_cupo === "EXPIRADO" || cupo.estado_cupo === "REASIGNADO" ? <p className="m06-aviso">No se proponen candidatos para este estado del cupo.</p> : consulta?.candidatos.length === 0 ? <p className="m06-aviso">No hay candidatos compatibles disponibles.</p> : <ol className="m06-lista-propuestas">{consulta?.candidatos.map((candidato, indice) => <li key={candidato.id_candidato}>
        <div><h3 className="font-semibold">Propuesta {indice + 1} · {candidato.paciente_anon_id}</h3><dl className="datos-cita"><div><dt>Prioridad de inscripción</dt><dd>{candidato.prioridad_registro}</dd></div><div><dt>Especialidad solicitada</dt><dd>{etiqueta(candidato.especialidad_req)}</dd></div><div><dt>Franja preferida</dt><dd>{etiqueta(candidato.franja_preferida)}</dd></div><div><dt>Inscrito el</dt><dd>{formatearFechaHora(candidato.fecha_registro)}</dd></div></dl></div>
        {puedeOfrecer && <button className="boton-secundario" disabled={bloqueado} onClick={() => ofrecer(candidato)} aria-label={`Ofrecer cupo a ${candidato.paciente_anon_id}`}>Ofrecer</button>}
      </li>)}</ol>}
    </section>
    <section className="tarjeta" aria-labelledby="titulo-reasignacion"><div className="seccion-cabecera"><h2 id="titulo-reasignacion">Reasignación registrada</h2></div>
      {!cupo.reasignacion ? <p className="m06-aviso">No hay reasignación registrada.</p> : <><dl className="datos-cita"><div><dt>Paciente asignado (seudónimo)</dt><dd>{cupo.reasignacion.paciente_anon_id}</dd></div><div><dt>Identificador de reasignación</dt><dd>#{cupo.reasignacion.id_reasignacion}</dd></div><div><dt>Confirmación humana</dt><dd>Confirmada por Usuario #{cupo.reasignacion.id_operador_confirma}</dd></div><div><dt>Medio de confirmación</dt><dd>{etiquetasMedio[cupo.reasignacion.medio_confirmacion]}</dd></div><div><dt>Fecha de reasignación</dt><dd>{formatearFechaHora(cupo.reasignacion.fecha_hora_reasigna)}</dd></div><div><dt>Observaciones</dt><dd>{cupo.reasignacion.observaciones || "Sin observaciones"}</dd></div></dl><p className="m06-aviso">{AVISO_AGENDAMIENTO}</p></>}
    </section>
    <section className="tarjeta" aria-labelledby="titulo-historial"><div className="seccion-cabecera"><h2 id="titulo-historial">Historial de ofertas</h2></div>
      {cupo.historial_ofertas.length === 0 ? <p className="m06-aviso">No hay ofertas registradas.</p> : <ol className="m06-historial">{cupo.historial_ofertas.map((oferta, indice) => <li key={`${oferta.id_candidato}-${oferta.fecha_hora_oferta}-${indice}`}><p className="font-semibold">Candidato #{oferta.id_candidato} · {oferta.cierre || "Oferta abierta"}</p><p>{formatearFechaHora(oferta.fecha_hora_oferta)}</p></li>)}</ol>}
    </section>
    <dialog ref={dialogo} className="dialogo-cambio m06-dialogo" aria-labelledby="titulo-confirmar-reasignacion" aria-describedby="ayuda-confirmar-reasignacion" onClose={limpiarConfirmacion} onCancel={(evento) => { if (ocupado) evento.preventDefault(); else limpiarConfirmacion(); }}>
      <form className="m06-formulario space-y-4" onSubmit={confirmarReasignacion}><h2 id="titulo-confirmar-reasignacion">Confirmar reasignación</h2><p id="ayuda-confirmar-reasignacion">Cupo #{cupo.id_cupo_liberado} para {cupo.oferta_vigente?.paciente_anon_id}. Confirma solo después de obtener la aceptación del paciente.</p>
        {errorConfirmacion && <Mensaje>{errorConfirmacion}</Mensaje>}
        <label className="m06-casilla"><input name="confirmacion_humana" type="checkbox" value="true" checked={confirmada} onChange={(evento) => setConfirmada(evento.currentTarget.checked)} disabled={ocupado} />Confirmé la reasignación con el paciente</label>
        <div><label htmlFor="medio-confirmacion">Medio de confirmación</label><select id="medio-confirmacion" name="medio_confirmacion" value={medio} onChange={(evento) => setMedio(evento.currentTarget.value)} required disabled={ocupado}><option value="">Selecciona un medio</option>{MEDIOS_CONFIRMACION.map((valor) => <option key={valor} value={valor}>{etiquetasMedio[valor]}</option>)}</select></div>
        <div><label htmlFor="observaciones-reasignacion">Observaciones (opcional)</label><textarea id="observaciones-reasignacion" name="observaciones" rows={3} maxLength={255} value={observaciones} onChange={(evento) => setObservaciones(evento.currentTarget.value)} disabled={ocupado} /></div>
        <div className="m06-acciones"><button className="boton-secundario" type="button" disabled={ocupado} onClick={cerrarDialogo}>Cancelar</button><button className="boton" type="submit" disabled={bloqueado || !confirmada || !medio}>{ocupado ? "Guardando reasignación…" : "Registrar reasignación"}</button></div>
      </form>
    </dialog>
  </>;
}
