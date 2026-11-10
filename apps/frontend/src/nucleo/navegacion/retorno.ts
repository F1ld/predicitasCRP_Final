/** Resuelve solo rutas internas explícitamente permitidas, manteniendo su query. */
export function resolverRetorno(estado: unknown, fallback: string, permitidas: readonly string[]): string {
  if (typeof estado !== "object" || estado === null || !("volver" in estado) || typeof estado.volver !== "string") return fallback;
  const valor = estado.volver;
  if (!valor.startsWith("/") || valor.startsWith("//") || /[\\\r\n]/.test(valor)) return fallback;
  const url = new URL(valor, "https://predicitas.invalid");
  return url.origin === "https://predicitas.invalid" && permitidas.includes(url.pathname) ? `${url.pathname}${url.search}` : fallback;
}
