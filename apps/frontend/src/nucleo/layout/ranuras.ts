import type { ReactElement } from "react";
import type { Rol } from "../api/tipos";

export interface RutaModulo {
  ruta: string;
  elemento: ReactElement;
  roles: readonly (Rol | "publico")[];
}
export interface EntradaMenu {
  etiqueta: string;
  ruta: string;
  icono: string;
  roles: Rol[];
  orden: number;
}
export interface ModuloRutas { default: readonly RutaModulo[] }
export interface ModuloMenu { default: EntradaMenu[] }

// RF-003: misma fuente de roles para la navegación y sus ranuras.
export function menuPorRol(modulos: Record<string, ModuloMenu>, rol: Rol): EntradaMenu[] {
  return Object.values(modulos).flatMap((modulo) => modulo.default)
    .filter((entrada) => entrada.roles.includes(rol))
    .sort((a, b) => a.orden - b.orden || a.ruta.localeCompare(b.ruta));
}

// comun.json: /panel entrará en T-071; hasta entonces todos inician en /citas.
export function inicioPorRol(rol: Rol, rutas: readonly RutaModulo[]): string {
  return rol !== "TECNICO_IA" && rutas.some((ruta) => ruta.ruta === "/panel" && ruta.roles.includes(rol)) ? "/panel" : "/citas";
}
