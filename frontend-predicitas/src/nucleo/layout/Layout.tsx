import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { etiqueta } from "../formato/formato";
import Marca from "../componentes/Marca";
import Icono from "../componentes/Icono";
import { menuPorRol, type ModuloMenu } from "./ranuras";
import GestorSesion from "../sesion/GestorSesion";

const modulosMenu = import.meta.glob<ModuloMenu>("../../modulos/*/menu.ts", { eager: true });

// RF-003, RNF-007: menú por rol y aviso visible del entorno de demostración.
export default function Layout() {
  const { usuario, cerrarSesion } = useAuth();
  const [saliendo, setSaliendo] = useState(false);
  const { pathname } = useLocation();
  if (!usuario) return null;
  const entradas = menuPorRol(modulosMenu, usuario.rol);
  const estiloEnlace = ({ isActive }: { isActive: boolean }) => `nav-enlace ${isActive ? "activo" : ""}`;
  async function salir() {
    if (saliendo) return;
    setSaliendo(true);
    try { await cerrarSesion(); } finally { setSaliendo(false); }
  }
  return <div className="app-shell">
    <GestorSesion />
    <a className="saltar-contenido" href="#contenido">Ir al contenido</a>
    <div className="franja-institucional"><div className="ancho-app"><span>Clínica Ricardo Palma</span><span>San Isidro · Entorno de demostración</span></div></div>
    <header className="cabecera-app">
      <div className="ancho-app cabecera-fila">
        <NavLink to="/" aria-label="PrediCitas CRP, inicio" className="marca-enlace"><Marca /></NavLink>
        <div className="perfil">
          <span className="avatar" aria-hidden="true">{usuario.nombre_completo.trim().charAt(0)}</span>
          <div className="perfil-datos"><p>{usuario.nombre_completo}</p><span>{etiqueta(usuario.rol)}</span></div>
          <button className="salir-sesion" disabled={saliendo} onClick={salir}><Icono nombre="salir" /><span>{saliendo ? "Cerrando…" : "Cerrar sesión"}</span></button>
        </div>
      </div>
      <div className="ancho-app navegacion-fila">
        <nav aria-label="Principal">
          {entradas.map((entrada) => <NavLink key={entrada.ruta} to={entrada.ruta}
            end={entradas.some((otra) => otra.ruta.startsWith(`${entrada.ruta}/`) && (pathname === otra.ruta || pathname.startsWith(`${otra.ruta}/`)))}
            className={estiloEnlace}><Icono nombre={entrada.icono} />{entrada.etiqueta}</NavLink>)}
        </nav>
        <span className="nota-navegacion">Seguimiento de citas médicas</span>
      </div>
    </header>
    <main id="contenido" tabIndex={-1} className="ancho-app contenido-app"><Outlet /></main>
    <footer className="pie-app ancho-app"><span>PrediCitas · Piloto San Isidro</span><span>Datos sintéticos de demostración <span aria-hidden="true">/</span> Horario de Lima</span></footer>
  </div>;
}
