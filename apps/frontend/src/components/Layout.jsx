import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { etiqueta } from "../lib/formato";
import { ROLES_ESCRITURA } from "../lib/transiciones";
import Marca from "./Marca";
import Icono from "./Icono";

export default function Layout() {
  const { usuario, cerrarSesion, tieneRol } = useAuth();
  const [saliendo, setSaliendo] = useState(false);
  const estiloEnlace = ({ isActive }) => `nav-enlace ${isActive ? "activo" : ""}`;
  async function salir() {
    if (saliendo) return;
    setSaliendo(true);
    try { await cerrarSesion(); } finally { setSaliendo(false); }
  }
  return <div className="app-shell">
    <a className="saltar-contenido" href="#contenido">Ir al contenido</a>
    <div className="franja-institucional"><div className="ancho-app"><span>Clínica Ricardo Palma</span><span>Sede San Isidro · Gestión Ambulatoria de Citas</span></div></div>
    <header className="cabecera-app">
      <div className="ancho-app cabecera-fila">
        <NavLink to="/citas" aria-label="PrediCitas CRP, inicio" className="marca-enlace"><Marca /></NavLink>
        <div className="perfil">
          <span className="avatar" aria-hidden="true">{usuario.nombre_completo.trim().charAt(0)}</span>
          <div className="perfil-datos"><p>{usuario.nombre_completo}</p><span>{etiqueta(usuario.rol)}</span></div>
          <button className="salir-sesion" disabled={saliendo} onClick={salir}><Icono nombre="salir" /><span>{saliendo ? "Cerrando…" : "Cerrar sesión"}</span></button>
        </div>
      </div>
      <div className="ancho-app navegacion-fila">
        <nav aria-label="Principal">
          <NavLink to="/citas" className={estiloEnlace}><Icono nombre="calendario" />Citas</NavLink>
          <NavLink to="/intervenciones" className={estiloEnlace}><Icono nombre="reloj" />Intervenciones</NavLink>
          <NavLink to="/reasignacion" className={estiloEnlace}><Icono nombre="calendario" />Cupos y Reasignación</NavLink>
          <NavLink to="/ia" className={estiloEnlace}><Icono nombre="exito" />Modelo IA</NavLink>
          {tieneRol(...ROLES_ESCRITURA) && <NavLink to="/importar" className={estiloEnlace}><Icono nombre="importar" />Importar CSV</NavLink>}
        </nav>
        <span className="nota-navegacion">Asistencia Predictiva y Seguimiento de Pacientes</span>
      </div>
    </header>
    <main id="contenido" tabIndex={-1} className="ancho-app contenido-app"><Outlet /></main>
    <footer className="pie-app ancho-app"><span>Clínica Ricardo Palma · Sede San Isidro</span><span>Asistencia predictiva para la gestión de citas médicas <span aria-hidden="true">/</span> Horario de Lima</span></footer>
  </div>;
}
