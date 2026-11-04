import { useContext } from "react";
import { ContextoSesion } from "./contexto";

/** RF-001: cada consumidor debe quedar bajo el proveedor de autenticación. */
export function useAuth() {
  const contexto = useContext(ContextoSesion);
  if (!contexto) throw new Error("useAuth requiere AuthProvider.");
  return contexto;
}
