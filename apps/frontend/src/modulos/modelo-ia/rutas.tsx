import ModeloIA from "./ModeloIA";
import type { RutaModulo } from "../../nucleo/layout/ranuras";

const rutas: RutaModulo[] = [
  { ruta: "/ia", elemento: <ModeloIA />, roles: ["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"] },
];

export default rutas;
