import type { EntradaMenu } from "../../nucleo/layout/ranuras";
import rutas from "./rutas";

const menu: EntradaMenu[] = [
  { etiqueta: "Modelo IA", ruta: "/ia", icono: "exito",
    roles: rutas[0].roles.filter((rol) => rol !== "publico"), orden: 45 },
];

export default menu;
