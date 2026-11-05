import type { EntradaMenu } from "../../nucleo/layout/ranuras";
import type { Rol } from "../../nucleo/api/tipos";

const rolesLectura: Rol[] = ["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"];
const rolesReporte: Rol[] = ["ADMINISTRADOR", "RECEPCION"];

// RF-003, RF-057 a RF-068, REP-02: navegación del módulo según contratos/modulo-05.json.
const menu: EntradaMenu[] = [
  { etiqueta: "Intervenciones", ruta: "/intervenciones", icono: "check", roles: rolesLectura, orden: 25 },
  { etiqueta: "Reporte de intervenciones", ruta: "/reportes/intervenciones", icono: "archivo", roles: rolesReporte, orden: 26 },
];

export default menu;
