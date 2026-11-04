import type { EntradaMenu } from "../../nucleo/layout/ranuras";

// RF-003, RNF-001: la administración de usuarios solo se ofrece al administrador.
const menu: EntradaMenu[] = [
  { etiqueta: "Usuarios", ruta: "/usuarios", icono: "escudo", roles: ["ADMINISTRADOR"], orden: 30 },
];
export default menu;
