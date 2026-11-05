import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, token } from "../../nucleo/api/cliente";
import type { TokenOut, Usuario } from "../../nucleo/api/tipos";
import { useConsulta } from "../../nucleo/api/useConsulta";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta, formatearFechaHora } from "../../nucleo/formato/formato";
import { guardarTokenRenovado, suspenderRenovacion } from "../../nucleo/sesion";
import { errorClave } from "./politicaClave";
import "./cuenta.css";

type CampoClave = "clave_actual" | "clave_nueva" | "confirmacion";
const VACIOS: Record<CampoClave, string> = { clave_actual: "", clave_nueva: "", confirmacion: "" };

// M01-V05, RF-008, RNF-004: cambio de clave propio con sustitución del JWT.
export default function MiCuenta() {
  const { datos: usuario, cargando, error, reintentar } = useConsulta<Usuario>("/auth/me");
  const [campos, setCampos] = useState(VACIOS);
  const [tocados, setTocados] = useState<Partial<Record<CampoClave, boolean>>>({});
  const [erroresServidor, setErroresServidor] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState("");
  const [exito, setExito] = useState("");
  const enCurso = useRef(false);
  const montado = useRef(true);
  useEffect(() => { montado.current = true; return () => { montado.current = false; }; }, []);

  const erroresLocales: Record<CampoClave, string> = {
    clave_actual: campos.clave_actual ? "" : "Ingresa tu contraseña actual.",
    clave_nueva: errorClave(campos.clave_nueva) || (campos.clave_nueva === campos.clave_actual ? "La nueva contraseña debe ser distinta de la actual." : ""),
    confirmacion: campos.confirmacion === campos.clave_nueva && campos.confirmacion ? "" : "Las contraseñas nuevas deben coincidir.",
  };

  function cambiar(campo: CampoClave, valor: string) {
    setCampos((actuales) => ({ ...actuales, [campo]: valor }));
    setTocados((actuales) => ({ ...actuales, [campo]: true }));
    setErroresServidor((actuales) => Object.fromEntries(Object.entries(actuales).filter(([nombre]) => nombre !== campo)));
    setFallo(""); setExito("");
  }

  async function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (enCurso.current) return;
    setTocados({ clave_actual: true, clave_nueva: true, confirmacion: true });
    if (Object.values(erroresLocales).some(Boolean)) return;
    const credencialAnterior = token.leer();
    if (!credencialAnterior) { setFallo("Tu sesión no está disponible. Vuelve a iniciar sesión."); return; }
    const reanudarRenovacion = suspenderRenovacion(credencialAnterior);
    enCurso.current = true;
    setEnviando(true); setFallo(""); setExito(""); setErroresServidor({});
    try {
      const nueva = await api<TokenOut>("/auth/cambiar-clave", { metodo: "POST", json: { clave_actual: campos.clave_actual, clave_nueva: campos.clave_nueva } });
      if (!nueva) throw new ApiError(204, "RESPUESTA_INVALIDA");
      // No se restaura una sesión que terminó o cambió mientras el POST esperaba.
      const guardada = guardarTokenRenovado(nueva, credencialAnterior);
      if (montado.current && guardada) {
        setCampos(VACIOS); setTocados({}); setExito("Contraseña actualizada.");
        reintentar();
      }
    } catch (errorCambio: unknown) {
      if (montado.current) {
        setFallo(errorCambio instanceof ApiError && errorCambio.codigo === "CLAVE_ACTUAL_INCORRECTA"
          ? "La contraseña actual no es correcta."
          : errorCambio instanceof Error ? errorCambio.message : "No se pudo completar la solicitud.");
        if (errorCambio instanceof ApiError) setErroresServidor(errorCambio.campos);
      }
    } finally {
      reanudarRenovacion();
      enCurso.current = false;
      if (montado.current) setEnviando(false);
    }
  }

  if (cargando) return <Cargando texto="Cargando mi cuenta…" />;
  if (error) return <div className="space-y-4"><h1>Mi cuenta</h1><Mensaje>{error}</Mensaje><button className="boton-secundario" onClick={reintentar}>Reintentar</button></div>;
  if (!usuario) return <div className="space-y-4"><h1>Mi cuenta</h1><Mensaje tipo="info">No se recibieron los datos de tu cuenta.</Mensaje><button className="boton-secundario" onClick={reintentar}>Reintentar</button></div>;

  function campoClave(campo: CampoClave, nombre: string, autocomplete: "current-password" | "new-password") {
    const mensaje = erroresServidor[campo] || (tocados[campo] ? erroresLocales[campo] : "");
    return <div><label htmlFor={campo}>{nombre}</label><input id={campo} name={campo} type="password" autoComplete={autocomplete}
      value={campos[campo]} maxLength={128} required aria-invalid={Boolean(mensaje)}
      aria-describedby={`${campo}-ayuda`} onChange={(evento) => cambiar(campo, evento.target.value)}
      onBlur={() => setTocados((actuales) => ({ ...actuales, [campo]: true }))} />
      <p id={`${campo}-ayuda`} className={mensaje ? "cuenta-error" : "cuenta-ayuda"} aria-live="polite">
        {mensaje || (campo === "clave_nueva" ? "Entre 8 y 128 caracteres, con al menos una letra y un número." : campo === "confirmacion" ? "Vuelve a escribir la nueva contraseña." : "Usa la contraseña con la que ingresaste.")}
      </p></div>;
  }

  return <>
    <div className="pagina-titulo"><div><p className="sobretitulo">ACCESO DEL EQUIPO</p><h1>Mi cuenta</h1><p>Consulta tus datos y mantén tu acceso al día.</p></div></div>
    {fallo && <Mensaje>{fallo}</Mensaje>}{exito && <Mensaje tipo="exito">{exito}</Mensaje>}
    <div className="cuenta-layout">
      <section className="tarjeta"><h2>Datos de tu cuenta</h2><dl className="cuenta-datos">
        <div><dt>Nombre completo</dt><dd>{usuario.nombre_completo}</dd></div>
        <div><dt>Correo institucional</dt><dd>{usuario.correo_institucional}</dd></div>
        <div><dt>Rol</dt><dd>{etiqueta(usuario.rol)}</dd></div>
        <div><dt>Estado</dt><dd>{usuario.activo ? "Activo" : "Inactivo"}</dd></div>
        <div><dt>Creación</dt><dd>{formatearFechaHora(usuario.creado_en)}</dd></div>
        <div><dt>Última actualización</dt><dd>{formatearFechaHora(usuario.actualizado_en)}</dd></div>
      </dl></section>
      <section className="tarjeta"><h2>Cambiar contraseña</h2><p className="ayuda-seccion">Elige una contraseña distinta de la actual. No la compartas con otras personas.</p>
        <form onSubmit={(evento) => { void guardar(evento); }} noValidate><fieldset className="cuenta-formulario" disabled={enviando}>
          {campoClave("clave_actual", "Contraseña actual", "current-password")}
          {campoClave("clave_nueva", "Nueva contraseña", "new-password")}
          {campoClave("confirmacion", "Confirmar nueva contraseña", "new-password")}
          <div><button className="boton" type="submit" disabled={enviando || Object.values(erroresLocales).some(Boolean)}>{enviando ? "Guardando…" : "Cambiar contraseña"}</button></div>
        </fieldset></form>
      </section>
    </div>
  </>;
}
