export type NivelRiesgo = "BAJO" | "MEDIO" | "ALTO";
const colores: Record<NivelRiesgo, string> = {
  BAJO: "bg-emerald-100 text-emerald-800",
  MEDIO: "bg-amber-100 text-amber-800",
  ALTO: "bg-rose-100 text-rose-800",
};
// RNF-017, RF-056, RN16: nivel de inasistencia, diferenciado por texto y color.
export default function NivelRiesgoBadge({ nivel }: { nivel: NivelRiesgo }) {
  return <span className={`estado-badge ${colores[nivel]}`} aria-label={`Riesgo de inasistencia: ${nivel}`}>
    <span className="estado-punto" aria-hidden="true" />{nivel}
  </span>;
}
