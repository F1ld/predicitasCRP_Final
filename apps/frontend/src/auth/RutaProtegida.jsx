import { Link, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./useAuth";
import Cargando from "../components/Cargando";

export default function RutaProtegida({ roles }) {
  const { usuario, cargando, tieneRol } = useAuth();
  if (cargando) return <Cargando texto="Verificando sesión…" />;
  if (!usuario) return <Navigate to="/login" replace />;
  if (roles && !tieneRol(...roles)) return <section className="tarjeta mx-auto max-w-xl">
    <h1>No tienes permiso para esta sección</h1>
    <p className="mt-3 text-slate-600">Tu rol permite consultar citas, pero no realizar esta operación.</p>
    <Link className="boton mt-5" to="/citas">Volver a citas</Link>
  </section>;
  return <Outlet />;
}
