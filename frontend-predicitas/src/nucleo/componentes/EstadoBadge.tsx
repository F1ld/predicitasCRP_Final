import { etiqueta } from "../formato/formato";
const colores: Record<string, string> = {
  RECIBIDA: "bg-slate-100 text-slate-700", CONFIRMADA: "bg-emerald-100 text-emerald-800",
  REPROGRAMADA: "bg-amber-100 text-amber-800", CANCELADA: "bg-rose-100 text-rose-800",
  LIBERADA: "bg-violet-100 text-violet-800", ATENDIDA: "bg-teal-100 text-teal-800",
  NO_SHOW: "bg-red-200 text-red-900",
};
// RF-014, RNF-016: el estado siempre tiene una etiqueta de texto.
export default function EstadoBadge({ estado }: { estado: string }) {
  return <span className={`estado-badge ${colores[estado] || colores.RECIBIDA}`}>
    <span className="estado-punto" aria-hidden="true" />{etiqueta(estado)}
  </span>;
}
