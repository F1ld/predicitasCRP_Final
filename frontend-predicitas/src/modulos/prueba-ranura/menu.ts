// RF-003: verifica el glob real del layout; no publica menú en desarrollo/build.
import type { EntradaMenu } from "../../nucleo/layout/ranuras";
const menu: EntradaMenu[] = import.meta.env.MODE === "test" ? [
  { etiqueta: "Prueba de ranura", ruta: "/prueba-ranura", icono: "calendario", roles: ["ADMINISTRADOR"], orden: 999 },
] : [];
export default menu;
