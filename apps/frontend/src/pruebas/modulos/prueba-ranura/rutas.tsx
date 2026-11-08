// RF-003: fixture real de descubrimiento de módulos; vacío fuera de Vitest.
import type { RutaModulo } from "../../../nucleo/layout/ranuras";
const rutas: RutaModulo[] = [
  { ruta: "/prueba-ranura", elemento: <h1>Módulo de prueba descubierto</h1>, roles: ["ADMINISTRADOR"] },
];
export default rutas;
