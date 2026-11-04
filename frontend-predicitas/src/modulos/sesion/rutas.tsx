import Login from "./Login";
import MiCuenta from "./MiCuenta";
import type { RutaModulo } from "../../nucleo/layout/ranuras";

/** RF-001: ranura pública de inicio de sesión según contratos/comun.json. */
const rutas: RutaModulo[] = [
  { ruta: "/login", elemento: <Login />, roles: ["publico"] },
  { ruta: "/mi-cuenta", elemento: <MiCuenta />, roles: ["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"] },
];

export default rutas;
