import { createContext } from "react";
import type { Rol, Usuario } from "../api/tipos";

/** RF-001, RF-002, RNF-001: acceso autenticado compartido por el núcleo. */
export interface ContextoAuth {
  usuario: Usuario | null;
  cargando: boolean;
  mensajeSesion: string;
  iniciarSesion: (correo: string, clave: string) => Promise<void>;
  cerrarSesion: () => Promise<void>;
  tieneRol: (...roles: Rol[]) => boolean;
}

export const ContextoSesion = createContext<ContextoAuth | null>(null);
