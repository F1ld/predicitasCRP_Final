import RelojLocal from "../componentes/RelojLocal";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { etiqueta } from "../formato/formato";
import Marca from "../componentes/Marca";
import Icono from "../componentes/Icono";
import { menuPorRol, type ModuloMenu } from "./ranuras";
import GestorSesion from "../sesion/GestorSesion";

const modulosMenu = import.meta.glob<ModuloMenu>("../../modulos/*/menu.ts", { eager: true });
const fixturesMenu = import.meta.env.MODE === "test"
  ? import.meta.glob<ModuloMenu>("../../pruebas/modulos/*/menu.ts", { eager: true })
  : {};

// RF-003, RNF-007: navegación por rol.
export default function Layout() {
  const { usuario, cerrarSesion } = useAuth();
  const [saliendo, setSaliendo] = useState(false);
  const [menuAbierto, setMenuAbierto] = useState(() => !window.matchMedia?.("(max-width: 760px)").matches);
  const { pathname } = useLocation();
  if (!usuario) return null;
  const entradas = menuPorRol({ ...modulosMenu, ...fixturesMenu }, usuario.rol);
  const estiloEnlace = ({ isActive }: { isActive: boolean }) => `nav-enlace ${isActive ? "activo" : ""}`;
  async function salir() {
    if (saliendo) return;
    setSaliendo(true);
    try { await cerrarSesion(); } finally { setSaliendo(false); }
  }
  return <div className={menuAbierto ? "app-shell" : "app-shell menu-plegado"}>
    <GestorSesion />
    <a className="saltar-contenido" href="#contenido">Ir al contenido</a>
    <aside className="barra-lateral">
      <div className="barra-lateral-cabecera">
        {menuAbierto && <NavLink to="/" aria-label="PrediCitas CRP, inicio" className="marca-enlace"><Marca lateral /></NavLink>}
        <button
          type="button"
          className="barra-lateral-control"
          aria-controls="menu-principal"
          aria-expanded={menuAbierto}
          aria-label={menuAbierto ? "Plegar navegación" : "Desplegar navegación"}
          onClick={() => setMenuAbierto((abierto) => !abierto)}
        >
          <Icono nombre="menu" />
        </button>
      </div>
      <nav id="menu-principal" aria-label="Principal">
        {entradas.map((entrada) => <NavLink key={entrada.ruta} to={entrada.ruta}
          end={entradas.some((otra) => otra.ruta.startsWith(`${entrada.ruta}/`) && (pathname === otra.ruta || pathname.startsWith(`${otra.ruta}/`)))}
          className={estiloEnlace}
          aria-label={entrada.etiqueta}
          title={menuAbierto ? undefined : entrada.etiqueta}
          onClick={() => { if (window.matchMedia?.("(max-width: 760px)").matches) setMenuAbierto(false); }}>
          <Icono nombre={entrada.icono} /><span hidden={!menuAbierto}>{entrada.etiqueta}</span>
        </NavLink>)}
      </nav>
    </aside>
    <div className="franja-institucional"><div className="ancho-app"><span>Clínica Ricardo Palma</span><span>San Isidro</span></div></div>
    <header className="cabecera-app">
      <div className="ancho-app cabecera-fila">
        <div className="perfil">
          <span className="avatar" aria-hidden="true">{usuario.nombre_completo.trim().charAt(0)}</span>
          <div className="perfil-datos"><p>{usuario.nombre_completo}</p><span>{etiqueta(usuario.rol)}</span></div>
          <button className="salir-sesion" disabled={saliendo} onClick={salir}><Icono nombre="salir" /><span>{saliendo ? "Cerrando…" : "Cerrar sesión"}</span></button>
        </div>
      </div>
    </header>
    <main key={pathname} id="contenido" tabIndex={-1} className="ancho-app contenido-app"><Outlet /></main>
    <footer className="pie-app ancho-app"><span>PrediCitas · San Isidro</span><RelojLocal /></footer>
  </div>;
}
