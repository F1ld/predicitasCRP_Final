import { etiqueta, formatearFechaHora } from "../../nucleo/formato/formato";
import type { CitaDetalleOut } from "./tipos";

// RF-018, RNF-007: lectura de contactos, cupo, oferta y reasignación seudonimizados.
export default function DetalleSecciones({ cita }: { cita: CitaDetalleOut }) {
  const cupo = cita.cupo_liberado;
  const reasignacion = cita.reasignacion;
  return <>
    <section className="tarjeta" aria-labelledby="titulo-intervenciones"><div className="seccion-cabecera"><h2 id="titulo-intervenciones">Intervenciones</h2><p>Los contactos y respuestas del paciente se conservan sin cambiar la cita automáticamente.</p></div>
      {cita.intervenciones.length === 0 ? <p className="citas-seccion-vacia">No hay intervenciones registradas.</p> : <ol className="citas-lista-detalle">{cita.intervenciones.map((intervencion) => <li key={intervencion.id_intervencion}>
        <h3 className="font-semibold">Intervención #{intervencion.id_intervencion}</h3>
        <dl className="datos-cita"><div><dt>Canal de contacto</dt><dd>{intervencion.canal_contacto}</dd></div><div><dt>Estado de intervención</dt><dd>{intervencion.estado_intervencion}</dd></div>
          <div><dt>Respuesta del paciente</dt><dd>{intervencion.respuesta_paciente || "Sin respuesta registrada"}</dd></div><div><dt>Plantilla</dt><dd>{intervencion.plantilla_mensaje}</dd></div>
          <div><dt>Envío</dt><dd>{formatearFechaHora(intervencion.fecha_hora_envio)}</dd></div><div><dt>Respuesta recibida</dt><dd>{formatearFechaHora(intervencion.fecha_hora_respuesta)}</dd></div>
          <div><dt>Operador</dt><dd>{intervencion.id_operador === null ? "No registrado" : `Usuario #${intervencion.id_operador}`}</dd></div><div><dt>Opt-out</dt><dd>{intervencion.consentimiento_optout ? "Sí · no admite nuevos contactos" : "No registrado"}</dd></div>
        </dl>
      </li>)}</ol>}
    </section>
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <section className="tarjeta" aria-labelledby="titulo-cupo"><div className="seccion-cabecera"><h2 id="titulo-cupo">Cupo liberado</h2></div>
        {!cupo ? <p className="citas-seccion-vacia">No hay cupo liberado para esta cita.</p> : <>
          <dl className="datos-cita"><div><dt>Identificador del cupo</dt><dd>#{cupo.id_cupo_liberado}</dd></div><div><dt>Estado del cupo</dt><dd>{cupo.estado_cupo}</dd></div>
            <div><dt>Origen de liberación</dt><dd>{cupo.origen_liberacion}</dd></div><div><dt>Liberado el</dt><dd>{formatearFechaHora(cupo.liberado_en)}</dd></div>
            <div><dt>Especialidad del cupo</dt><dd>{etiqueta(cupo.especialidad)}</dd></div><div><dt>Médico del cupo</dt><dd>{cupo.medico}</dd></div>
            <div><dt>Fecha del cupo</dt><dd>{formatearFechaHora(cupo.fecha_hora_cupo)}</dd></div><div><dt>Franja del cupo</dt><dd>{etiqueta(cupo.franja_horaria)}</dd></div>
            <div><dt>Cita de origen</dt><dd>{cupo.id_cita_externa_origen}</dd></div>
          </dl>
          {cupo.oferta_vigente ? <div className="mt-4"><h3 className="font-semibold">Oferta vigente</h3><dl className="datos-cita">
            <div><dt>Candidato</dt><dd>#{cupo.oferta_vigente.id_candidato}</dd></div><div><dt>Paciente de la oferta (seudónimo)</dt><dd>{cupo.oferta_vigente.paciente_anon_id}</dd></div>
            <div><dt>Operador de oferta</dt><dd>Usuario #{cupo.oferta_vigente.id_operador}</dd></div><div><dt>Fecha de oferta</dt><dd>{formatearFechaHora(cupo.oferta_vigente.fecha_hora_oferta)}</dd></div>
          </dl></div> : <p className="citas-seccion-vacia">No hay oferta vigente.</p>}
        </>}
      </section>
      <section className="tarjeta" aria-labelledby="titulo-reasignacion"><div className="seccion-cabecera"><h2 id="titulo-reasignacion">Reasignación</h2></div>
        {!reasignacion ? <p className="citas-seccion-vacia">No hay reasignación registrada.</p> : <>
          <dl className="datos-cita"><div><dt>Identificador de reasignación</dt><dd>#{reasignacion.id_reasignacion}</dd></div><div><dt>Cupo reasignado</dt><dd>#{reasignacion.id_cupo_liberado}</dd></div>
            <div><dt>Candidato asignado</dt><dd>#{reasignacion.id_candidato}</dd></div><div><dt>Paciente reasignado (seudónimo)</dt><dd>{reasignacion.paciente_anon_id}</dd></div>
            <div><dt>Confirmación humana</dt><dd>{reasignacion.confirmacion_humana ? "Confirmada" : "Pendiente"}</dd></div><div><dt>Medio de confirmación</dt><dd>{reasignacion.medio_confirmacion}</dd></div>
            <div><dt>Operador que confirmó</dt><dd>Usuario #{reasignacion.id_operador_confirma}</dd></div><div><dt>Fecha de reasignación</dt><dd>{formatearFechaHora(reasignacion.fecha_hora_reasigna)}</dd></div>
            <div><dt>Observaciones</dt><dd>{reasignacion.observaciones || "Sin observaciones"}</dd></div>
          </dl><p className="mt-4 text-sm text-slate-600">La nueva cita se agenda en el sistema externo; PrediCitas registra la reasignación (RN03).</p>
        </>}
      </section>
    </div>
  </>;
}
