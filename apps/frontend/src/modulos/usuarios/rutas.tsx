import type { RutaModulo } from "../../nucleo/layout/ranuras";
import Usuarios from "./Usuarios";

// RF-003, RF-004, RNF-001: acceso directo a M01-V02 reservado al administrador.
const rutas: RutaModulo[] = [
  { ruta: "/usuarios", elemento: <Usuarios />, roles: ["ADMINISTRADOR"] },
];
export default rutas;
