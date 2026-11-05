import type { EntradaMenu } from "../../nucleo/layout/ranuras";
import { ROLES_ESCRITURA } from "./tipos";

// RF-003, RF-072, RF-073, REP-03: entradas M06 solo para roles del contrato.
export default [
  { etiqueta: "Lista de espera", ruta: "/lista-espera", icono: "reloj", roles: ROLES_ESCRITURA, orden: 40 },
  { etiqueta: "Cupos liberados", ruta: "/cupos", icono: "calendario", roles: ROLES_ESCRITURA, orden: 41 },
  { etiqueta: "Reporte de reasignaciones", ruta: "/reportes/reasignaciones", icono: "archivo", roles: ROLES_ESCRITURA, orden: 42 },
] satisfies EntradaMenu[];
