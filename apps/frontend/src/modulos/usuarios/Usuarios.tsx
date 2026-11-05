import { useState, type FormEvent } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import type { Pagina } from "../../nucleo/api/tipos";
import { useConsulta } from "../../nucleo/api/useConsulta";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import Icono from "../../nucleo/componentes/Icono";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta } from "../../nucleo/formato/formato";
import { CambiarEstado, RestablecerAcceso } from "./AccionesUsuario";
import FormularioUsuario from "./FormularioUsuario";
import { ROLES, type UsuarioOut } from "./tipos";
import "./usuarios.css";

type Accion = { tipo: "crear" } | { tipo: "editar" | "estado" | "restablecer"; usuario: UsuarioOut };

// RF-003, RF-004, RNF-001: defensa local además de la ranura protegida del router.
export default function Usuarios() {
  const { usuario, cargando } = useAuth();
  if (cargando) return <Cargando texto="Verificando sesión…" />;
  if (usuario?.rol !== "ADMINISTRADOR") return <Navigate to="/" replace />;
  return <ListaUsuarios />;
}

// RF-004 a RF-008, RNF-016: cuatro estados, filtros y paginación persistentes en URL.
function ListaUsuarios() {
  const [busqueda, setBusqueda] = useSearchParams();
  const [accion, setAccion] = useState<Accion | null>(null);
  const [aviso, setAviso] = useState("");
  const valorLimite = Number(busqueda.get("limite") || 50);
  const limite = Number.isSafeInteger(valorLimite) && valorLimite >= 1 && valorLimite <= 200 ? valorLimite : 50;
  const valorDesplazamiento = Number(busqueda.get("desplazamiento") || 0);
  const desplazamiento = Number.isSafeInteger(valorDesplazamiento) && valorDesplazamiento >= 0 ? valorDesplazamiento : 0;
  const rol = ROLES.find((valor) => valor === busqueda.get("rol")) ?? "";
  const activo = ["true", "false"].find((valor) => valor === busqueda.get("activo")) ?? "";
  const consulta = new URLSearchParams({ limite: String(limite), desplazamiento: String(desplazamiento) });
  if (busqueda.get("q")?.trim()) consulta.set("q", busqueda.get("q")!.trim());
  if (rol) consulta.set("rol", rol);
  if (activo) consulta.set("activo", activo);
  const { datos, error, cargando, reintentar } = useConsulta<Pagina<UsuarioOut>>(`/usuarios?${consulta}`);

  function aplicar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const formulario = new FormData(evento.currentTarget);
    const nuevos = new URLSearchParams();
    ["q", "rol", "activo", "limite"].forEach((campo) => {
      const valor = String(formulario.get(campo) ?? "").trim();
      if (valor) nuevos.set(campo, valor);
    });
    setBusqueda(nuevos);
  }

  function pagina(nuevo: number) {
    const siguientes = new URLSearchParams(busqueda);
    siguientes.set("desplazamiento", String(nuevo));
    setBusqueda(siguientes);
  }

  function completado(mensaje: string) { setAccion(null); setAviso(mensaje); reintentar(); }

  return <>
    <div className="pagina-titulo"><div><p className="sobretitulo">ADMINISTRACIÓN</p><h1>Usuarios</h1><p>Gestiona las cuentas y los permisos de acceso a PrediCitas.</p></div><button className="boton" onClick={() => { setAviso(""); setAccion({ tipo: "crear" }); }}>Crear usuario</button></div>
    <form key={busqueda.toString()} className="tarjeta filtros-citas" onSubmit={aplicar}>
      <div className="seccion-cabecera"><h2><Icono nombre="filtro" />Buscar usuarios</h2><p>Filtra por nombre, correo, rol o estado.</p></div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div><label htmlFor="usuarios-q">Nombre o correo</label><input id="usuarios-q" name="q" type="search" defaultValue={busqueda.get("q") ?? ""} placeholder="Buscar usuario" /></div>
        <div><label htmlFor="usuarios-rol">Rol</label><select id="usuarios-rol" name="rol" defaultValue={rol}><option value="">Todos los roles</option>{ROLES.map((valor) => <option key={valor} value={valor}>{etiqueta(valor)}</option>)}</select></div>
        <div><label htmlFor="usuarios-activo">Estado</label><select id="usuarios-activo" name="activo" defaultValue={activo}><option value="">Todos los estados</option><option value="true">Activo</option><option value="false">Inactivo</option></select></div>
        <div><label htmlFor="usuarios-limite">Por página</label><select id="usuarios-limite" name="limite" defaultValue={limite}>{Array.from(new Set([10, 20, 50, 100, 200, limite])).sort((a, b) => a - b).map((valor) => <option key={valor} value={valor}>{valor}</option>)}</select></div>
      </div>
      <div className="usuarios-acciones mt-4"><button className="boton" type="submit"><Icono nombre="buscar" />Aplicar filtros</button><button type="button" className="boton-secundario" onClick={() => setBusqueda({})}>Limpiar</button></div>
    </form>
    <Mensaje tipo="exito">{aviso}</Mensaje>
    {cargando ? <Cargando texto="Cargando usuarios…" /> : error || !datos ? <div className="space-y-3"><Mensaje>{error || "El servidor no devolvió la lista de usuarios."}</Mensaje><button className="boton-secundario" onClick={reintentar}>Reintentar</button></div> : <>
      <div className="resultados-cabecera"><h2>Usuarios encontrados <span className="contador-citas">{datos.total}</span></h2><p>Las cuentas se ordenan por nombre completo.</p></div>
      {datos.items.length === 0 ? <div className="tarjeta estado-vacio"><Icono nombre="escudo" /><p>No hay usuarios con esos filtros.</p><span>Prueba otra búsqueda o utiliza «Limpiar».</span></div> : <div className="tabla-contenedor" role="region" aria-label="Tabla de usuarios; desplázate horizontalmente para ver las acciones" tabIndex={0}>
        <table className="usuarios-tabla tabla-citas"><caption className="sr-only">Usuarios que cumplen los filtros aplicados</caption><thead><tr><th scope="col">Usuario</th><th scope="col">Rol</th><th scope="col">Estado</th><th scope="col">Acciones</th></tr></thead><tbody>
          {datos.items.map((usuario) => <tr key={usuario.id_usuario} className="fila-cita"><th scope="row">{usuario.nombre_completo}<span className="usuarios-correo">{usuario.correo_institucional}</span></th><td>{etiqueta(usuario.rol)}</td><td><span className={`estado-badge usuarios-estado-${usuario.activo ? "activo" : "inactivo"}`}>{usuario.activo ? "Activo" : "Inactivo"}</span></td><td><div className="usuarios-acciones">
            <button className="boton-secundario" aria-label={`Editar a ${usuario.nombre_completo}`} onClick={() => setAccion({ tipo: "editar", usuario })}>Editar</button>
            <button className="boton-secundario" aria-label={`${usuario.activo ? "Desactivar" : "Activar"} a ${usuario.nombre_completo}`} onClick={() => setAccion({ tipo: "estado", usuario })}>{usuario.activo ? "Desactivar" : "Activar"}</button>
            <button className="boton-secundario" aria-label={`Restablecer acceso de ${usuario.nombre_completo}`} onClick={() => setAccion({ tipo: "restablecer", usuario })}>Restablecer acceso</button>
          </div></td></tr>)}
        </tbody></table>
      </div>}
      <div className="paginacion"><p>Página {Math.floor(desplazamiento / limite) + 1} de {Math.max(1, Math.ceil(datos.total / limite))} · {datos.total} usuarios</p><div className="usuarios-acciones"><button className="boton-secundario" disabled={desplazamiento === 0} onClick={() => pagina(Math.max(0, desplazamiento - limite))}>Anterior</button><button className="boton-secundario" disabled={desplazamiento + limite >= datos.total} onClick={() => pagina(desplazamiento + limite)}>Siguiente</button></div></div>
    </>}
    {accion?.tipo === "crear" && <FormularioUsuario cerrar={() => setAccion(null)} completado={completado} />}
    {accion?.tipo === "editar" && <FormularioUsuario usuario={accion.usuario} cerrar={() => setAccion(null)} completado={completado} />}
    {accion?.tipo === "estado" && <CambiarEstado usuario={accion.usuario} cerrar={() => setAccion(null)} completado={completado} />}
    {accion?.tipo === "restablecer" && <RestablecerAcceso usuario={accion.usuario} cerrar={() => setAccion(null)} />}
  </>;
}
