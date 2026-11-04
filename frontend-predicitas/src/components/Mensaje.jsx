export default function Mensaje({ tipo = "error", children }) {
  if (!children) return null;
  const colores = {
    error: "border-rose-200 bg-rose-50 text-rose-800",
    exito: "border-emerald-200 bg-emerald-50 text-emerald-800",
    info: "border-sky-200 bg-sky-50 text-sky-800",
  };
  return <div role={tipo === "error" ? "alert" : "status"}
    className={`rounded-lg border p-4 text-sm ${colores[tipo] || colores.info}`}>{children}</div>;
}
