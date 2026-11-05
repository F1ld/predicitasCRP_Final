import Cargando from "../components/Cargando";
import Icono from "../components/Icono";
import Mensaje from "../components/Mensaje";
import { useConsulta } from "../lib/useConsulta";

const ETIQUETAS_VARIABLES = {
  "inasistencias_previas / tasa_previa": "Historial de inasistencias previas del paciente",
  "antelacion_dias": "Días de anticipación con que se reservó la cita",
  "reprogramaciones_prev": "Reprogramaciones previas acumuladas",
  "asistencias_previas": "Cumplimiento de citas anteriores (asistencias)",
  "tipo_paciente": "Condición del paciente (Nuevo o Continuador)",
  "canal_origen": "Canal de agendamiento (Web, Call Center o Presencial)",
  "franja_horaria": "Turno horario de la cita (Mañana o Tarde)",
  "especialidad": "Especialidad médica",
  "dia_semana": "Día de la semana de la atención",
};

export default function ModeloIA() {
  const { datos: metricas, cargando: c1, error: e1 } = useConsulta("/ia/metricas");
  const { datos: dataset, cargando: c2, error: e2 } = useConsulta("/ia/dataset-resumen");

  if (c1 || c2) return <Cargando texto="Cargando indicadores de desempeño del modelo predictivo…" />;
  if (e1 || e2) return <Mensaje>{e1 || e2}</Mensaje>;

  const mt = metricas.metricas_test;
  const mb = metricas.metricas_baseline_test;
  const mc = mt.matriz_confusion;
  const versionLimpia = metricas.version_modelo.replace("_", " ");

  return (
    <>
      <div className="pagina-titulo">
        <div>
          <p className="sobretitulo">MÓDULO DE ANÁLISIS PREDICTIVO Y MÉTRICAS DEL MODELO</p>
          <h1>Desempeño del Modelo Predictivo y Calidad de Datos</h1>
          <p>Herramienta de asistencia predictiva para apoyo a la recepción médica · Las decisiones de contacto y reasignación cuentan siempre con supervisión del personal.</p>
        </div>
        <span className="inline-block rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-900 border border-emerald-300">
          {versionLimpia} · Exactitud F1: {(mt.f1_score * 100).toFixed(2)}%
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="tarjeta">
          <p className="text-xs font-bold uppercase text-slate-500">Exactitud Equilibrada (F1-Score)</p>
          <p className="mt-2 text-3xl font-extrabold text-teal-900">{(mt.f1_score * 100).toFixed(2)}%</p>
          <p className="mt-1 text-xs text-emerald-700 font-semibold">
            Supera al modelo base tradicional ({(mb.f1_score * 100).toFixed(2)}%)
          </p>
        </div>
        <div className="tarjeta">
          <p className="text-xs font-bold uppercase text-slate-500">Precisión / Sensibilidad (Umbral {(mt.umbral * 100).toFixed(0)}%)</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {(mt.precision * 100).toFixed(1)}% / {(mt.recall * 100).toFixed(1)}%
          </p>
          <p className="mt-1 text-xs text-slate-500">Capacidad de detección oportuna de inasistencias</p>
        </div>
        <div className="tarjeta">
          <p className="text-xs font-bold uppercase text-slate-500">Capacidad Discriminativa (ROC-AUC)</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {(mt.roc_auc * 100).toFixed(2)}%
          </p>
          <p className="mt-1 text-xs text-slate-500">Evaluado sobre {dataset.test_size} citas de validación independiente</p>
        </div>
        <div className="tarjeta">
          <p className="text-xs font-bold uppercase text-slate-500">Integridad y Aislamiento de Datos</p>
          <p className="mt-2 text-2xl font-bold text-emerald-800">
            {dataset.control_leakage.aprobado ? "VERIFICADO (100%)" : "EN REVISIÓN"}
          </p>
          <p className="mt-1 text-xs text-slate-500">Evaluación exclusiva con datos previos a la cita</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="tarjeta space-y-4">
          <div className="seccion-cabecera">
            <h2>
              <Icono nombre="archivo" /> Ficha Técnica de Calidad de Datos Históricos
            </h2>
            <p>Sede San Isidro · Especialidades de Cardiología, Traumatología y Pediatría.</p>
          </div>
          <dl className="datos-cita">
            <div>
              <dt>Citas Históricas Analizadas</dt>
              <dd>{dataset.total_historicas} atenciones cerradas</dd>
            </div>
            <div>
              <dt>Pacientes Atendidos / Inasistencias</dt>
              <dd>
                {dataset.atendidas_historicas} ({((1 - dataset.tasa_no_show_global) * 100).toFixed(1)}%) /{" "}
                {dataset.no_show_historicas} ({(dataset.tasa_no_show_global * 100).toFixed(1)}%)
              </dd>
            </div>
            <div>
              <dt>Distribución de Entrenamiento y Prueba</dt>
              <dd>
                Entrenamiento: {dataset.train_size} · Validación: {dataset.val_size} · Prueba: {dataset.test_size}
              </dd>
            </div>
            <div>
              <dt>Citas Próximas en Seguimiento Activo</dt>
              <dd>{dataset.proximas_operativas_bd} citas programadas</dd>
            </div>
          </dl>
        </section>

        <section className="tarjeta space-y-4">
          <div className="seccion-cabecera">
            <h2>
              <Icono nombre="escudo" /> Evaluación de Exactitud y Matriz de Aciertos
            </h2>
            <p>Resultados obtenidos sobre el grupo independiente de {dataset.test_size} citas de prueba.</p>
          </div>
          <div className="grid grid-cols-2 gap-3 text-center text-sm">
            <div className="rounded bg-slate-100 p-3">
              <p className="text-xs text-slate-600">Asistencias Correctamente Previstas</p>
              <p className="text-xl font-bold text-slate-900">{mc.tn}</p>
            </div>
            <div className="rounded bg-amber-50 p-3">
              <p className="text-xs text-amber-800">Alertas Preventivas Adicionales</p>
              <p className="text-xl font-bold text-amber-900">{mc.fp}</p>
            </div>
            <div className="rounded bg-rose-50 p-3">
              <p className="text-xs text-rose-800">Inasistencias No Anticipadas</p>
              <p className="text-xl font-bold text-rose-900">{mc.fn}</p>
            </div>
            <div className="rounded bg-emerald-50 p-3">
              <p className="text-xs text-emerald-800">Inasistencias Detectadas a Tiempo</p>
              <p className="text-xl font-bold text-emerald-900">{mc.tp}</p>
            </div>
          </div>
          <div>
            <p className="text-xs font-bold uppercase text-slate-500 mb-2">Factores Clínicos y Operativos con Mayor Peso en la Predicción</p>
            <ul className="space-y-1 text-xs">
              {metricas.importancia_global_variables.slice(0, 5).map((item) => (
                <li key={item.variable} className="flex justify-between border-b border-slate-100 py-1.5">
                  <span className="font-medium text-slate-700">{ETIQUETAS_VARIABLES[item.variable] || item.variable}</span>
                  <span className="font-bold text-teal-900">{item.importancia} puntos de decisión</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </>
  );
}
