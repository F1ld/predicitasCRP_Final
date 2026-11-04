import { Link, Navigate, Route, Routes } from "react-router-dom";
import RutaProtegida from "./nucleo/auth/RutaProtegida";
import { useAuth } from "./nucleo/auth/useAuth";
import Layout from "./nucleo/layout/Layout";
import { inicioPorRol, type ModuloRutas, type RutaModulo } from "./nucleo/layout/ranuras";
import type { Rol } from "./nucleo/api/tipos";

// T-012, RF-003: un módulo nuevo solo publica rutas.tsx y menu.ts.
const modulos = import.meta.glob<ModuloRutas>("./modulos/*/rutas.tsx", { eager: true });
const rutas: RutaModulo[] = Object.values(modulos).flatMap((modulo) => modulo.default);
const ROLES: Rol[] = ["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"];

function Inicio() {
  const { usuario } = useAuth();
  return <Navigate to={usuario ? inicioPorRol(usuario.rol, rutas) : "/login"} replace />;
}

export default function App() {
  return <Routes>
    {rutas.filter((ruta) => ruta.roles.includes("publico")).map((ruta) => <Route key={ruta.ruta} path={ruta.ruta} element={ruta.elemento} />)}
    <Route element={<RutaProtegida roles={ROLES} />}>
      <Route element={<Layout />}>
        <Route path="/" element={<Inicio />} />
        {rutas.filter((ruta) => !ruta.roles.includes("publico")).map((ruta) => <Route key={ruta.ruta} element={<RutaProtegida roles={ruta.roles.filter((rol): rol is Rol => rol !== "publico")} />}>
          <Route path={ruta.ruta} element={ruta.elemento} />
        </Route>)}
        <Route path="/importar" element={<Navigate to="/citas/importar" replace />} />
      </Route>
    </Route>
    <Route path="*" element={<main className="mx-auto max-w-lg space-y-4 p-8"><h1>Página no encontrada</h1><Link className="boton" to="/">Volver al inicio</Link></main>} />
  </Routes>;
}
