import NivelRiesgoBadge from "../../nucleo/componentes/NivelRiesgoBadge";
import RotuloSimulado from "../../nucleo/componentes/RotuloSimulado";
import { formatearFechaHora } from "../../nucleo/formato/formato";
import type { PrediccionOut } from "./tipos";

/**
 * RF-018, RF-041 a RF-056, RNF-010, RN16:
 * Indicador de Riesgo Predictivo de Inasistencia (LightGBM + TreeSHAP)
 * Enfoque clínico: alta visibilidad asistencial, explicabilidad estructurada y aviso ético obligatorio.
 */
export default function DetallePrediccion({
  prediccion,
  destacado = false,
}: {
  prediccion: PrediccionOut;
  destacado?: boolean;
}) {
  const porcentaje = Math.round(prediccion.probabilidad_no_show * 1000) / 10;
  const umbralPorcentaje = Math.round(prediccion.umbral_aplicado * 1000) / 10;
  const nivel = prediccion.nivel_riesgo;

  // Clases semánticas según nivel de riesgo asistencial
  const configRiesgo = {
    ALTO: {
      colorTexto: "text-rose-700",
      colorFondo: "bg-rose-50",
      colorBorde: "border-rose-200",
      colorBarra: "bg-rose-600",
      sugerencia: "Prioridad alta: Se recomienda intervención preventiva inmediata (WhatsApp / Llamada).",
    },
    MEDIO: {
      colorTexto: "text-amber-700",
      colorFondo: "bg-amber-50",
      colorBorde: "border-amber-200",
      colorBarra: "bg-amber-500",
      sugerencia: "Riesgo moderado: Sugerido recordatorio automatizado previo a las 48h.",
    },
    BAJO: {
      colorTexto: "text-emerald-700",
      colorFondo: "bg-emerald-50",
      colorBorde: "border-emerald-200",
      colorBarra: "bg-emerald-600",
      sugerencia: "Riesgo estándar: Paciente con alta probabilidad de asistencia confirmada.",
    },
  }[nivel];

  // Parseo de factores de explicabilidad TreeSHAP
  const factores = prediccion.explicabilidad_resumen
    ? prediccion.explicabilidad_resumen.split(/[,;|]+/).map((f) => f.trim()).filter(Boolean)
    : [];

  return (
    <article
      className={`citas-prediccion-kpi ${destacado ? "kpi-hero " + configRiesgo.colorFondo + " " + configRiesgo.colorBorde : "kpi-secundario"}`}
      aria-label={`Evaluación predictiva #${prediccion.id_prediccion} - Riesgo ${nivel}`}
    >
      {/* Cabecera del KPI */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/70 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Modelo IA {prediccion.version_modelo}
            </span>
            {prediccion.resultado_simulado && <RotuloSimulado />}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Inferencia: {formatearFechaHora(prediccion.fecha_hora_inferencia)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium">Clasificación:</span>
          <NivelRiesgoBadge nivel={prediccion.nivel_riesgo} />
        </div>
      </div>

      {/* Probabilidad y Barra de Progreso */}
      <div className="my-2">
        <div className="flex items-baseline justify-between mb-1.5">
          <span className="text-sm font-semibold text-slate-700">
            Probabilidad estimada de inasistencia:
          </span>
          <span className={`text-2xl font-black ${configRiesgo.colorTexto}`}>
            {porcentaje.toLocaleString("es-PE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %
          </span>
        </div>

        {/* Barra de progreso */}
        <div className="w-full bg-slate-200 rounded-full h-3.5 overflow-hidden flex" title={`Probabilidad: ${porcentaje}%, Umbral: ${umbralPorcentaje}%`}>
          <div
            className={`h-full transition-all duration-500 ${configRiesgo.colorBarra}`}
            style={{ width: `${Math.min(Math.max(porcentaje, 4), 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-[11px] text-slate-500 mt-1">
          <span>0% (Asistencia segura)</span>
          <span className="font-semibold text-slate-700">Umbral de decisión: {umbralPorcentaje}%</span>
          <span>100% (No asistirá)</span>
        </div>
      </div>

      {/* Sugerencia de conducta asistencial */}
      <div className="p-2.5 rounded-lg bg-white/80 border border-slate-200/60 text-xs text-slate-700">
        <strong className="font-semibold text-slate-800">Criterio asistencial: </strong>
        {configRiesgo.sugerencia}
      </div>

      {/* Explicabilidad Clínica (TreeSHAP) */}
      <div className="space-y-1.5">
        <span className="text-xs font-semibold text-slate-700 block">
          Factores principales de influencia clínica (TreeSHAP):
        </span>
        {factores.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {factores.map((factor, idx) => (
              <span
                key={idx}
                className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-white text-slate-700 border border-slate-300 shadow-2xs"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-teal-600 mr-1.5" />
                {factor}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic">
            {prediccion.explicabilidad_resumen || "Variables de agenda en rango habitual para el perfil."}
          </p>
        )}
      </div>

      {/* Advertencia Ética Obligatoria (RF-056) */}
      <div className="mt-1 p-2 rounded bg-amber-50/70 border border-amber-200/60 text-[11px] text-amber-900 leading-tight">
        <span className="font-bold">Aviso ético asistencial (RF-056):</span> Resultado predictivo de carácter orientativo generado mediante modelo LightGBM acreditado sobre dataset sintético. No constituye decisión diagnóstica ni restringe la prestación de servicios de salud.
      </div>

      {/* Variables conservadas (Snapshot de features para auditoría) */}
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer text-teal-800 hover:text-teal-950 font-semibold py-1">
          Ver vector de características conservadas (Snapshot de inferencia)
        </summary>
        <dl className="datos-cita citas-instantanea mt-2">
          {Object.entries(prediccion.features_snapshot || {}).map(([nombre, valor]) => (
            <div key={nombre}>
              <dt className="text-[11px]">{nombre}</dt>
              <dd className="font-mono text-[11px]">
                {typeof valor === "object" ? JSON.stringify(valor) : String(valor)}
              </dd>
            </div>
          ))}
        </dl>
      </details>
    </article>
  );
}
