import type { RutaModulo } from "../../nucleo/layout/ranuras";
import ListaEspera from "./ListaEspera";
import Cupos from "./Cupos";
import DetalleCupo from "./DetalleCupo";
import Reporte from "./Reporte";
import { ROLES_ESCRITURA } from "./tipos";

// RF-003, RF-069 a RF-082 y REP-03: ranura M06; TECNICO_IA no tiene acceso.
export default [
  { ruta: "/lista-espera", elemento: <ListaEspera />, roles: ROLES_ESCRITURA },
  { ruta: "/cupos", elemento: <Cupos />, roles: ROLES_ESCRITURA },
  { ruta: "/cupos/:id", elemento: <DetalleCupo />, roles: ROLES_ESCRITURA },
  { ruta: "/reportes/reasignaciones", elemento: <Reporte />, roles: ROLES_ESCRITURA },
] satisfies RutaModulo[];
