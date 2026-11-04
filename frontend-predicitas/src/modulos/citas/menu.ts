import type { Rol } from "../../nucleo/api/tipos";

const rolesLectura: Rol[] = ["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"];
const rolesEscritura: Rol[] = ["ADMINISTRADOR", "RECEPCION"];

// RF-009 y RF-011: conserva los accesos existentes y sus permisos.
export default [
  { etiqueta: "Citas", ruta: "/citas", icono: "calendario", roles: rolesLectura, orden: 10 },
  { etiqueta: "Importar CSV", ruta: "/citas/importar", icono: "importar", roles: rolesEscritura, orden: 20 },
];
