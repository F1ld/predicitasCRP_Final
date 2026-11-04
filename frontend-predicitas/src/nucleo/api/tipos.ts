// RF-003, RNF-004: nombres exactos de contratos/comun.json y modulo-01.json.
export type Rol = "ADMINISTRADOR" | "RECEPCION" | "TECNICO_IA";
export interface Usuario {
  id_usuario: number;
  nombre_completo: string;
  correo_institucional: string;
  rol: Rol;
  activo: boolean;
  creado_en: string;
  actualizado_en: string | null;
}
export interface TokenOut {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}
export interface Pagina<T> {
  total: number;
  limite: number;
  desplazamiento: number;
  items: T[];
}
export interface ErrorApi {
  error: {
    codigo: string;
    mensaje: string;
    campos?: Record<string, string>;
  };
}
