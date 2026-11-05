import { useEffect } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { iniciarGestorSesion } from "./controlador";

/** M01-V06, RF-002, RNF-004: se monta una vez en el layout autenticado. */
export default function GestorSesion() {
  const { usuario } = useAuth();
  const idUsuario = usuario?.id_usuario;
  const navegar = useNavigate();
  const { pathname } = useLocation();
  useEffect(() => {
    if (idUsuario === undefined) return;
    return iniciarGestorSesion(idUsuario, () => { void navegar("/login", { replace: true }); });
  }, [idUsuario, navegar]);
  // RF-003: adapta M01 al guard genérico sin cambiar el router ni consultar Usuarios.
  if (usuario && usuario.rol !== "ADMINISTRADOR" && (pathname === "/usuarios" || pathname.startsWith("/usuarios/"))) {
    return <Navigate to="/" replace />;
  }
  return null;
}
