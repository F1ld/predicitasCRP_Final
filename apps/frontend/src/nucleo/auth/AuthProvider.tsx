import { useEffect, useRef, useState } from "react";
import type { PropsWithChildren } from "react";
import { api, ApiError, esCancelacion, SESION_EXPIRADA, token } from "../api/cliente";
import type { Rol, TokenOut, Usuario } from "../api/tipos";
import { ContextoSesion } from "./contexto";

/** RF-001, RF-002: conserva la sesión actual; renovación/inactividad corresponden a T-021. */
export function AuthProvider({ children }: PropsWithChildren) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
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
      void api<Usuario>("/auth/me", { signal: controlador.signal }).then(
        (datos) => {
          if (actual === version.current) {
            setUsuario(datos);
            setCargando(false);
          }
        },
        (error: unknown) => {
          if (!esCancelacion(error) && actual === version.current) {
            token.borrar();
            setUsuario(null);
            setCargando(false);
            setMensajeSesion(error instanceof Error ? error.message : "No se pudo completar la solicitud.");
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

  async function iniciarSesion(correo: string, clave: string): Promise<void> {
    const actual = ++version.current;
    setMensajeSesion("");
    try {
      const credenciales = await api<TokenOut>("/auth/login", {
        metodo: "POST", form: { username: correo.trim(), password: clave },
      });
      if (actual !== version.current) return;
      if (!credenciales) throw new ApiError(204, "RESPUESTA_INVALIDA");
      token.guardar(credenciales.access_token);
      const datos = await api<Usuario>("/auth/me");
      if (actual === version.current) setUsuario(datos);
    } catch (error: unknown) {
      if (actual === version.current) {
        token.borrar();
        setUsuario(null);
      }
      throw error;
    }
  }

  async function cerrarSesion(): Promise<void> {
    version.current += 1;
    try { await api<void>("/auth/logout", { metodo: "POST" }); }
    catch { /* RF-002: el cierre local también se realiza si la API no está disponible. */ }
    finally {
      token.borrar();
      setUsuario(null);
      setMensajeSesion("");
    }
  }

  return <ContextoSesion.Provider value={{ usuario, cargando, mensajeSesion, iniciarSesion,
    cerrarSesion, tieneRol: (...roles: Rol[]) => usuario !== null && roles.includes(usuario.rol) }}>
    {children}
  </ContextoSesion.Provider>;
}
