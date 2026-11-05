import type { ReactNode } from "react";
import { Link, Navigate, Outlet } from "react-router-dom";
import type { Rol } from "../api/tipos";
import { useAuth } from "./useAuth";
import Cargando from "../componentes/Cargando";

interface Props {
  roles?: readonly Rol[];
  children?: ReactNode;
}

/** RF-003, RNF-001: verifica la sesión y el rol antes de mostrar una ruta. */
export default function RutaProtegida({ roles, children }: Props) {
  const { usuario, cargando, tieneRol } = useAuth();
  if (cargando) return <Cargando texto="Verificando sesión…" />;
  if (!usuario) return <Navigate to="/login" replace />;
  if (roles && !tieneRol(...roles)) return <section className="tarjeta mx-auto max-w-xl">
    <h1>No tienes permiso para esta sección</h1>
    <p className="mt-3 text-slate-600">Tu rol permite consultar citas, pero no realizar esta operación.</p>
    <Link className="boton mt-5" to="/citas">Volver a citas</Link>
  </section>;
  return children ?? <Outlet />;
}
