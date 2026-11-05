import type { RutaModulo } from "../../nucleo/layout/ranuras";
import Usuarios from "./Usuarios";

// RF-003, RF-004, RNF-001: ranura M01-V02 protegida por el mismo rol que el menú.
const rutas: RutaModulo[] = [
  { ruta: "/usuarios", elemento: <Usuarios />, roles: ["ADMINISTRADOR"] },
];
export default rutas;
