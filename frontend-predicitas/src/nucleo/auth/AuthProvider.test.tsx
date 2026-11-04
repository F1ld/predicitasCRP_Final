import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Usuario } from "../api/tipos";
import { SESION_EXPIRADA, token } from "../api/cliente";
import { AuthProvider } from "./AuthProvider";
import { useAuth } from "./useAuth";

const usuario: Usuario = {
  id_usuario: 1, nombre_completo: "Usuario de prueba", correo_institucional: "recepcion@predicitas.crp",
  rol: "RECEPCION", activo: true, creado_en: "2026-10-18T10:00:00-05:00", actualizado_en: null,
};

function respuesta(datos: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(datos), {
    status, headers: { "Content-Type": "application/json" },
  });
}

function EstadoSesion() {
  const auth = useAuth();
  return <>
    <p>{auth.cargando ? "Cargando sesión" : "Sesión lista"}</p>
    <p>{auth.usuario?.nombre_completo ?? "Anónimo"}</p>
    <p>{auth.mensajeSesion}</p>
    <p>{auth.tieneRol("RECEPCION") ? "Recepción permitida" : "Recepción denegada"}</p>
    <button onClick={() => { void auth.iniciarSesion(" recepcion@predicitas.crp ", "Clave123").catch(() => undefined); }}>Entrar</button>
    <button onClick={() => { void auth.cerrarSesion(); }}>Salir</button>
  </>;
}

// RF-001, RF-002, RNF-001: sesión sintética, caducidad y cierre sin datos personales.
describe("AuthProvider", () => {
  const fetchMock = vi.fn<typeof fetch>();
  beforeEach(() => {
    sessionStorage.clear();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("comienza sin sesión y sin consultar la API si falta el token", () => {
    render(<AuthProvider><EstadoSesion /></AuthProvider>);
    expect(screen.getByText("Sesión lista")).toBeInTheDocument();
    expect(screen.getByText("Anónimo")).toBeInTheDocument();
    expect(screen.getByText("Recepción denegada")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("restaura el usuario y verifica el rol con el token de sessionStorage", async () => {
    token.guardar("token-previo");
    fetchMock.mockResolvedValue(respuesta(usuario));
    render(<AuthProvider><EstadoSesion /></AuthProvider>);
    expect(screen.getByText("Cargando sesión")).toBeInTheDocument();
    expect(await screen.findByText(usuario.nombre_completo)).toBeInTheDocument();
    expect(screen.getByText("Recepción permitida")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0]?.[1]?.headers).toMatchObject({ Authorization: "Bearer token-previo" });
  });

  it("envía las credenciales sin espacios externos y conserva solo el token", async () => {
    fetchMock.mockResolvedValueOnce(respuesta({ access_token: "token-nuevo", token_type: "bearer", expires_in: 1800 }))
      .mockResolvedValueOnce(respuesta(usuario));
    render(<AuthProvider><EstadoSesion /></AuthProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByText(usuario.nombre_completo)).toBeInTheDocument();
    const cuerpo = fetchMock.mock.calls[0]?.[1]?.body;
    expect(cuerpo).toBeInstanceOf(URLSearchParams);
    expect(String(cuerpo)).toBe("username=recepcion%40predicitas.crp&password=Clave123");
    expect(token.leer()).toBe("token-nuevo");
    expect(sessionStorage.length).toBe(1);
  });

  it("limpia una restauración fallida y presenta un mensaje legible", async () => {
    token.guardar("token-previo");
    fetchMock.mockResolvedValue(respuesta({ error: { codigo: "ERROR_INTERNO", mensaje: "Servidor temporalmente no disponible." } }, 500));
    render(<AuthProvider><EstadoSesion /></AuthProvider>);
    expect(await screen.findByText("Servidor temporalmente no disponible.")).toBeInTheDocument();
    expect(screen.getByText("Anónimo")).toBeInTheDocument();
    expect(token.leer()).toBeNull();
  });

  it("invalida la sesión cuando el cliente recibe 401 SESION_INVALIDA", async () => {
    token.guardar("token-vencido");
    fetchMock.mockResolvedValue(respuesta({ error: { codigo: "SESION_INVALIDA", mensaje: "Sesión inválida" } }, 401));
    render(<AuthProvider><EstadoSesion /></AuthProvider>);
    expect(await screen.findByText("Tu sesión expiró. Inicia sesión nuevamente.")).toBeInTheDocument();
    expect(token.leer()).toBeNull();
    expect(screen.getByText("Sesión lista")).toBeInTheDocument();
  });

  it("cierra sesión contra la API y elimina la credencial local", async () => {
    token.guardar("token-previo");
    fetchMock.mockResolvedValueOnce(respuesta(usuario)).mockResolvedValueOnce(respuesta(null, 204));
    render(<AuthProvider><EstadoSesion /></AuthProvider>);
    await screen.findByText(usuario.nombre_completo);
    fireEvent.click(screen.getByRole("button", { name: "Salir" }));
    await waitFor(() => expect(screen.getByText("Anónimo")).toBeInTheDocument());
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain("/auth/logout");
    expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("POST");
    expect(token.leer()).toBeNull();
  });

  it("realiza el cierre local aunque falle la conexión de logout", async () => {
    token.guardar("token-previo");
    fetchMock.mockResolvedValueOnce(respuesta(usuario)).mockRejectedValueOnce(new TypeError("Sin red"));
    render(<AuthProvider><EstadoSesion /></AuthProvider>);
    await screen.findByText(usuario.nombre_completo);
    fireEvent.click(screen.getByRole("button", { name: "Salir" }));
    await waitFor(() => expect(screen.getByText("Anónimo")).toBeInTheDocument());
    expect(token.leer()).toBeNull();
  });

  it("elimina el token si falla /auth/me después del login", async () => {
    fetchMock.mockResolvedValueOnce(respuesta({ access_token: "token-nuevo", token_type: "bearer", expires_in: 1800 }))
      .mockResolvedValueOnce(respuesta({ error: { codigo: "ERROR_INTERNO", mensaje: "Fallo de usuario" } }, 500));
    render(<AuthProvider><EstadoSesion /></AuthProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(token.leer()).toBeNull());
    expect(screen.getByText("Anónimo")).toBeInTheDocument();
  });

  it("no restaura una respuesta antigua después del evento de caducidad", async () => {
    token.guardar("token-previo");
    let completar: ((respuesta: Response) => void) | undefined;
    fetchMock.mockImplementation(() => new Promise((resolver) => { completar = resolver; }));
    const vista = render(<AuthProvider><EstadoSesion /></AuthProvider>);
    act(() => { window.dispatchEvent(new Event(SESION_EXPIRADA)); });
    await act(async () => { completar?.(respuesta(usuario)); });
    expect(screen.getByText("Anónimo")).toBeInTheDocument();
    expect(screen.queryByText(usuario.nombre_completo)).not.toBeInTheDocument();
    const señal = fetchMock.mock.calls[0]?.[1]?.signal;
    vista.unmount();
    expect(señal?.aborted).toBe(true);
  });
});

describe("useAuth", () => {
  it("exige AuthProvider para no usar una sesión inexistente (RF-001)", () => {
    const silenciar = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const errorEsperado = (evento: ErrorEvent) => {
      if (evento.error instanceof Error && evento.error.message === "useAuth requiere AuthProvider.") {
        evento.preventDefault();
      }
    };
    window.addEventListener("error", errorEsperado);
    try { expect(() => render(<EstadoSesion />)).toThrow("useAuth requiere AuthProvider."); }
    finally {
      window.removeEventListener("error", errorEsperado);
      silenciar.mockRestore();
    }
  });
});
