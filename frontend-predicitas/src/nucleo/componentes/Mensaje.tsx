import type { ReactNode } from "react";
const colores = {
  error: "border-rose-200 bg-rose-50 text-rose-800",
  exito: "border-emerald-200 bg-emerald-50 text-emerald-800",
  info: "border-sky-200 bg-sky-50 text-sky-800",
};
// RNF-016: los errores se anuncian como alerta; los avisos como estado.
export default function Mensaje({ tipo = "error", children }: { tipo?: keyof typeof colores; children?: ReactNode }) {
  if (!children) return null;
  return <div role={tipo === "error" ? "alert" : "status"}
    className={`rounded-lg border p-4 text-sm ${colores[tipo]}`}>{children}</div>;
}
