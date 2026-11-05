import { Link, useParams } from "react-router-dom";
import { useConsulta } from "../../nucleo/api/useConsulta";
import Cargando from "../../nucleo/componentes/Cargando";
import EstadoBadge from "../../nucleo/componentes/EstadoBadge";
import Icono from "../../nucleo/componentes/Icono";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta, formatearFechaHora } from "../../nucleo/formato/formato";
import type { CitaDetalleOut } from "./tipos";
import "./citas.css";

/**
 * Vista de Trazabilidad y Bitácora de la Cita (RF-018, RF-024, RF-104)
 * Muestra el recorrido cronológico completo, transiciones de estado, actores y eventos clínicos asociados.
 */
export default function TrazabilidadCita() {
  const { id = "" } = useParams();
  const { datos: cita, cargando, error, reintentar } = useConsulta<CitaDetalleOut>(`/citas/${id}`);

  if (cargando) return <Cargando texto="Cargando trazabilidad de la cita…" />;
  if (error) {
    return (
      <div className="space-y-4">
        <Link className="enlace-volver" to={`/citas/${id}`}>← Volver al detalle de la cita</Link>
        <Mensaje>{error}</Mensaje>
        <button className="boton-secundario" onClick={reintentar}>Reintentar</button>
      </div>
    );
  }
  if (!cita) {
    return (
      <div className="space-y-4">
        <Link className="enlace-volver" to="/citas">← Volver a la bandeja</Link>
        <Mensaje>No se encontró la cita solicitada.</Mensaje>
      </div>
    );
  }

  const eventosOrdenados = [...cita.historial].sort(
    (a, b) => new Date(b.fecha_hora_evento).getTime() - new Date(a.fecha_hora_evento).getTime() || b.id_historial - a.id_historial
  );

  return (
    <div className="trazabilidad-contenedor space-y-6">
      <nav aria-label="Navegación de retorno">
        <Link className="enlace-volver" to={`/citas/${id}`}>← Volver al detalle de la cita {cita.id_cita_externa}</Link>
      </nav>

      {/* Encabezado clínico */}
      <header className="tarjeta bg-slate-50 border-teal-700/20">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="sobretitulo">AUDITORÍA Y TRAZABILIDAD CLÍNICA</p>
            <h1 className="text-2xl font-bold text-slate-900">Bitácora de Cita {cita.id_cita_externa}</h1>
            <p className="text-sm text-slate-600 mt-1">
              Paciente (seudónimo): <span className="font-semibold text-slate-800">{cita.paciente_anon_id}</span> · Especialidad: <span className="font-semibold text-slate-800">{etiqueta(cita.especialidad)}</span> · Sede San Isidro
            </p>
          </div>
          <div className="text-right">
            <span className="text-xs text-slate-500 uppercase tracking-wider block mb-1">Estado actual</span>
            <EstadoBadge estado={cita.estado_actual} />
          </div>
        </div>
      </header>

      {/* Resumen de hitos relevantes */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="tarjeta p-4 bg-white border-l-4 border-l-teal-600">
          <p className="text-xs font-semibold text-slate-500 uppercase">Fecha y Hora Programada</p>
          <p className="text-base font-bold text-slate-800 mt-1">{formatearFechaHora(cita.fecha_hora_cita)}</p>
          <p className="text-xs text-slate-500 mt-0.5">Antelación: {cita.antelacion_dias} días</p>
        </div>
        <div className="tarjeta p-4 bg-white border-l-4 border-l-sky-600">
          <p className="text-xs font-semibold text-slate-500 uppercase">Check-in de Llegada</p>
          {cita.check_in ? (
            <>
              <p className="text-base font-bold text-sky-900 mt-1">{formatearFechaHora(cita.check_in.fecha_hora_check_in)}</p>
              <p className="text-xs text-slate-500 mt-0.5">Registrado por Usuario #{cita.check_in.id_usuario}</p>
            </>
          ) : (
            <p className="text-sm text-slate-500 mt-1">Sin check-in registrado</p>
          )}
        </div>
        <div className="tarjeta p-4 bg-white border-l-4 border-l-indigo-600">
          <p className="text-xs font-semibold text-slate-500 uppercase">Total Transiciones</p>
          <p className="text-2xl font-bold text-indigo-900 mt-1">{cita.historial.length}</p>
          <p className="text-xs text-slate-500 mt-0.5">Cambios de estado registrados</p>
        </div>
      </div>

      {/* Línea de tiempo visual (Timeline) */}
      <section className="tarjeta" aria-labelledby="titulo-timeline">
        <div className="seccion-cabecera mb-6">
          <h2 id="titulo-timeline" className="text-lg font-bold flex items-center gap-2">
            <Icono nombre="reloj" /> Línea Cronológica de Estados y Auditoría
          </h2>
          <p className="text-sm text-slate-600">Registro inmutable de transiciones con actor responsable y motivo justificado (RN01, RF-018).</p>
        </div>

        {eventosOrdenados.length === 0 ? (
          <p className="citas-seccion-vacia">No se registran eventos de transición para esta cita.</p>
        ) : (
          <div className="trazabilidad-timeline">
            {eventosOrdenados.map((evento, index) => {
              const esUltimo = index === 0;
              return (
                <div key={evento.id_historial} className={`timeline-nodo ${esUltimo ? "nodo-activo" : ""}`}>
                  <div className="timeline-marcador">
                    <span className="marcador-circulo" />
                  </div>
                  <div className="timeline-contenido tarjeta">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                          {etiqueta(evento.estado_anterior)}
                        </span>
                        <span className="text-slate-400 font-bold">→</span>
                        <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-teal-100 text-teal-800">
                          {etiqueta(evento.estado_nuevo)}
                        </span>
                        {esUltimo && (
                          <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                            Estado Vigente
                          </span>
                        )}
                      </div>
                      <time className="text-xs font-semibold text-slate-600" dateTime={evento.fecha_hora_evento}>
                        {formatearFechaHora(evento.fecha_hora_evento)}
                      </time>
                    </div>

                    <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                      <div>
                        <span className="text-xs text-slate-500 block">Actor responsable</span>
                        <p className="font-medium text-slate-800">
                          {evento.id_usuario_actor !== null ? (
                            `Usuario del sistema #${evento.id_usuario_actor}`
                          ) : (
                            <span className="italic text-slate-500">Transición externa / Piloto CRP</span>
                          )}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs text-slate-500 block">Identificador de evento</span>
                        <p className="font-mono text-xs text-slate-700">Registro #{evento.id_historial}</p>
                      </div>
                    </div>

                    <div className="mt-2.5 bg-slate-50 p-2.5 rounded-md border border-slate-200/60">
                      <span className="text-xs font-semibold text-slate-600 block mb-0.5">Motivo del cambio:</span>
                      <p className="text-xs text-slate-700 whitespace-pre-wrap">
                        {evento.motivo_cambio ? evento.motivo_cambio : "Transición estándar sin observaciones adicionales."}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Bloque de intervenciones y reasignaciones asociadas si aplican */}
      {cita.intervenciones.length > 0 && (
        <section className="tarjeta" aria-labelledby="titulo-intervenciones-traz">
          <div className="seccion-cabecera mb-4">
            <h2 id="titulo-intervenciones-traz" className="text-base font-bold text-slate-900">
              Intervenciones de Contacto Vinculadas ({cita.intervenciones.length})
            </h2>
            <p className="text-xs text-slate-500">Gestiones asistenciales realizadas por el personal de recepción (M05).</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {cita.intervenciones.map((i) => (
              <div key={i.id_intervencion} className="border border-slate-200 rounded-lg p-3 bg-white">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-bold text-slate-800">Intervención #{i.id_intervencion}</span>
                  <span className="px-2 py-0.5 rounded bg-slate-100 font-semibold">{i.canal_contacto}</span>
                </div>
                <p className="text-xs text-slate-600 mt-2">
                  <strong>Estado:</strong> {i.estado_intervencion} · <strong>Respuesta:</strong> {i.respuesta_paciente || "Pendiente"}
                </p>
                <p className="text-xs text-slate-500 mt-1">Envío: {formatearFechaHora(i.fecha_hora_envio)}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

