import type { Rol } from "../../nucleo/api/tipos";

// RF-004 a RF-008: tipos exactos de contratos/modulo-01.json.
export interface UsuarioOut {
  id_usuario: number;
  nombre_completo: string;
  correo_institucional: string;
  rol: Rol;
  activo: boolean;
  creado_en: string;
  actualizado_en: string | null;
}

export interface ClaveTemporalOut {
  id_usuario: number;
  clave_temporal: string;
}

export const ROLES: readonly Rol[] = ["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"];
