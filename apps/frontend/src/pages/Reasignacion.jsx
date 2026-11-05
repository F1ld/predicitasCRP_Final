import { useState } from "react";
import { useAuth } from "../auth/useAuth";
import Cargando from "../components/Cargando";
import Icono from "../components/Icono";
import Mensaje from "../components/Mensaje";
import { api } from "../lib/api";
import { etiqueta, formatearFechaHora } from "../lib/formato";
import { ROLES_ESCRITURA } from "../lib/transiciones";
import { useConsulta } from "../lib/useConsulta";

export default function Reasignacion() {
  const { tieneRol } = useAuth();
  const puedeOperar = tieneRol(...ROLES_ESCRITURA);

  const [estadoCupo, setEstadoCupo] = useState("TODOS");
  const {
    datos: cupos,
    cargando: cargandoCupos,
    error: errorCupos,
    reintentar: recargarCupos,
  } = useConsulta(`/cupos-liberados?estado_cupo=${estadoCupo}`);

  const {
    datos: listaEspera,
    cargando: cargandoEspera,
    error: errorEspera,
    reintentar: recargarEspera,
  } = useConsulta("/lista-espera");

  const [propuesta, setPropuesta] = useState(null);
  const [confirmacionHumana, setConfirmacionHumana] = useState(false);
  const [medioConfirmacion, setMedioConfirmacion] = useState("LLAMADA_CONFIRMADA");
  const [observaciones, setObservaciones] = useState("");
  const [procesando, setProcesando] = useState(false);
  const [exito, setExito] = useState("");
  const [errorAccion, setErrorAccion] = useState("");

  async function agregarCandidato(e) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    setProcesando(true);
    setErrorAccion("");
    setExito("");
    try {
      const creado = await api("/lista-espera", {
        metodo: "POST",
        json: {
          paciente_anon_id: String(fd.get("paciente_anon_id") || "").trim(),
          especialidad_req: String(fd.get("especialidad_req")),
          franja_preferida: String(fd.get("franja_preferida")),
          prioridad_registro: Number(fd.get("prioridad_registro") || 1),
        },
      });
      setExito(`Paciente ${creado.paciente_anon_id} inscrito en Lista de Espera (#${creado.id_candidato}).`);
      form.reset();
      recargarEspera();
      if (propuesta) verCandidatosDeCupo(propuesta.cupo.id_cupo_liberado);
    } catch (err) {
      setErrorAccion(err.message);
    } finally {
      setProcesando(false);
    }
  }

  async function verCandidatosDeCupo(idCupo) {
    setProcesando(true);
    setErrorAccion("");
    try {
      const res = await api(`/cupos-liberados/${idCupo}/candidatos`);
      setPropuesta(res);
      setConfirmacionHumana(false);
    } catch (err) {
      setErrorAccion(err.message);
    } finally {
      setProcesando(false);
    }
  }

  async function confirmarReasignacion(idCupo, idCandidato) {
    setProcesando(true);
    setErrorAccion("");
    setExito("");
    try {
      const res = await api(`/cupos-liberados/${idCupo}/reasignar`, {
        metodo: "POST",
        json: {
          id_candidato: idCandidato,
          confirmacion_humana: confirmacionHumana,
          medio_confirmacion: medioConfirmacion,
          observaciones: observaciones || "Reasignación asistida confirmada por recepción",
        },
      });
      setExito(
        `Turno #${res.id_cupo_liberado} reasignado exitosamente (Registro #${res.id_reasignacion}). ` +
        `Estado del turno: ${res.estado_cupo_final} | Paciente #${res.id_candidato}: ${res.estado_candidato_final}.`
      );
      setPropuesta(null);
      recargarCupos();
      recargarEspera();
    } catch (err) {
      setErrorAccion(err.message);
    } finally {
      setProcesando(false);
    }
  }

  return (
    <>
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">GESTIÓN Y RECUPERACIÓN DE TURNOS MÉDICOS</p>
          <h1>Turnos Liberados y Reasignación Asistida</h1>
          <p>Asignación de turnos disponibles a pacientes en lista de espera según especialidad médica, horario preferido y orden de prioridad.</p>
        </div>
      </div>

      {errorAccion && <Mensaje>{errorAccion}</Mensaje>}
      {exito && <Mensaje tipo="exito">{exito}</Mensaje>}

      <div className="grid items-start gap-6 lg:grid-cols-3">
        <section className="tarjeta lg:col-span-2 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="seccion-cabecera">
              <h2>
                <Icono nombre="calendario" /> Turnos Médicos Liberados{" "}
                <span className="contador-citas">{cupos ? cupos.length : 0}</span>
              </h2>
              <p>Horarios liberados anticipadamente por pacientes y disponibles para ser cubiertos.</p>
            </div>
            <select value={estadoCupo} onChange={(e) => setEstadoCupo(e.target.value)} className="w-44">
              <option value="TODOS">Todos los estados</option>
              <option value="DISPONIBLE">Solo Disponibles</option>
              <option value="REASIGNADO">Solo Reasignados</option>
            </select>
          </div>

          {cargandoCupos ? (
            <Cargando texto="Cargando turnos liberados…" />
          ) : errorCupos ? (
            <Mensaje>{errorCupos}</Mensaje>
          ) : (
            <div className="tabla-contenedor">
              <table className="w-full tabla-citas">
                <thead>
                  <tr>
                    <th>Turno / Cita Origen</th>
                    <th>Especialidad y Médico</th>
                    <th>Fecha, Hora y Turno</th>
                    <th>Estado</th>
                    <th>Acción</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {cupos.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-6 text-center text-sm text-slate-600">
                        No hay turnos liberados en este filtro. Puedes liberar un turno desde la pestaña «Intervenciones».
                      </td>
                    </tr>
                  ) : (
                    cupos.map((c) => (
                      <tr key={c.id_cupo_liberado}>
                        <td>
                          <span className="font-bold">Turno #{c.id_cupo_liberado}</span>
                          <p className="text-xs text-slate-500">Cita origen #{c.id_cita_origen}</p>
                        </td>
                        <td>
                          <p className="font-semibold">{etiqueta(c.especialidad)}</p>
                          <p className="text-xs text-slate-500">{c.medico}</p>
                        </td>
                        <td>
                          <p>{formatearFechaHora(c.fecha_hora_cupo)}</p>
                          <p className="text-xs font-medium text-teal-800">Turno: {etiqueta(c.franja_horaria)}</p>
                        </td>
                        <td>
                          <span
                            className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${
                              c.estado_cupo === "DISPONIBLE"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-slate-200 text-slate-800"
                            }`}
                          >
                            {c.estado_cupo}
                          </span>
                        </td>
                        <td>
                          {c.estado_cupo === "DISPONIBLE" ? (
                            <button
                              className="boton text-xs"
                              disabled={procesando}
                              onClick={() => verCandidatosDeCupo(c.id_cupo_liberado)}
                            >
                              Buscar Pacientes Compatibles
                            </button>
                          ) : (
                            <span className="text-xs text-slate-500">Turno ya cubierto</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {propuesta && (
            <div className="rounded-lg border-2 border-teal-700 bg-teal-50/40 p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-teal-950">
                  Pacientes en Espera Compatibles con el Turno #{propuesta.cupo.id_cupo_liberado} (
                  {etiqueta(propuesta.cupo.especialidad)} · {etiqueta(propuesta.cupo.franja_horaria)})
                </h3>
                <button className="boton-secundario text-xs" onClick={() => setPropuesta(null)}>
                  Cerrar
                </button>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="medio-conf">Medio de confirmación con el paciente</label>
                  <select
                    id="medio-conf"
                    value={medioConfirmacion}
                    onChange={(e) => setMedioConfirmacion(e.target.value)}
                  >
                    <option value="LLAMADA_CONFIRMADA">Llamada telefónica confirmada</option>
                    <option value="PRESENCIAL">Confirmación presencial en recepción</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="obs-reasig">Observaciones de recepción</label>
                  <input
                    id="obs-reasig"
                    value={observaciones}
                    onChange={(e) => setObservaciones(e.target.value)}
                    placeholder="Ej. Paciente confirma que asistirá al turno"
                  />
                </div>
              </div>

              <label className="flex items-center gap-2 rounded border border-amber-300 bg-amber-50 p-3 text-sm font-semibold text-amber-950 cursor-pointer">
                <input
                  type="checkbox"
                  checked={confirmacionHumana}
                  onChange={(e) => setConfirmacionHumana(e.target.checked)}
                  className="h-4 w-4"
                />
                <span>
                  Confirmación del personal de recepción: Certifico que me comuniqué con el paciente seleccionado y confirmó su asistencia al turno disponible.
                </span>
              </label>

              {propuesta.candidatos.length === 0 ? (
                <p className="text-sm text-slate-700">
                  No hay pacientes activos en lista de espera compatibles con {etiqueta(propuesta.cupo.especialidad)} en turno{" "}
                  {etiqueta(propuesta.cupo.franja_horaria)}. Puedes inscribir uno en el formulario lateral.
                </p>
              ) : (
                <ul className="space-y-2">
                  {propuesta.candidatos.map((cand, idx) => (
                    <li
                      key={cand.id_candidato}
                      className="flex flex-wrap items-center justify-between gap-2 rounded bg-white p-3 shadow-sm border border-slate-200"
                    >
                      <div>
                        <p className="font-bold text-slate-900">
                          #{idx + 1} · {cand.paciente_anon_id} (Registro #{cand.id_candidato})
                        </p>
                        <p className="text-xs text-slate-600">{cand.criterio_compatibilidad?.replace(/\s*\(FIFO\)/gi, "· Orden de llegada")}</p>
                      </div>
                      {puedeOperar && (
                        <button
                          className="boton text-xs"
                          disabled={procesando}
                          onClick={() => confirmarReasignacion(propuesta.cupo.id_cupo_liberado, cand.id_candidato)}
                        >
                          Asignar Turno al Paciente
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>

        <section className="tarjeta space-y-4">
          <div className="seccion-cabecera">
            <h2>Inscribir en Lista de Espera</h2>
            <p>Registra a un paciente que desea adelantar su atención cuando se libere un horario.</p>
          </div>
          {puedeOperar ? (
            <form onSubmit={agregarCandidato} className="space-y-3">
              <div>
                <label htmlFor="pac-espera">Código del Paciente</label>
                <input id="pac-espera" name="paciente_anon_id" required placeholder="Ej. PAC-SIM-00901" />
              </div>
              <div>
                <label htmlFor="esp-espera">Especialidad requerida</label>
                <select id="esp-espera" name="especialidad_req" defaultValue="CARDIOLOGIA">
                  <option value="CARDIOLOGIA">Cardiología</option>
                  <option value="TRAUMATOLOGIA">Traumatología</option>
                  <option value="PEDIATRIA">Pediatría</option>
                </select>
              </div>
              <div>
                <label htmlFor="franja-espera">Turno horario preferido</label>
                <select id="franja-espera" name="franja_preferida" defaultValue="INDIFERENTE">
                  <option value="INDIFERENTE">Indiferente (Mañana o Tarde)</option>
                  <option value="MANANA">Solo Mañana</option>
                  <option value="TARDE">Solo Tarde</option>
                </select>
              </div>
              <div>
                <label htmlFor="prio-espera">Nivel de prioridad (1 = más alta)</label>
                <input id="prio-espera" name="prioridad_registro" type="number" min={1} max={10} defaultValue={1} />
              </div>
              <button type="submit" className="boton w-full" disabled={procesando}>
                Inscribir en Lista de Espera
              </button>
            </form>
          ) : (
            <p className="text-sm text-slate-600">Solo el personal de Recepción y Administración puede inscribir pacientes.</p>
          )}
        </section>
      </div>

      <section className="tarjeta space-y-4">
        <div className="seccion-cabecera">
          <h2>
            Pacientes en Lista de Espera <span className="contador-citas">{listaEspera ? listaEspera.length : 0}</span>
          </h2>
          <p>Ordenados por prioridad clínica-administrativa y fecha de solicitud.</p>
        </div>
        {cargandoEspera ? (
          <Cargando texto="Cargando lista de espera…" />
        ) : errorEspera ? (
          <Mensaje>{errorEspera}</Mensaje>
        ) : (
          <div className="tabla-contenedor">
            <table className="w-full tabla-citas">
              <thead>
                <tr>
                  <th>N.°</th>
                  <th>Paciente</th>
                  <th>Especialidad Solicitada</th>
                  <th>Horario Preferido</th>
                  <th>Prioridad</th>
                  <th>Estado</th>
                  <th>Fecha de Solicitud</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {listaEspera.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-6 text-center text-sm text-slate-600">
                      No hay pacientes inscritos en lista de espera.
                    </td>
                  </tr>
                ) : (
                  listaEspera.map((c) => (
                    <tr key={c.id_candidato}>
                      <td className="font-semibold">#{c.id_candidato}</td>
                      <td>{c.paciente_anon_id}</td>
                      <td>{etiqueta(c.especialidad_req)}</td>
                      <td>{etiqueta(c.franja_preferida)}</td>
                      <td>Prioridad {c.prioridad_registro}</td>
                      <td>
                        <span className="font-semibold">{c.estado_candidato}</span>
                      </td>
                      <td>{formatearFechaHora(c.fecha_registro)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
