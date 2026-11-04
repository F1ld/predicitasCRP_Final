import type { Rol } from "../../nucleo/api/tipos";
import Intervenciones from "./Intervenciones";
import Seguimiento from "./Seguimiento";
import Reporte from "./Reporte";

const rolesLectura: Rol[] = ["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"];
const rolesReporte: Rol[] = ["ADMINISTRADOR", "RECEPCION"];

// M05-V01, M05-V03, M05-V04, RF-057 a RF-068, REP-02: ranura M05 según contratos/modulo-05.json.
export default [
  { ruta: "/intervenciones", elemento: <Intervenciones />, roles: rolesLectura },
  { ruta: "/intervenciones/:id", elemento: <Seguimiento />, roles: rolesLectura },
  { ruta: "/reportes/intervenciones", elemento: <Reporte />, roles: rolesReporte },
];
