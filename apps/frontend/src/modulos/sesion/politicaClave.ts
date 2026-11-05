// RF-008, RNF-002: política exacta de contratos/modulo-01.json; no se recorta la clave.
export function errorClave(clave: string): string {
  if (clave.length < 8 || clave.length > 128) return "Usa entre 8 y 128 caracteres.";
  if (!/\p{L}/u.test(clave) || !/\p{N}/u.test(clave)) return "Incluye al menos una letra y un número.";
  return "";
}
