import type { Rol } from "../../nucleo/api/tipos";
import Bandeja from "./Bandeja";
import Detalle from "./Detalle";
import Importar from "./Importar";
import Registrar from "./Registrar";
import TrazabilidadCita from "./TrazabilidadCita";
import { ROLES_ESCRITURA } from "./transiciones";

const rolesLectura: Rol[] = ["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"];

// RF-009, RF-018, RF-024 y RF-011: ranura M02; App aplica los permisos de cada ruta.
export default [
  { ruta: "/citas", elemento: <Bandeja />, roles: rolesLectura },
  { ruta: "/citas/nueva", elemento: <Registrar />, roles: ROLES_ESCRITURA },
  { ruta: "/citas/importar", elemento: <Importar />, roles: ROLES_ESCRITURA },
  { ruta: "/citas/:id", elemento: <Detalle />, roles: rolesLectura },
  { ruta: "/citas/:id/trazabilidad", elemento: <TrazabilidadCita />, roles: rolesLectura },
];
