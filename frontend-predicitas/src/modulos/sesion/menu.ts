import type { EntradaMenu } from "../../nucleo/layout/ranuras";
// RF-008, RNF-004: los tres roles pueden gestionar su propio acceso.
const menu: EntradaMenu[] = [{ etiqueta: "Mi cuenta", ruta: "/mi-cuenta", icono: "escudo", roles: ["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"], orden: 40 }];
export default menu;
