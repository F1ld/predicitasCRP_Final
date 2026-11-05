import { useContext } from "react";
import { ContextoSesion } from "./contexto";
export function useAuth() {
  const contexto = useContext(ContextoSesion);
  if (!contexto) throw new Error("useAuth requiere AuthProvider.");
  return contexto;
}
