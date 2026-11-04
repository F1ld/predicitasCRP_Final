import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import Cargando from "../components/Cargando";
import EstadoBadge from "../components/EstadoBadge";
import Icono from "../components/Icono";
import Mensaje from "../components/Mensaje";
import { api } from "../lib/api";
import { etiqueta, formatearFechaHora } from "../lib/formato";
import { ROLES_ESCRITURA } from "../lib/transiciones";
import { useConsulta } from "../lib/useConsulta";

const COLOR_RIESGO = {
  ALTO: "bg-rose-100 text-rose-800 border border-rose-300",
  MEDIO: "bg-amber-100 text-amber-800 border border-amber-300",
  BAJO: "bg-emerald-100 text-emerald-800 border border-emerald-300",
};

function limpiarExplicabilidad(texto) {
  if (!texto) return "";
  return String(texto).replace(/\s*\[Simulado\]/gi, "").replace(/\s*\((?:RF|RN|RNF)[^)]*\)/gi, "").trim();
}

export default function Intervenciones() {
  const { tieneRol } = useAuth();
  const puedeOperar = tieneRol(...ROLES_ESCRITURA);
  const [filtroRiesgo, setFiltroRiesgo] = useState("");
  const [filtroEsp, setFiltroEsp] = useState("");
  const params = new URLSearchParams();
  if (filtroRiesgo) params.set("nivel_riesgo", filtroRiesgo);
  if (filtroEsp) params.set("especialidad", filtroEsp);

  const { datos, cargando, error, reintentar } = useConsulta(`/intervenciones?${params}`);
  const [mensajeExito, setMensajeExito] = useState("");
  const [mensajeError, setMensajeError] = useState("");
  const [procesando, setProcesando] = useState(false);

  async function evaluarLoteIA() {
    setProcesando(true);
    setMensajeError("");
    setMensajeExito("");
    try {
      const res = await api("/ia/predecir-lote", { metodo: "POST" });
      setMensajeExito(
        `Evaluación masiva completada (${res.version_modelo.replace("_", " ")}): ${res.evaluadas} citas analizadas ` +
        `(Riesgo Alto: ${res.riesgo_alto}, Medio: ${res.riesgo_medio}, Bajo: ${res.riesgo_bajo}).`
      );
      reintentar();
    } catch (e) {
      setMensajeError(e.message);
    } finally {
      setProcesando(false);
    }
  }

  async function enviarIntervencion(idCita, canal, optout = false) {
    setProcesando(true);
    setMensajeError("");
    setMensajeExito("");
    try {
      await api(`/citas/${idCita}/intervenciones`, {
        metodo: "POST",
        json: {
          canal_contacto: canal,
          plantilla_mensaje: "PLANTILLA_CONFIRMACION_PREVENTIVA",
          consentimiento_optout: optout,
        },
      });
      setMensajeExito(`Comunicación preventiva enviada por ${etiqueta(canal)} para la cita #${idCita}.`);
      reintentar();
    } catch (e) {
      setMensajeError(e.message);
    } finally {
      setProcesando(false);
    }
  }

  async function registrarRespuesta(idIntervencion, respuestaPaciente, optout = null) {
    setProcesando(true);
    setMensajeError("");
    setMensajeExito("");
    try {
      const res = await api(`/intervenciones/${idIntervencion}`, {
        metodo: "PATCH",
        json: {
          respuesta_paciente: respuestaPaciente,
          consentimiento_optout: optout,
          observacion: `Respuesta registrada en bandeja de recepción: ${respuestaPaciente}`,
        },
      });
      if (respuestaPaciente === "SOLICITA_LIBERACION") {
        setMensajeExito(
          `La cita pasó al estado LIBERADA y el turno #${res.id_cupo_liberado_generado} quedó habilitado como DISPONIBLE para otros pacientes.`
        );
      } else if (respuestaPaciente === "CONFIRMA") {
        setMensajeExito("Asistencia confirmada por el paciente. La cita pasó al estado CONFIRMADA.");
      } else {
        setMensajeExito(`Respuesta registrada. La cita se mantiene vigente en estado '${res.estado_cita_actual}'.`);
      }
      reintentar();
    } catch (e) {
      setMensajeError(e.message);
    } finally {
      setProcesando(false);
    }
  }

  return (
    <>
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">COMUNICACIÓN PREVENTIVA CON EL PACIENTE</p>
          <h1>Bandeja de Intervenciones Preventivas</h1>
          <p>Seguimiento proactivo de citas con riesgo alto y medio de inasistencia para confirmar la atención o liberar turnos oportunamente.</p>
        </div>
        {puedeOperar && (
          <button className="boton" disabled={procesando} onClick={evaluarLoteIA}>
            <Icono nombre="escudo" />
            {procesando ? "Analizando…" : "Evaluar Citas Pendientes con IA"}
          </button>
        )}
      </div>

      {mensajeError && <Mensaje>{mensajeError}</Mensaje>}
      {mensajeExito && <Mensaje tipo="exito">{mensajeExito}</Mensaje>}

      <div className="tarjeta">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label htmlFor="filtro-riesgo">Nivel de riesgo estimado</label>
            <select id="filtro-riesgo" value={filtroRiesgo} onChange={(e) => setFiltroRiesgo(e.target.value)}>
              <option value="">Riesgo Alto y Medio</option>
              <option value="ALTO">Solo Riesgo ALTO (&gt; 45%)</option>
              <option value="MEDIO">Solo Riesgo MEDIO (30% – 45%)</option>
            </select>
          </div>
          <div>
            <label htmlFor="filtro-esp">Especialidad médica</label>
            <select id="filtro-esp" value={filtroEsp} onChange={(e) => setFiltroEsp(e.target.value)}>
              <option value="">Todas las especialidades</option>
              <option value="CARDIOLOGIA">Cardiología</option>
              <option value="TRAUMATOLOGIA">Traumatología</option>
              <option value="PEDIATRIA">Pediatría</option>
            </select>
          </div>
          <button type="button" className="boton-secundario" onClick={reintentar}>
            Actualizar bandeja
          </button>
        </div>
      </div>

      {cargando ? (
        <Cargando texto="Cargando bandeja de seguimiento preventivo…" />
      ) : error ? (
        <Mensaje>{error}</Mensaje>
      ) : (
        <>
          <section className="tarjeta space-y-4">
            <div className="seccion-cabecera">
              <h2>
                <Icono nombre="calendario" /> Citas Priorizadas para Contacto Preventivo{" "}
                <span className="contador-citas">{datos.total_sugeridas}</span>
              </h2>
              <p>Política de atención al paciente: máximo 1 recordatorio preventivo por cita y respeto a la solicitud de no contacto.</p>
            </div>

            <div className="tabla-contenedor">
              <table className="w-full tabla-citas">
                <thead>
                  <tr>
                    <th>Cita / Paciente</th>
                    <th>Especialidad y Fecha</th>
                    <th>Riesgo Estimado</th>
                    <th>Factores Clave del Riesgo</th>
                    <th>Estado / Contacto</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {datos.citas_sugeridas.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-6 text-center text-sm text-slate-600">
                        No hay citas en riesgo alto o medio pendientes de evaluación. Pulsa «Evaluar Citas Pendientes con IA».
                      </td>
                    </tr>
                  ) : (
                    datos.citas_sugeridas.map((c) => (
                      <tr key={c.id_cita}>
                        <td>
                          <Link className="font-semibold text-teal-800 underline" to={`/citas/${c.id_cita}`}>
                            {c.id_cita_externa}
                          </Link>
                          <p className="text-xs text-slate-500">{c.paciente_anon_id}</p>
                        </td>
                        <td>
                          <p className="font-medium">{etiqueta(c.especialidad)}</p>
                          <p className="text-xs text-slate-500">
                            {c.medico} · {formatearFechaHora(c.fecha_hora_cita)}
                          </p>
                        </td>
                        <td>
                          <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${COLOR_RIESGO[c.nivel_riesgo]}`}>
                            {c.nivel_riesgo} · {(Number(c.probabilidad_no_show) * 100).toFixed(1)}%
                          </span>
                          <div className="mt-1">
                            <EstadoBadge estado={c.estado_actual} />
                          </div>
                        </td>
                        <td className="max-w-md text-xs text-slate-700">{limpiarExplicabilidad(c.explicabilidad_resumen)}</td>
                        <td>
                          <p className="mb-2 text-xs text-slate-600">
                            Recordatorios enviados: <strong>{c.intervenciones_enviadas} / 1</strong>
                            {c.tiene_optout && <span className="ml-2 font-bold text-rose-700">(NO CONTACTAR)</span>}
                          </p>
                          {puedeOperar && (
                            <div className="flex flex-wrap gap-1.5">
                              <button
                                className="boton-secundario text-xs"
                                disabled={procesando}
                                onClick={() => enviarIntervencion(c.id_cita, "WHATSAPP")}
                              >
                                Enviar WhatsApp
                              </button>
                              <button
                                className="boton-secundario text-xs"
                                disabled={procesando}
                                onClick={() => enviarIntervencion(c.id_cita, "LLAMADA_TELEFONICA")}
                              >
                                Llamada
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="tarjeta space-y-4">
            <div className="seccion-cabecera">
              <h2>
                <Icono nombre="reloj" /> Historial de Comunicaciones y Respuesta del Paciente{" "}
                <span className="contador-citas">{datos.total_intervenciones}</span>
              </h2>
              <p>Registra la respuesta del paciente para confirmar su asistencia, liberar voluntariamente el turno o mantener la cita vigente ante falta de respuesta.</p>
            </div>

            <div className="tabla-contenedor">
              <table className="w-full tabla-citas">
                <thead>
                  <tr>
                    <th>N.° / Cita</th>
                    <th>Canal Utilizado</th>
                    <th>Estado de Envío</th>
                    <th>Respuesta del Paciente</th>
                    <th>Registrar Respuesta en Recepción</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {datos.historial_intervenciones.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-6 text-center text-sm text-slate-600">
                        Aún no se han enviado comunicaciones preventivas.
                      </td>
                    </tr>
                  ) : (
                    datos.historial_intervenciones.map((item) => (
                      <tr key={item.id_intervencion}>
                        <td>
                          <span className="font-semibold">#{item.id_intervencion}</span>
                          <p className="text-xs text-slate-500">
                            <Link className="text-teal-800 underline" to={`/citas/${item.id_cita}`}>
                              Cita #{item.id_cita}
                            </Link>
                          </p>
                        </td>
                        <td>
                          <p className="font-medium">{etiqueta(item.canal_contacto)}</p>
                          <p className="text-xs text-slate-500">Confirmación preventiva</p>
                        </td>
                        <td>
                          <span className="text-xs font-semibold">{item.estado_intervencion}</span>
                          <p className="text-xs text-slate-500">{formatearFechaHora(item.fecha_hora_envio)}</p>
                        </td>
                        <td>
                          <span className="font-semibold text-slate-800">{item.respuesta_paciente || "Pendiente de respuesta"}</span>
                          {item.consentimiento_optout && (
                            <p className="text-xs font-bold text-rose-700">Solicitó no recibir mensajes</p>
                          )}
                        </td>
                        <td>
                          {puedeOperar ? (
                            <div className="flex flex-wrap gap-1.5">
                              <button
                                className="boton-secundario text-xs"
                                disabled={procesando}
                                onClick={() => registrarRespuesta(item.id_intervencion, "CONFIRMA")}
                              >
                                Confirma Asistencia
                              </button>
                              <button
                                className="boton text-xs"
                                disabled={procesando}
                                onClick={() => registrarRespuesta(item.id_intervencion, "SOLICITA_LIBERACION")}
                              >
                                Solicita Liberar Turno
                              </button>
                              <button
                                className="boton-secundario text-xs"
                                disabled={procesando}
                                onClick={() => registrarRespuesta(item.id_intervencion, "SIN_RESPUESTA")}
                              >
                                Sin Respuesta
                              </button>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500">Solo lectura</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </>
  );
}
