import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { Rol, Usuario } from "../api/tipos";
import { ContextoSesion } from "./contexto";
import type { ContextoAuth } from "./contexto";
import RutaProtegida from "./RutaProtegida";

const usuario: Usuario = {
  id_usuario: 2, nombre_completo: "Usuario sintético", correo_institucional: "tecnico.ia@predicitas.crp",
  rol: "TECNICO_IA", activo: true, creado_en: "2026-10-18T10:00:00-05:00", actualizado_en: null,
};

function sesion(cambios: Partial<ContextoAuth> = {}): ContextoAuth {
  return {
    usuario, cargando: false, mensajeSesion: "", iniciarSesion: vi.fn(), cerrarSesion: vi.fn(),
    tieneRol: (...roles: Rol[]) => roles.includes(usuario.rol), ...cambios,
  };
}

function mostrar(contexto: ContextoAuth, roles?: Rol[]) {
  return render(<ContextoSesion.Provider value={contexto}>
    <MemoryRouter initialEntries={["/privada"]}><Routes>
      <Route path="/login" element={<p>Formulario de acceso</p>} />
      <Route element={<RutaProtegida roles={roles} />}>
        <Route path="/privada" element={<p>Contenido autorizado</p>} />
      </Route>
    </Routes></MemoryRouter>
  </ContextoSesion.Provider>);
}

// RF-003, RNF-001: la interfaz evita mostrar una operación sin sesión o sin rol.
describe("RutaProtegida", () => {
  it("espera a que se verifique la sesión", () => {
    mostrar(sesion({ cargando: true }));
    expect(screen.getByRole("status")).toHaveTextContent("Verificando sesión…");
    expect(screen.queryByText("Contenido autorizado")).not.toBeInTheDocument();
  });

  it("redirige al acceso cuando no hay usuario", () => {
    mostrar(sesion({ usuario: null }));
    expect(screen.getByText("Formulario de acceso")).toBeInTheDocument();
  });

  it("muestra la denegación y el enlace a citas cuando falta el rol", () => {
    mostrar(sesion(), ["ADMINISTRADOR", "RECEPCION"]);
    expect(screen.getByRole("heading", { name: "No tienes permiso para esta sección" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver a citas" })).toHaveAttribute("href", "/citas");
    expect(screen.queryByText("Contenido autorizado")).not.toBeInTheDocument();
  });

  it("permite el rol correcto mediante Outlet", () => {
    mostrar(sesion(), ["TECNICO_IA"]);
    expect(screen.getByText("Contenido autorizado")).toBeInTheDocument();
  });

  it("permite las rutas autenticadas sin una restricción adicional de rol", () => {
    mostrar(sesion());
    expect(screen.getByText("Contenido autorizado")).toBeInTheDocument();
  });

  it("acepta el elemento de una ranura como hijo protegido", () => {
    render(<ContextoSesion.Provider value={sesion()}><MemoryRouter>
      <RutaProtegida roles={["TECNICO_IA"]}><p>Elemento de ranura</p></RutaProtegida>
    </MemoryRouter></ContextoSesion.Provider>);
    expect(screen.getByText("Elemento de ranura")).toBeInTheDocument();
  });
});
