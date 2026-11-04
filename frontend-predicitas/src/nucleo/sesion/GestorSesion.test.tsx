import { act, render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ContextoSesion } from "../auth/contexto";
import { token } from "../api/cliente";
import type { Rol, Usuario } from "../api/tipos";
import GestorSesion from "./GestorSesion";

const usuario: Usuario = {
  id_usuario: 7, nombre_completo: "Usuario sintético", correo_institucional: "tecnico@predicitas.crp",
  rol: "TECNICO_IA", activo: true, creado_en: "2026-10-18T10:00:00-05:00", actualizado_en: null,
};
function Aplicacion({ rol = "TECNICO_IA", ruta = "/citas", sinUsuario = false }: { rol?: Rol; ruta?: string; sinUsuario?: boolean }) {
  return <StrictMode><ContextoSesion.Provider value={{
    usuario: sinUsuario ? null : { ...usuario, rol }, cargando: false, mensajeSesion: "",
    iniciarSesion: vi.fn(), cerrarSesion: vi.fn(), tieneRol: (permitido) => permitido === rol,
  }}><MemoryRouter initialEntries={[ruta]}><GestorSesion /><Routes>
    <Route path="/" element={<h1>Inicio permitido</h1>} />
    <Route path="/usuarios/*" element={<h1>Usuarios</h1>} />
    <Route path="/citas" element={<h1>Citas</h1>} />
    <Route path="/login" element={<h1>Iniciar sesión</h1>} />
  </Routes></MemoryRouter></ContextoSesion.Provider></StrictMode>;
}

// RF-002, RF-003, RNF-004: integración del efecto, StrictMode, guard de M01 y navegación al expirar.
describe("GestorSesion", () => {
  const fetchMock = vi.fn<typeof fetch>();
  beforeEach(() => {
    vi.useFakeTimers();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("BroadcastChannel", undefined);
    sessionStorage.clear();
  });
  afterEach(() => vi.useRealTimers());

  it("StrictMode no duplica timers ni logout y vuelve al login por inactividad", async () => {
    token.guardar("token-sintetico");
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    render(<Aplicacion />);
    expect(screen.getByRole("heading", { name: "Citas" })).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(30 * 60_000); });
    expect(screen.getByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(token.leer()).toBeNull();
  });

  it.each<Rol>(["RECEPCION", "TECNICO_IA"])("redirige %s al inicio sin consultar usuarios", (rol) => {
    render(<Aplicacion rol={rol} ruta="/usuarios" />);
    expect(screen.getByRole("heading", { name: "Inicio permitido" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("también protege las subrutas de Usuarios", () => {
    render(<Aplicacion ruta="/usuarios/7" />);
    expect(screen.getByRole("heading", { name: "Inicio permitido" })).toBeInTheDocument();
  });

  it("conserva la ruta del administrador", () => {
    render(<Aplicacion rol="ADMINISTRADOR" ruta="/usuarios" />);
    expect(screen.getByRole("heading", { name: "Usuarios" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sin usuario el efecto no consulta ni programa vencimientos", async () => {
    render(<Aplicacion sinUsuario />);
    await act(async () => { await vi.advanceTimersByTimeAsync(40 * 60_000); });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "Citas" })).toBeInTheDocument();
  });
});
