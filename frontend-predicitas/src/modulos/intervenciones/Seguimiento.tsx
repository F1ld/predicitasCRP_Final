import { useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../../nucleo/api/cliente";
import { useConsulta } from "../../nucleo/api/useConsulta";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { formatearFechaHora } from "../../nucleo/formato/formato";
import Dialogo from "./Dialogo";
import { mensajeError } from "./errores";
import { rotulo } from "./presentacion";
import { RESPUESTAS, type AccionIntervencion, type CupoOut, type IntervencionOut } from "./tipos";
import "./intervenciones.css";
import "./seguimiento.css";

export default function Seguimiento() {
  const { id = "" } = useParams();
  return <DetalleIntervencion key={id} id={id} />;
}

// RF-059, RF-061 a RF-068, RN02: solo las acciones explícitas cambian datos.
function DetalleIntervencion({ id }: { id: string }) {
  const { tieneRol } = useAuth();
  const { datos: intervencion, cargando, error, actualizar, reintentar } = useConsulta<IntervencionOut>(`/intervenciones/${id}`);
  const [ocupada, setOcupada] = useState(false);
  const [errorAccion, setErrorAccion] = useState("");
  const [exito, setExito] = useState("");
  const [liberando, setLiberando] = useState(false);
  const [cupo, setCupo] = useState<CupoOut | null>(null);
  const accionEnCurso = useRef(false);
  const puedeEscribir = tieneRol("ADMINISTRADOR", "RECEPCION");
  const disponible = (accion: AccionIntervencion) => puedeEscribir && !!intervencion?.acciones_disponibles.includes(accion);

  async function registrar(ruta: string, json?: unknown) {
    if (accionEnCurso.current || !puedeEscribir) return;
    accionEnCurso.current = true;
    setOcupada(true); setErrorAccion(""); setExito("");
    try {
      const resultado = await api<IntervencionOut>(`/intervenciones/${id}/${ruta}`, { metodo: "POST", json });
      if (!resultado) throw new Error("El servidor no devolvió la intervención actualizada. Vuelve a consultar antes de repetir la acción.");
      actualizar(resultado);
      setExito(ruta === "respuesta" ? "Respuesta registrada. El estado de la cita se conserva; cualquier cambio requiere una acción explícita." : ruta === "optout" ? "Opt-out registrado. El paciente no recibirá nuevas intervenciones en ninguna de sus citas." : "Estado de la intervención actualizado.");
    } catch (fallo) {
      setErrorAccion(mensajeError(fallo));
      if (fallo instanceof ApiError && fallo.status === 409) reintentar();
    } finally { accionEnCurso.current = false; setOcupada(false); }
  }

  function registrarRespuesta(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!disponible("REGISTRAR_RESPUESTA") || !evento.currentTarget.reportValidity()) return;
    const campos = new FormData(evento.currentTarget);
    // RF-062, RF-064, RF-067: este POST nunca llama al cambio de estado de M02.
    void registrar("respuesta", { respuesta_paciente: String(campos.get("respuesta_paciente")), optout: campos.get("optout") === "on" });
  }

  async function liberarCupo(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (accionEnCurso.current || !disponible("LIBERAR_CUPO") || !evento.currentTarget.reportValidity()) return;
    const motivo = String(new FormData(evento.currentTarget).get("motivo") || "").trim();
    accionEnCurso.current = true;
    setOcupada(true); setErrorAccion(""); setExito("");
    try {
      // RF-068, RN04: el servidor libera cita y cupo juntos tras la confirmación.
      const resultado = await api<CupoOut>(`/intervenciones/${id}/liberar-cupo`, { metodo: "POST", json: motivo ? { motivo } : {} });
      if (!resultado) throw new Error("El servidor no devolvió el cupo liberado. Vuelve a consultar antes de repetir la acción.");
      setCupo(resultado); setLiberando(false);
      setExito(`Cupo #${resultado.id_cupo_liberado} liberado. Estado del cupo: ${rotulo(resultado.estado_cupo)}.`);
      if (intervencion) actualizar({ ...intervencion, acciones_disponibles: intervencion.acciones_disponibles.filter((accion) => accion !== "LIBERAR_CUPO") });
    } catch (fallo) {
      setLiberando(false); setErrorAccion(mensajeError(fallo));
      if (fallo instanceof ApiError && fallo.status === 409) reintentar();
    } finally { accionEnCurso.current = false; setOcupada(false); }
  }

  const volver = <Link className="enlace-volver" to="/intervenciones">← Volver a intervenciones</Link>;
  if (cargando) return <>{volver}<Cargando texto="Cargando seguimiento…" /></>;
  if (error) return <>{volver}<Mensaje>{error}</Mensaje><button className="boton-secundario" onClick={reintentar}>Reintentar</button></>;
  if (!intervencion) return <>{volver}<Mensaje>No se encontró la intervención.</Mensaje></>;

  return <>
    {volver}
    <div className="pagina-titulo"><div><p className="sobretitulo">INTERVENCIÓN INTELIGENTE</p><h1>Seguimiento de intervención #{intervencion.id_intervencion}</h1><p>Cita {intervencion.id_cita_externa}</p></div><span className="m05-estado">{rotulo(intervencion.estado_intervencion)}</span></div>
    {errorAccion && <Mensaje>{errorAccion}</Mensaje>}
    {exito && <Mensaje tipo="exito">{exito}</Mensaje>}
    <div className="m05-seguimiento">
      <section className="tarjeta" aria-labelledby="m05-datos-titulo">
        <div className="seccion-cabecera"><h2 id="m05-datos-titulo">Datos de la intervención</h2><p>Registro de contacto y respuesta del paciente.</p></div>
        <dl className="m05-datos">
          <div><dt>Cita</dt><dd><Link className="m05-enlace" to={`/citas/${intervencion.id_cita}`}>{intervencion.id_cita_externa}</Link></dd></div>
          <div><dt>Canal de contacto</dt><dd>{rotulo(intervencion.canal_contacto)}</dd></div>
          <div><dt>Plantilla</dt><dd>{intervencion.plantilla_mensaje}</dd></div>
          <div><dt>Operador</dt><dd>{intervencion.id_operador === null ? "No registrado" : `Usuario #${intervencion.id_operador}`}</dd></div>
          <div><dt>Fecha y hora de envío</dt><dd>{formatearFechaHora(intervencion.fecha_hora_envio)}</dd></div>
          <div><dt>Respuesta del paciente</dt><dd>{intervencion.respuesta_paciente ? rotulo(intervencion.respuesta_paciente) : "Sin respuesta registrada"}</dd></div>
          <div><dt>Fecha y hora de respuesta</dt><dd>{intervencion.fecha_hora_respuesta ? formatearFechaHora(intervencion.fecha_hora_respuesta) : "Sin respuesta registrada"}</dd></div>
          <div><dt>Opt-out</dt><dd>{intervencion.consentimiento_optout ? "Sí · bloquea nuevos contactos del paciente" : "No registrado"}</dd></div>
        </dl>
      </section>
      <section className="tarjeta" aria-labelledby="m05-acciones-titulo">
        <h2 id="m05-acciones-titulo">Acciones de seguimiento</h2>
        <p className="m05-ayuda">Registrar una respuesta nunca cambia el estado de la cita.</p>
        {!puedeEscribir ? <p className="m05-ayuda">Tu rol permite consultar el seguimiento. Solo Recepción y Administración pueden registrar cambios.</p> : <>
          {intervencion.acciones_disponibles.length === 0 && <p className="m05-ayuda">No hay acciones disponibles para esta intervención.</p>}
          <div className="m05-acciones">
            {disponible("REGISTRAR_ENVIO") && <button className="boton-secundario" disabled={ocupada} onClick={() => void registrar("estado", { estado_intervencion: "ENVIADA" })}>Registrar envío</button>}
            {disponible("REGISTRAR_ENTREGA") && <button className="boton-secundario" disabled={ocupada} onClick={() => void registrar("estado", { estado_intervencion: "ENTREGADA" })}>Registrar entrega</button>}
            {disponible("REGISTRAR_FALLO") && <button className="boton-secundario" disabled={ocupada} onClick={() => void registrar("estado", { estado_intervencion: "FALLIDA" })}>Registrar fallo</button>}
          </div>
          {disponible("REGISTRAR_RESPUESTA") && <form className="m05-formulario m05-respuesta" onSubmit={registrarRespuesta}>
            <div><label htmlFor="m05-respuesta">Respuesta del paciente</label><select id="m05-respuesta" name="respuesta_paciente" required disabled={ocupada} defaultValue=""><option value="" disabled>Selecciona una respuesta</option>{RESPUESTAS.map((respuesta) => <option key={respuesta} value={respuesta}>{rotulo(respuesta)}</option>)}</select></div>
            <label className="m05-casilla"><input type="checkbox" name="optout" disabled={ocupada} />El paciente solicita no recibir más comunicaciones (opt-out)</label>
            <p className="m05-ayuda">El opt-out impedirá nuevas intervenciones en todas las citas de este paciente.</p>
            <button className="boton" type="submit" disabled={ocupada}>{ocupada ? "Guardando…" : "Registrar respuesta"}</button>
          </form>}
          {disponible("REGISTRAR_OPTOUT") && <div className="m05-optout"><p className="m05-ayuda">Si el paciente retira su consentimiento, registra el opt-out para bloquear nuevas intervenciones en todas sus citas.</p><button className="boton-secundario" disabled={ocupada} onClick={() => void registrar("optout")}>Registrar opt-out</button></div>}
          {disponible("CONFIRMAR_CITA") && intervencion.respuesta_paciente === "CONFIRMA" && <div className="m05-paso-siguiente"><Link className="boton" to={`/citas/${intervencion.id_cita}?id_intervencion=${intervencion.id_intervencion}`}>Ir a confirmar la cita</Link><p className="m05-ayuda">En el detalle, marca la cita como Confirmada y selecciona la intervención #{intervencion.id_intervencion} para asociar la confirmación.</p></div>}
          {disponible("LIBERAR_CUPO") && !cupo && intervencion.respuesta_paciente === "SOLICITA_LIBERACION" && <div className="m05-paso-siguiente"><p className="m05-ayuda">El paciente solicitó liberar su cita. Confirma la liberación para ofrecer el cupo a la lista de espera.</p><button className="boton" disabled={ocupada} onClick={() => setLiberando(true)}>Liberar cupo</button></div>}
        </>}
        {intervencion.respuesta_paciente === "SOLICITA_REPROG" && <div className="m05-paso-siguiente"><Mensaje tipo="info">Gestiónalo en el sistema de agendamiento</Mensaje><p className="m05-ayuda">PrediCitas registra la solicitud. La nueva fecha se acuerda en el sistema externo (RN03).</p></div>}
      </section>
    </div>
    {liberando && <Dialogo titulo="¿Liberar el cupo de esta cita?" cerrar={() => { if (!accionEnCurso.current) setLiberando(false); }}>
      <form className="m05-formulario" onSubmit={liberarCupo}>
        <p>Cita {intervencion.id_cita_externa}. La cita quedará Liberada y su cupo quedará Disponible para la lista de espera.</p>
        <div><label htmlFor="m05-motivo">Motivo de liberación (opcional)</label><textarea id="m05-motivo" name="motivo" maxLength={255} rows={3} disabled={ocupada} /></div>
        <div className="m05-acciones"><button type="button" className="boton-secundario" disabled={ocupada} onClick={() => setLiberando(false)}>Cancelar</button><button type="submit" className="boton" disabled={ocupada}>{ocupada ? "Liberando…" : "Confirmar liberación"}</button></div>
      </form>
    </Dialogo>}
  </>;
}
