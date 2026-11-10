import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import App from "../../App";
import { paginaPrueba, resumenPrueba } from "../../pruebas/panel";
import { ContextoSesion, type ContextoAuth } from "../../nucleo/auth/contexto";
import type { Rol, Usuario } from "../../nucleo/api/tipos";

function mostrar(rol: Rol, ruta: string) {
  const usuario: Usuario = { id_usuario: 1, nombre_completo: "Cuenta sintética M01", correo_institucional: "cuenta@predicitas.crp", rol, activo: true, creado_en: "2026-10-18T09:00:00-05:00", actualizado_en: null };
  const contexto: ContextoAuth = { usuario, cargando: false, mensajeSesion: "", iniciarSesion: vi.fn(), cerrarSesion: vi.fn(), tieneRol: (...roles) => roles.includes(rol) };
  const fetch = vi.fn<typeof window.fetch>(async (url) => {
    const rutaApi = new URL(String(url)).pathname;
    const datos = rutaApi === "/auth/me" ? usuario
      : rutaApi === "/panel/resumen" ? { ...resumenPrueba(), fecha: new URL(String(url)).searchParams.get("fecha") }
      : rutaApi === "/panel/pendientes" ? { ...paginaPrueba(), fecha: new URL(String(url)).searchParams.get("fecha") }
      : rutaApi === "/citas/catalogos" ? { especialidades: [], estados: [], niveles_riesgo: [], medicos: [], canales_origen: [], tipos_paciente: [] }
      : { total: 0, limite: 50, desplazamiento: 0, items: [] };
    return new Response(JSON.stringify(datos), { status: 200 });
  });
  vi.stubGlobal("fetch", fetch);
  render(<ContextoSesion.Provider value={contexto}><MemoryRouter initialEntries={[ruta]}><App /></MemoryRouter></ContextoSesion.Provider>);
  return fetch;
}

// RF-003 a RF-008, RNF-001: permisos efectivos del router y menú reales (CP-M01-04/05).
describe("M01 integrado mediante las ranuras de T-012", () => {
  it.each<Rol>(["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"])("Mi cuenta es accesible por URL y el menú respeta el rol %s", async (rol) => {
    mostrar(rol, "/mi-cuenta");
    expect(await screen.findByRole("heading", { name: "Mi cuenta" })).toBeInTheDocument();
    const navegacion = within(screen.getByRole("navigation", { name: "Principal" }));
    expect(navegacion.queryByRole("link", { name: "Mi cuenta" })).not.toBeInTheDocument();
    expect(navegacion.queryByRole("link", { name: "Modelo IA" })).not.toBeInTheDocument();
    if (rol === "ADMINISTRADOR") {
      expect(navegacion.getByRole("link", { name: "Usuarios" })).toHaveAttribute("href", "/usuarios");
    } else {
      expect(navegacion.queryByRole("link", { name: "Usuarios" })).not.toBeInTheDocument();
    }
  });

  it("permite plegar y volver a desplegar la navegación", () => {
    mostrar("RECEPCION", "/citas");
    fireEvent.click(screen.getByRole("button", { name: "Plegar navegación" }));
    const citas = within(screen.getByRole("navigation", { name: "Principal" })).getByRole("link", { name: "Citas" });
    expect(citas).toHaveAttribute("href", "/citas");
    expect(within(citas).getByText("Citas")).not.toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Desplegar navegación" }));
    expect(within(citas).getByText("Citas")).toBeVisible();
  });

  it.each<Rol>(["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"])("retira la pantalla Modelo IA para %s", (rol) => {
    mostrar(rol, "/ia");
    expect(screen.getByRole("heading", { name: "Página no encontrada" })).toBeInTheDocument();
  });

  it.each<Rol>(["RECEPCION", "TECNICO_IA"])("devuelve al inicio a %s sin consultar usuarios", async (rol) => {
    const fetch = mostrar(rol, "/usuarios");
    await waitFor(() => expect(screen.getByRole("heading", { name: rol === "RECEPCION" ? "Panel operativo" : "Bandeja de citas" })).toBeInTheDocument());
    expect(screen.queryByRole("heading", { name: "Usuarios" })).not.toBeInTheDocument();
    expect(fetch.mock.calls.some(([url]) => new URL(String(url)).pathname.startsWith("/usuarios"))).toBe(false);
  });

  it("permite al administrador consultar el módulo Usuarios", async () => {
    const fetch = mostrar("ADMINISTRADOR", "/usuarios");
    expect(await screen.findByRole("heading", { name: "Usuarios" })).toBeInTheDocument();
    await waitFor(() => expect(fetch.mock.calls.some(([url]) => new URL(String(url)).pathname === "/usuarios")).toBe(true));
  });
});
