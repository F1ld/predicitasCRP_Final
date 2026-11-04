import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import Cargando from "../components/Cargando";
import EstadoBadge from "../components/EstadoBadge";
import Mensaje from "../components/Mensaje";
import { api } from "../lib/api";
import { etiqueta, formatearFechaHora } from "../lib/formato";
import { ROLES_ESCRITURA, TRANSICIONES } from "../lib/transiciones";
import { useConsulta } from "../lib/useConsulta";
import Icono from "../components/Icono";

function limpiarTextoClinico(texto) {
  if (!texto) return "";
  return String(texto).replace(/\s*\[Simulado\]/gi, "").replace(/\s*\((?:RF|RN|RNF)[^)]*\)/gi, "").trim();
}

export default function CitaDetalle() {
  const { id } = useParams();
  return <Detalle key={id} id={id} />;
}

function Detalle({ id }) {
  const { state } = useLocation();
  const volver = typeof state?.volver === "string" && state.volver.startsWith("/citas?") ? state.volver : "/citas";
  const { tieneRol } = useAuth();
  const { datos: cita, cargando, error, reintentar, actualizar } = useConsulta(`/citas/${id}`);
  const [destino, setDestino] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [errorCambio, setErrorCambio] = useState("");
  const [exito, setExito] = useState("");
  const [prediccion, setPrediccion] = useState(null);
  const [evaluandoIA, setEvaluandoIA] = useState(false);
  const dialogo = useRef(null);

  useEffect(() => {
    let activo = true;
    api(`/ia/predicciones/${id}`)
      .then((res) => { if (activo && res && res.length > 0) setPrediccion(res[0]); })
      .catch(() => {});
    return () => { activo = false; };
  }, [id]);

  async function evaluarIA() {
    setEvaluandoIA(true); setErrorCambio(""); setExito("");
    try {
      const pred = await api(`/ia/predecir/${id}`, { metodo: "POST" });
      setPrediccion(pred);
      setExito(`Evaluación completada: Riesgo ${pred.nivel_riesgo} (${(Number(pred.probabilidad_no_show) * 100).toFixed(1)}%).`);
    } catch (fallo) {
      setErrorCambio(fallo.message);
    } finally {
      setEvaluandoIA(false);
    }
  }

  function prepararCambio(estado) {
    setDestino(estado);
    dialogo.current.showModal();
  }

  async function confirmar(evento) {
    evento.preventDefault();
    if (enviando) return;
    const formulario = evento.currentTarget;
    const motivo = String(new FormData(formulario).get("motivo") || "").trim();
    setEnviando(true); setErrorCambio(""); setExito("");
    try {
      const nueva = await api(`/citas/${id}/estado`, { metodo: "POST", json: { estado_nuevo: destino, motivo: motivo || null } });
      actualizar(nueva);
      setExito(`Estado actualizado a ${etiqueta(destino)}.`);
      formulario.reset();
      dialogo.current?.close();
      try { actualizar(await api(`/citas/${id}`)); }
      catch (fallo) { setErrorCambio(`El cambio se guardó, pero no se pudo refrescar el detalle: ${fallo.message}`); }
    } catch (fallo) {
      dialogo.current?.close();
      setErrorCambio(fallo.status === 409 ? `La cita ya no admite ese cambio. ${fallo.message}` : fallo.message);
      if (fallo.status === 409) reintentar();
    } finally { setEnviando(false); }
  }

  if (cargando) return <Cargando texto="Cargando detalle…" />;
  if (error) return <div className="space-y-4"><Link className="text-teal-800 underline" to={volver}>Volver a la bandeja</Link><Mensaje>{error}</Mensaje><button className="boton-secundario" onClick={reintentar}>Reintentar</button></div>;
  const opciones = TRANSICIONES[cita.estado_actual] || [];
  const campos = [
    ["Identificador interno", cita.id_cita], ["Código de paciente", cita.paciente_anon_id],
    ["Sede", etiqueta(cita.sede)], ["Especialidad", etiqueta(cita.especialidad)], ["Médico tratante", cita.medico],
    ["Fecha y hora de cita", formatearFechaHora(cita.fecha_hora_cita)], ["Fecha de agendamiento", formatearFechaHora(cita.fecha_registro_cita)],
    ["Antelación de reserva", `${cita.antelacion_dias} días`], ["Tipo de paciente", cita.tipo_paciente],
    ["Canal de agendamiento", cita.canal_origen], ["Turno horario", etiqueta(cita.franja_horaria)], ["Día de atención", cita.dia_semana],
    ["Asistencias previas", cita.asistencias_previas], ["Inasistencias previas", cita.inasistencias_previas],
    ["Reprogramaciones previas", cita.reprogramaciones_prev],
  ];
  return <>
    <Link className="enlace-volver" to={volver}>← Volver a la bandeja</Link>
    <div className="pagina-titulo"><div><p className="sobretitulo">DETALLE Y SEGUIMIENTO DE ATENCIÓN</p><h1 className="break-words">Cita {cita.id_cita_externa}</h1><p>{etiqueta(cita.especialidad)} <span aria-hidden="true">·</span> {formatearFechaHora(cita.fecha_hora_cita)}</p></div><EstadoBadge estado={cita.estado_actual} /></div>
    {errorCambio && <Mensaje>{errorCambio}</Mensaje>}{exito && <Mensaje tipo="exito">{exito}</Mensaje>}
    <div className="grid items-start gap-6 lg:grid-cols-3">
      <section className="tarjeta lg:col-span-2"><div className="seccion-cabecera"><h2><Icono nombre="calendario" />Información de la cita médica</h2><p>Datos clínicos y administrativos registrados en la sede.</p></div>
        <dl className="datos-cita">{campos.map(([nombre, valor]) => <div key={nombre}><dt>{nombre}</dt><dd>{valor}</dd></div>)}</dl>
        <div className="desenlace-cita"><p className="font-semibold">Resultado de asistencia</p>
          <p className="mt-1">{cita.target_no_show === null ? "— Pendiente de atención médica" : cita.target_no_show === 0 ? "Paciente asistió a su cita" : "Inasistencia registrada (No-Show)"}</p>
        </div>
      </section>
      <div className="space-y-6">
        <section className="tarjeta space-y-3">
          <div className="seccion-cabecera">
            <h2><Icono nombre="exito" />Evaluación Predictiva de Asistencia</h2>
            <p>Estimación de riesgo de inasistencia y factores asociados.</p>
          </div>
          {prediccion ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-600">Nivel de riesgo estimado:</span>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                  prediccion.nivel_riesgo === "ALTO" ? "bg-rose-100 text-rose-900" :
                  prediccion.nivel_riesgo === "MEDIO" ? "bg-amber-100 text-amber-900" :
                  "bg-emerald-100 text-emerald-900"
                }`}>{prediccion.nivel_riesgo}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-600">Probabilidad de inasistencia:</span>
                <span className="font-mono font-bold text-slate-900">{(Number(prediccion.probabilidad_no_show) * 100).toFixed(1)}%</span>
              </div>
              <div className="rounded bg-slate-50 p-2.5 text-xs text-slate-700 border border-slate-200">
                <p className="font-semibold text-slate-900 mb-1">Principales factores identificados:</p>
                <p>{limpiarTextoClinico(prediccion.explicabilidad_resumen)}</p>
              </div>
              <p className="text-xs text-slate-400">Modelo predictivo: {prediccion.version_modelo.replace("_", " ")}</p>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Aún no se ha calculado el riesgo de inasistencia para esta cita.</p>
          )}
          <button className="boton-secundario w-full text-xs" disabled={evaluandoIA} onClick={evaluarIA}>
            {evaluandoIA ? "Calculando…" : prediccion ? "Actualizar Evaluación Predictiva" : "Calcular Riesgo de Inasistencia"}
          </button>
        </section>

        <section className="tarjeta acciones-cita"><h2>Acciones operativas</h2><p className="ayuda-seccion">Actualiza el estado de la cita cuando cuentes con la confirmación correspondiente.</p>
          {opciones.length === 0 ? <p className="mt-4 text-sm text-slate-600">Estado final: no admite más cambios.</p> : !tieneRol(...ROLES_ESCRITURA) ? <p className="mt-4 text-sm text-slate-600">Tu perfil permite consultar la cita. No tienes permiso para modificar su estado.</p> : <div className="mt-4 flex flex-col gap-2">{opciones.map((estado) => <button key={estado} className="boton-secundario" disabled={enviando} onClick={() => prepararCambio(estado)}>Marcar como {etiqueta(estado)}</button>)}</div>}
        </section>
      </div>
    </div>
    <section className="tarjeta"><div className="seccion-cabecera"><h2><Icono nombre="reloj" />Historial de cambios de estado</h2><p>Registro cronológico de la cita, desde el movimiento más reciente.</p></div>
      <ol className="historial-cita">{[...cita.historial].reverse().map((evento) => <li key={evento.id_historial}>
        <p className="text-sm font-semibold">{etiqueta(evento.estado_anterior)} → {etiqueta(evento.estado_nuevo)}</p>
        <p className="mt-1 text-xs text-slate-500">{formatearFechaHora(evento.fecha_hora_evento)} · {evento.id_usuario_actor === null ? "Sistema" : `Colaborador #${evento.id_usuario_actor}`}</p>
        <p className="mt-2 break-words text-sm text-slate-600">{evento.motivo_cambio || "Sin observación adicional"}</p>
      </li>)}</ol>
      {cita.historial.length === 0 && <p className="mt-4 text-sm text-slate-500">No hay transiciones registradas.</p>}
    </section>
    <dialog ref={dialogo} aria-labelledby="titulo-cambio" onCancel={(evento) => { if (enviando) evento.preventDefault(); }} className="dialogo-cambio">
      <form onSubmit={confirmar} className="space-y-4">
        <h2 id="titulo-cambio">¿Cambiar a {etiqueta(destino)}?</h2>
        <p className="text-sm text-slate-600">Cita {cita.id_cita_externa}. Los estados finales de atención no admiten cambios posteriores.</p>
        <div><label htmlFor="motivo">Motivo u observación (opcional)</label><textarea id="motivo" name="motivo" maxLength={255} rows={3} disabled={enviando} /></div>
        <div className="flex flex-wrap justify-end gap-2"><button type="button" className="boton-secundario" disabled={enviando} onClick={() => dialogo.current.close()}>Cancelar</button><button className="boton" disabled={enviando} type="submit">{enviando ? "Guardando…" : "Confirmar cambio"}</button></div>
      </form>
    </dialog>
  </>;
}
