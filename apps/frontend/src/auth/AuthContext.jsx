import { useEffect, useRef, useState } from "react";
import { api, SESION_EXPIRADA, token } from "../lib/api";
import { ContextoSesion } from "./contexto";

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [cargando, setCargando] = useState(() => Boolean(token.leer()));
  const [mensajeSesion, setMensajeSesion] = useState("");
  const version = useRef(0);

  useEffect(() => {
    const controlador = new AbortController();
    const actual = ++version.current;
    const expirar = () => {
      version.current += 1;
      setUsuario(null);
      setCargando(false);
      setMensajeSesion("Tu sesión expiró. Inicia sesión nuevamente.");
    };
    window.addEventListener(SESION_EXPIRADA, expirar);
    if (token.leer()) {
      api("/auth/me", { signal: controlador.signal }).then(
        (datos) => {
          if (actual === version.current) { setUsuario(datos); setCargando(false); }
        },
        (error) => {
          if (error.name !== "AbortError" && actual === version.current) {
            token.borrar();
            setUsuario(null);
            setCargando(false);
            setMensajeSesion(error.message);
          }
        },
      );
    }
    return () => {
      version.current += 1;
      controlador.abort();
      window.removeEventListener(SESION_EXPIRADA, expirar);
    };
  }, []);

  async function iniciarSesion(correo, clave) {
    const actual = ++version.current;
    setMensajeSesion("");
    try {
      const credenciales = await api("/auth/login", {
        metodo: "POST", form: { username: correo.trim(), password: clave },
      });
      if (actual !== version.current) return;
      token.guardar(credenciales.access_token);
      const datos = await api("/auth/me");
      if (actual === version.current) setUsuario(datos);
    } catch (error) {
      if (actual === version.current) { token.borrar(); setUsuario(null); }
      throw error;
    }
  }

  async function cerrarSesion() {
    version.current += 1;
    try { await api("/auth/logout", { metodo: "POST" }); }
    catch { /* El cierre local se realiza también si la API no está disponible. */ }
    finally {
      token.borrar(); setUsuario(null); setMensajeSesion("");
    }
  }

  return <ContextoSesion.Provider value={{ usuario, cargando, mensajeSesion, iniciarSesion,
    cerrarSesion, tieneRol: (...roles) => roles.includes(usuario?.rol) }}>
    {children}
  </ContextoSesion.Provider>;
}
