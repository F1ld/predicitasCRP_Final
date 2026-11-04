import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { useEffect } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../nucleo/api/cliente";
import { useConsulta } from "../../nucleo/api/useConsulta";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import EstadoBadge from "../../nucleo/componentes/EstadoBadge";
import Icono from "../../nucleo/componentes/Icono";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta, formatearFechaHora } from "../../nucleo/formato/formato";
import DetallePrediccion from "./DetallePrediccion";
import DetalleSecciones from "./DetalleSecciones";
import { mensajeErrorCitas } from "./errores";
import type { CheckInOut, CitaDetalleOut, EstadoDestino, PrediccionOut } from "./tipos";
import { ROLES_ESCRITURA, TRANSICIONES } from "./transiciones";
import "./citas.css";

export default function CitaDetalle() {
  const { id = "" } = useParams();
  // RF-018: cada cita conserva sus propios formularios y mensajes.
  return <Detalle key={id} id={id} />;
}

function diaLima(instante: number): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Lima", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(instante));
}

// RN01, RF-018 a RF-024, RF-104: el servidor confirma cada cambio y su historial.
function Detalle({ id }: { id: string }) {
  const { state } = useLocation();
  const estadoNavegacion: unknown = state;
  const rutaAnterior = typeof estadoNavegacion === "object" && estadoNavegacion !== null && "volver" in estadoNavegacion ? estadoNavegacion.volver : null;
  const volver = typeof rutaAnterior === "string" && rutaAnterior.startsWith("/citas?") ? rutaAnterior : "/citas";
  const { tieneRol } = useAuth();
  const [parametrosConsulta] = useSearchParams();
  const idIntervencionParam = parametrosConsulta.get("id_intervencion");
  const idIntervencionNum = idIntervencionParam && /^[1-9]\d*$/.test(idIntervencionParam.trim()) ? Number(idIntervencionParam.trim()) : null;
  const { datos: cita, cargando, error, reintentar, actualizar } = useConsulta<CitaDetalleOut>(`/citas/${id}`);
  const intervencionOrigen = idIntervencionNum !== null && cita?.intervenciones.some((i) => i.id_intervencion === idIntervencionNum) ? idIntervencionNum : null;
  const [destino, setDestino] = useState<EstadoDestino | "">("");
  const [enviando, setEnviando] = useState(false);
  const [registrandoLlegada, setRegistrandoLlegada] = useState(false);
  const [calculando, setCalculando] = useState(false);
  const [errorCambio, setErrorCambio] = useState("");
  const [errorLlegada, setErrorLlegada] = useState("");
  const [errorPrediccion, setErrorPrediccion] = useState("");
  const [exito, setExito] = useState("");
  const [resultadoRiesgo, setResultadoRiesgo] = useState<PrediccionOut | null>(null);
  const [ahora, setAhora] = useState(() => Date.now());
  const dialogo = useRef<HTMLDialogElement>(null);
  // RF-019 y RF-104: el bloqueo inmediato evita dos eventos antes del render.
  const accionEnCurso = useRef(false);

  // RF-104: actualiza la elegibilidad al pasar la hora o el día en Lima.
  useEffect(() => {
    const reloj = window.setInterval(() => setAhora(Date.now()), 60_000);
    return () => window.clearInterval(reloj);
  }, []);

  function prepararCambio(estado: EstadoDestino) {
    setDestino(estado); setErrorCambio("");
    dialogo.current?.querySelector("form")?.reset();
    dialogo.current?.showModal();
  }

  async function confirmar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (accionEnCurso.current || !destino) return;
    const formulario = evento.currentTarget;
    if (!formulario.reportValidity()) return;
    const campos = new FormData(formulario);
    const motivo = String(campos.get("motivo") || "").trim();
    const peticion: { estado_nuevo: EstadoDestino; motivo: string | null; nueva_fecha_hora_cita?: string; liberar_cupo?: boolean; id_intervencion?: number } = { estado_nuevo: destino, motivo: motivo || null };
    // RF-021 a RF-024: los campos de un destino nunca se envían para otro.
    if (destino === "REPROGRAMADA") peticion.nueva_fecha_hora_cita = `${String(campos.get("nueva_fecha_hora_cita"))}:00-05:00`;
    if (destino === "CANCELADA" && campos.get("liberar_cupo") === "on") peticion.liberar_cupo = true;
    if (destino === "CONFIRMADA" && campos.get("id_intervencion")) peticion.id_intervencion = Number(campos.get("id_intervencion"));
    accionEnCurso.current = true;
    setEnviando(true); setErrorCambio(""); setExito("");
    try {
      const nueva = await api<CitaDetalleOut>(`/citas/${id}/estado`, { metodo: "POST", json: peticion });
      if (!nueva) throw new Error("El servidor no devolvió el estado actualizado.");
      actualizar(nueva); setExito(`Estado actualizado a ${etiqueta(destino)}.`);
      formulario.reset(); dialogo.current?.close();
      // RF-019: el GET vuelve a consultar el estado persistido después del POST.
      try {
        const persistida = await api<CitaDetalleOut>(`/citas/${id}`);
        if (!persistida) throw new Error("El servidor no devolvió el detalle.");
        actualizar(persistida);
      } catch (fallo) { setErrorCambio(`El cambio se guardó, pero no se pudo refrescar el detalle: ${mensajeErrorCitas(fallo)}`); }
    } catch (fallo) {
      dialogo.current?.close(); setErrorCambio(mensajeErrorCitas(fallo));
      if (fallo instanceof ApiError && fallo.status === 409) reintentar();
    } finally { accionEnCurso.current = false; setEnviando(false); }
  }

  async function registrarLlegada(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (accionEnCurso.current || !cita) return;
    const observacion = String(new FormData(evento.currentTarget).get("observacion") || "").trim();
    accionEnCurso.current = true;
    setRegistrandoLlegada(true); setErrorLlegada(""); setExito("");
    try {
      const llegada = await api<CheckInOut>(`/citas/${id}/check-in`, { metodo: "POST", json: { observacion: observacion || null } });
      if (!llegada) throw new Error("El servidor no devolvió el check-in registrado.");
      actualizar({ ...cita, check_in: llegada });
      setExito("Llegada registrada (check-in). El estado de la cita se conserva.");
    } catch (fallo) {
      setErrorLlegada(mensajeErrorCitas(fallo));
      if (fallo instanceof ApiError && fallo.status === 409) reintentar();
    } finally { accionEnCurso.current = false; setRegistrandoLlegada(false); }
  }

  // RF-052, RF-056, RF-098, RF-103, RN16: el resultado no cambia el estado de cita.
  async function calcularRiesgo() {
    if (accionEnCurso.current || !cita) return;
    accionEnCurso.current = true;
    setCalculando(true); setErrorPrediccion(""); setResultadoRiesgo(null);
    try {
      // Inferencia vía endpoint estándar o alias de citas
      let resultado: PrediccionOut | null = null;
      try {
        resultado = await api<PrediccionOut>(`/ia/predecir/${id}`, { metodo: "POST" });
      } catch {
        resultado = await api<PrediccionOut>(`/citas/${id}/prediccion`, { metodo: "POST" });
      }
      if (!resultado) throw new Error("El servidor no devolvió la predicción.");
      setResultadoRiesgo(resultado);
      // RF-018, RF-057, RF-099: la predicción más reciente encabeza el historial
      const predicciones = [resultado, ...cita.predicciones.filter((previa) => previa.id_prediccion !== resultado.id_prediccion)]
        .sort((a, b) => new Date(b.fecha_hora_inferencia).getTime() - new Date(a.fecha_hora_inferencia).getTime() || b.id_prediccion - a.id_prediccion);
      actualizar({ ...cita, predicciones });
    } catch (fallo) { setErrorPrediccion(mensajeErrorCitas(fallo)); }
    finally { accionEnCurso.current = false; setCalculando(false); }
  }

  if (cargando) return <Cargando texto="Cargando detalle de la cita…" />;
  if (error) return <div className="space-y-4"><Link className="text-teal-800 underline" to={volver}>Volver a la bandeja</Link><Mensaje>{error}</Mensaje><button className="boton-secundario" onClick={reintentar}>Reintentar</button></div>;
  if (!cita) return <div className="space-y-4"><Link className="enlace-volver" to={volver}>← Volver a la bandeja</Link><Mensaje>No se encontró la cita.</Mensaje></div>;

  const opciones = TRANSICIONES[cita.estado_actual];
  const puedeEscribir = tieneRol(...ROLES_ESCRITURA);
  const activa = opciones.length > 0;
  const citaFutura = new Date(cita.fecha_hora_cita).getTime() > ahora;
  const citaHoy = diaLima(new Date(cita.fecha_hora_cita).getTime()) === diaLima(ahora);
  const ocupada = enviando || registrandoLlegada || calculando;
  const ultimaPrediccion = cita.predicciones[0];

  // RF-057, RN07: M05 valida además opt-out de otras citas y modo sombra.
  const puedeIntervenir = puedeEscribir && activa && citaFutura && ultimaPrediccion && ultimaPrediccion.nivel_riesgo !== "BAJO"
    && !cita.intervenciones.some((intervencion) => intervencion.consentimiento_optout)
    && (cita.intervenciones.length === 0 || (cita.intervenciones.length === 1 && cita.intervenciones[0].estado_intervencion === "FALLIDA"));

  const campos: [string, ReactNode][] = [
    ["Identificador interno", cita.id_cita], ["Paciente (seudónimo)", cita.paciente_anon_id],
    ["Sede", etiqueta(cita.sede)], ["Especialidad", etiqueta(cita.especialidad)], ["Médico", cita.medico],
    ["Fecha y hora", formatearFechaHora(cita.fecha_hora_cita)], ["Registro", formatearFechaHora(cita.fecha_registro_cita)],
    ["Antelación", `${cita.antelacion_dias} días`], ["Tipo de paciente", cita.tipo_paciente],
    ["Canal de origen", cita.canal_origen], ["Franja", etiqueta(cita.franja_horaria)], ["Día", cita.dia_semana],
    ["Asistencias previas", cita.asistencias_previas], ["Inasistencias previas", cita.inasistencias_previas],
    ["Reprogramaciones previas", cita.reprogramaciones_prev],
  ];

  // Clases cromáticas clínicas para botones de acción según estado destino
  const estiloBotonEstado = (estado: EstadoDestino) => {
    switch (estado) {
      case "CONFIRMADA":
        return "boton-accion-confirmada";
      case "REPROGRAMADA":
        return "boton-accion-reprogramada";
      case "CANCELADA":
        return "boton-accion-cancelada";
      case "NO_SHOW":
        return "boton-accion-noshow";
      default:
        return "boton-secundario";
    }
  };

  return (
    <div className="cita-detalle-contenedor space-y-6">
      {/* Navegación y Encabezado principal */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Link className="enlace-volver" to={volver}>← Volver a la bandeja</Link>
        <div className="flex items-center gap-3">
          <a href="#historial-estados" className="text-xs font-semibold text-slate-600 hover:text-teal-800 underline">
            Ir a historial de estados
          </a>
          <Link to={`/citas/${id}/trazabilidad`} className="boton-accion-trazabilidad">
            <Icono nombre="reloj" /> Ver trazabilidad completa
          </Link>
        </div>
      </div>

      <header className="tarjeta bg-slate-50 border-teal-800/15">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="sobretitulo">GESTIÓN CLÍNICA Y ASISTENCIAL</p>
            <h1 className="text-2xl font-bold text-slate-900 break-words">Cita {cita.id_cita_externa}</h1>
            <p className="text-sm text-slate-600 mt-1">
              <span className="font-semibold text-slate-800">{etiqueta(cita.especialidad)}</span> · {formatearFechaHora(cita.fecha_hora_cita)} · Dr(a). {cita.medico}
            </p>
          </div>
          <div className="text-right">
            <span className="text-xs text-slate-500 uppercase tracking-wider block mb-1">Estado de cita</span>
            <EstadoBadge estado={cita.estado_actual} />
          </div>
        </div>
      </header>

      {intervencionOrigen !== null && (
        <Mensaje tipo="info">
          Vienes de la intervención #{intervencionOrigen}. Para registrar la confirmación del paciente, presiona &quot;Confirmar Asistencia&quot;.
        </Mensaje>
      )}
      {errorCambio && <Mensaje>{errorCambio}</Mensaje>}
      {exito && <Mensaje tipo="exito">{exito}</Mensaje>}

      {/* BLOQUE SUPERIOR CLÍNICO (GRID 2 COLUMNAS): DATOS + PREDICCIÓN IA Y ACCIONES */}
      <div className="grid items-start gap-6 lg:grid-cols-12">
        {/* Columna Izquierda: Datos Asistenciales de la Cita */}
        <section className="tarjeta lg:col-span-7" aria-labelledby="titulo-datos">
          <div className="seccion-cabecera border-b border-slate-100 pb-3 mb-4">
            <h2 id="titulo-datos" className="text-base font-bold flex items-center gap-2 text-slate-900">
              <Icono nombre="calendario" /> Datos de la Cita Médica
            </h2>
            <p className="text-xs text-slate-500">Parámetros registrados en el sistema asistencial de San Isidro.</p>
          </div>
          <dl className="datos-cita">
            {campos.map(([nombre, valor]) => (
              <div key={nombre}>
                <dt>{nombre}</dt>
                <dd>{valor}</dd>
              </div>
            ))}
          </dl>
          <div className="desenlace-cita mt-4 pt-3 border-t border-slate-200">
            <p className="text-xs font-semibold text-slate-500 uppercase">Desenlace Asistencial (target_no_show)</p>
            <p className="mt-1 text-sm font-medium">
              {cita.target_no_show === null
                ? "— Pendiente de desenlace clínico"
                : cita.target_no_show === 0
                ? "✓ 0 · Paciente Asistió a consulta"
                : "✗ 1 · Paciente No Asistió (No-Show)"}
            </p>
          </div>
        </section>

        {/* Columna Derecha: Predicción IA LightGBM en Primer Golpe de Vista + Acciones */}
        <div className="space-y-6 lg:col-span-5">
          {/* TARJETA DESTACADA: MOTOR PREDICTIVO IA */}
          <section className="tarjeta tarjeta-ia-destacada" aria-labelledby="titulo-prediccion-ia">
            <div className="seccion-cabecera mb-3">
              <div className="flex items-center justify-between">
                <h2 id="titulo-prediccion-ia" className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-teal-600 animate-pulse" />
                  Predicción de Inasistencia (IA)
                </h2>
                {puedeEscribir && activa && citaFutura && (
                  <button
                    className="boton-ia-calcular"
                    disabled={ocupada}
                    onClick={calcularRiesgo}
                    title="Calcular inferencia en tiempo real con LightGBM"
                  >
                    {calculando ? "Evaluando con IA…" : "Recalcular IA"}
                  </button>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Modelo LightGBM v1.0.0 · Clasificación basada en historial y antelación.
              </p>
            </div>

            {errorPrediccion && <div className="mb-3"><Mensaje>{errorPrediccion}</Mensaje></div>}
            {resultadoRiesgo && (
              <div className="mb-3">
                <Mensaje tipo="exito">
                  {resultadoRiesgo.ya_existia
                    ? "Inferencia ya disponible para esta cita; no se duplicaron registros."
                    : "Inferencia calculada exitosamente por LightGBM."}
                </Mensaje>
              </div>
            )}

            {ultimaPrediccion ? (
              <DetallePrediccion prediccion={ultimaPrediccion} destacado={true} />
            ) : (
              <div className="p-4 text-center border border-dashed border-slate-300 rounded-lg bg-slate-50/70">
                <p className="text-sm text-slate-600 font-medium">No hay evaluación predictiva generada.</p>
                <p className="text-xs text-slate-500 mt-1">Presiona el botón para inferir la probabilidad de inasistencia.</p>
                {puedeEscribir && activa && citaFutura && (
                  <button
                    className="boton mt-3 text-xs py-2 px-4"
                    disabled={ocupada}
                    onClick={calcularRiesgo}
                  >
                    {calculando ? "Calculando riesgo…" : "Ejecutar Motor Predictivo LightGBM"}
                  </button>
                )}
              </div>
            )}
          </section>

          {/* TARJETA ACCIONES ASISTENCIALES CON ESTILO CLÍNICO */}
          <section className="tarjeta acciones-cita" aria-labelledby="titulo-acciones">
            <div className="seccion-cabecera border-b border-slate-100 pb-2 mb-3">
              <h2 id="titulo-acciones" className="text-base font-bold text-slate-900">
                Acciones de Gestión Asistencial
              </h2>
              <p className="text-xs text-slate-500">Transiciones formales de estado y trazabilidad.</p>
            </div>

            {!puedeEscribir && (
              <p className="text-sm text-slate-600">Tu rol permite consultar la cita. No tienes permiso para cambiar su estado.</p>
            )}

            {!activa ? (
              <div className="p-3 bg-slate-100 rounded-md text-xs text-slate-700">
                <strong>Estado final inmutable:</strong> Esta cita ha alcanzado un estado de cierre y no admite modificaciones posteriores.
              </div>
            ) : puedeEscribir && (
              <div className="flex flex-col gap-2.5">
                {opciones.map((estado) => (
                  <button
                    key={estado}
                    className={`boton-transicion ${estiloBotonEstado(estado)}`}
                    disabled={ocupada}
                    onClick={() => prepararCambio(estado)}
                  >
                    Marcar como {etiqueta(estado)}
                  </button>
                ))}
              </div>
            )}

            <div className="citas-vinculos-acciones mt-4 pt-3 border-t border-slate-200 flex flex-col gap-2">
              <Link className="boton-enlace-trazabilidad" to={`/citas/${id}/trazabilidad`}>
                <Icono nombre="reloj" /> Abrir bitácora de trazabilidad
              </Link>
              {puedeIntervenir && (
                <Link className="boton-enlace-intervencion" to={`/intervenciones?id_cita=${id}`}>
                  Crear intervención preventiva (WhatsApp / Llamada)
                </Link>
              )}
            </div>
          </section>
        </div>
      </div>

      {/* SECCIÓN CHECK-IN (RECEPCIÓN SAN ISIDRO) */}
      <section className="tarjeta" aria-labelledby="titulo-check-in">
        <div className="seccion-cabecera">
          <h2 id="titulo-check-in" className="flex items-center gap-2 text-base font-bold text-slate-900">
            <Icono nombre="check" /> Registro de Llegada (Check-in Asistencial)
          </h2>
          <p className="text-xs text-slate-500">Acredita la presencia física del paciente en sala de espera sin alterar el estado clínico de la cita.</p>
        </div>
        {errorLlegada && <Mensaje>{errorLlegada}</Mensaje>}
        {cita.check_in ? (
          <dl className="datos-cita mt-3">
            <div>
              <dt>Hora de llegada confirmada</dt>
              <dd className="font-semibold text-teal-900">{formatearFechaHora(cita.check_in.fecha_hora_check_in)}</dd>
            </div>
            <div>
              <dt>Recepción</dt>
              <dd>Operador #{cita.check_in.id_usuario}</dd>
            </div>
            {cita.check_in.observacion && (
              <div>
                <dt>Observaciones</dt>
                <dd>{cita.check_in.observacion}</dd>
              </div>
            )}
          </dl>
        ) : (
          <div className="mt-3">
            <p className="citas-seccion-vacia">No se ha registrado check-in para esta cita.</p>
            {puedeEscribir && activa && (
              <form onSubmit={registrarLlegada} className="mt-4 space-y-3">
                {!citaHoy && (
                  <p id="ayuda-check-in" className="text-xs text-amber-700 bg-amber-50 p-2 rounded border border-amber-200">
                    Nota: El check-in asistencial se registra exclusivamente el día de la cita (Horario de Lima).
                  </p>
                )}
                <div>
                  <label htmlFor="observacion-check-in" className="text-xs font-semibold text-slate-700 block mb-1">
                    Observación de recepción (opcional)
                  </label>
                  <textarea
                    id="observacion-check-in"
                    name="observacion"
                    maxLength={255}
                    rows={2}
                    disabled={ocupada || !citaHoy}
                    placeholder="Ej. Paciente llegó acompañado, derivado a triaje"
                    className="w-full text-xs"
                  />
                </div>
                <button
                  type="submit"
                  className="boton"
                  disabled={ocupada || !citaHoy}
                  aria-describedby={!citaHoy ? "ayuda-check-in" : undefined}
                >
                  {registrandoLlegada ? "Registrando en recepción…" : "Confirmar llegada del paciente (Check-in)"}
                </button>
              </form>
            )}
          </div>
        )}
      </section>

      {/* HISTORIAL COMPLETO DE PREDICCIONES (SI EXISTE MÁS DE UNA) */}
      {cita.predicciones.length > 1 && (
        <section className="tarjeta" aria-labelledby="titulo-historial-predicciones">
          <div className="seccion-cabecera mb-3">
            <h2 id="titulo-historial-predicciones" className="text-base font-bold text-slate-900">
              Historial de Inferencia IA ({cita.predicciones.length} evaluaciones)
            </h2>
            <p className="text-xs text-slate-500">Integredad de predicciones generadas previamente para esta cita.</p>
          </div>
          <ol className="citas-lista-detalle">
            {cita.predicciones.slice(1).map((prediccion) => (
              <li key={prediccion.id_prediccion}>
                <DetallePrediccion prediccion={prediccion} />
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* MÓDULOS ASOCIADOS (INTERVENCIONES, CUPOS Y REASIGNACIONES) */}
      <DetalleSecciones cita={cita} />

      {/* BITÁCORA LOCAL DE ESTADOS (TIMELINE ANCLABLE) */}
      <section id="historial-estados" className="tarjeta" aria-labelledby="titulo-historial">
        <div className="seccion-cabecera flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
          <div>
            <h2 id="titulo-historial" className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Icono nombre="reloj" /> Historial de Estados de la Cita
            </h2>
            <p className="text-xs text-slate-500">Transiciones ordenadas desde el cambio más reciente.</p>
          </div>
          <Link to={`/citas/${id}/trazabilidad`} className="text-xs text-teal-800 font-bold hover:underline">
            Ver pantalla completa de auditoría →
          </Link>
        </div>
        <ol className="historial-cita">
          {[...cita.historial].reverse().map((evento) => (
            <li key={evento.id_historial} className="pb-3 mb-3 border-b border-slate-100 last:border-b-0">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-slate-800">
                  {etiqueta(evento.estado_anterior)} <span className="text-slate-400">→</span> {etiqueta(evento.estado_nuevo)}
                </p>
                <span className="text-xs text-slate-500">{formatearFechaHora(evento.fecha_hora_evento)}</span>
              </div>
              <p className="mt-0.5 text-xs text-slate-500">
                {evento.id_usuario_actor === null ? "Actor no registrado" : `Operador #${evento.id_usuario_actor}`}
              </p>
              <p className="mt-1.5 break-words text-xs text-slate-700 bg-slate-50 p-2 rounded">
                {evento.motivo_cambio || "Sin observaciones adicionales"}
              </p>
            </li>
          ))}
        </ol>
        {cita.historial.length === 0 && <p className="citas-seccion-vacia">No hay transiciones registradas.</p>}
      </section>

      {/* DIÁLOGO MODAL PARA CAMBIOS DE ESTADO */}
      <dialog
        ref={dialogo}
        aria-labelledby="titulo-cambio"
        aria-describedby="ayuda-cambio"
        onCancel={(evento) => { if (enviando) evento.preventDefault(); }}
        className="dialogo-cambio"
      >
        <form onSubmit={confirmar} className="space-y-4">
          <h2 id="titulo-cambio" className="text-lg font-bold text-slate-900">
            ¿Confirmar transición a {etiqueta(destino)}?
          </h2>
          <p id="ayuda-cambio" className="text-xs text-slate-600">
            Cita {cita.id_cita_externa}. Los estados finales son inmutables y no admiten reversión.
          </p>
          {destino === "REPROGRAMADA" && (
            <div>
              <label htmlFor="nueva-fecha-cita" className="text-xs font-bold text-slate-700 block mb-1">
                Nueva fecha y hora acordada (Lima)
              </label>
              <input
                id="nueva-fecha-cita"
                name="nueva_fecha_hora_cita"
                type="datetime-local"
                required
                disabled={enviando}
                aria-describedby="ayuda-reprogramacion"
                className="w-full text-xs"
              />
              <p id="ayuda-reprogramacion" className="mt-1 text-[11px] text-slate-500">
                Registra la fecha acordada con el paciente en el sistema externo.
              </p>
            </div>
          )}
          {destino === "CANCELADA" && citaFutura && (
            <label className="citas-check-control text-xs font-semibold text-slate-800">
              <input type="checkbox" name="liberar_cupo" disabled={enviando} />
              Liberar cupo para reasignación en lista de espera (M06)
            </label>
          )}
          {destino === "CONFIRMADA" && (
            <div>
              <label htmlFor="intervencion-confirmacion" className="text-xs font-bold text-slate-700 block mb-1">
                Intervención asistencial asociada (opcional)
              </label>
              <select
                id="intervencion-confirmacion"
                name="id_intervencion"
                disabled={enviando}
                defaultValue={intervencionOrigen ?? ""}
                className="w-full text-xs"
              >
                <option value="">Sin intervención asociada directa</option>
                {cita.intervenciones.map((intervencion) => (
                  <option key={intervencion.id_intervencion} value={intervencion.id_intervencion}>
                    #{intervencion.id_intervencion} · {intervencion.canal_contacto} · {intervencion.respuesta_paciente || "Sin respuesta"}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div>
            <label htmlFor="motivo" className="text-xs font-bold text-slate-700 block mb-1">
              Motivo o justificación clínica (opcional)
            </label>
            <textarea
              id="motivo"
              name="motivo"
              maxLength={255}
              rows={3}
              disabled={enviando}
              placeholder="Indica la razón del cambio de estado para la auditoría interna"
              className="w-full text-xs"
            />
          </div>
          <div className="flex flex-wrap justify-end gap-2 pt-2 border-t border-slate-200">
            <button
              type="button"
              className="boton-secundario text-xs"
              disabled={enviando}
              onClick={() => dialogo.current?.close()}
            >
              Cancelar
            </button>
            <button className="boton text-xs" disabled={enviando} type="submit">
              {enviando ? "Guardando cambio…" : "Confirmar transición"}
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
