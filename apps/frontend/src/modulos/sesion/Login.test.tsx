import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../nucleo/api/cliente";
import type { Usuario } from "../../nucleo/api/tipos";
import { ContextoSesion } from "../../nucleo/auth/contexto";
import type { ContextoAuth } from "../../nucleo/auth/contexto";
import Login from "./Login";
import rutas from "./rutas";
import * as motivos from "../../nucleo/sesion";

function sesion(cambios: Partial<ContextoAuth> = {}): ContextoAuth {
  return {
    usuario: null, cargando: false, mensajeSesion: "", iniciarSesion: vi.fn(), cerrarSesion: vi.fn(),
    tieneRol: vi.fn(() => false), ...cambios,
  };
}

function mostrar(contexto: ContextoAuth = sesion()) {
  return render(<ContextoSesion.Provider value={contexto}><MemoryRouter initialEntries={["/login"]}>
    <Routes><Route path="/login" element={<Login />} /><Route path="/citas" element={<p>Bandeja de citas</p>} /></Routes>
  </MemoryRouter></ContextoSesion.Provider>);
}

async function completarFormulario() {
  const persona = userEvent.setup();
  await persona.type(screen.getByLabelText("Correo institucional"), "recepcion@predicitas.crp");
  await persona.type(screen.getByLabelText("Contraseña"), "Clave123");
  await persona.click(screen.getByRole("button", { name: "Ingresar" }));
}

// RF-001, RNF-016: credenciales sintéticas y todos los estados del acceso migrado M01-V01.
describe("Login", () => {
  it("muestra el motivo exacto de inactividad y lo limpia al volver a ingresar (RNF-004, CP-M01-11)", async () => {
    vi.spyOn(motivos, "leerMotivoSesion").mockReturnValue("Tu sesión expiró por inactividad");
    const limpiar = vi.spyOn(motivos, "limpiarMotivoSesion");
    mostrar(sesion({ mensajeSesion: "Tu sesión expiró. Inicia sesión nuevamente." }));
    expect(screen.getByRole("status")).toHaveTextContent("Tu sesión expiró por inactividad");
    await completarFormulario();
    expect(limpiar).toHaveBeenCalledOnce();
  });
  it("conserva los campos accesibles, la marca y la ranura pública de acceso", () => {
    mostrar();
    expect(screen.getByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
    expect(screen.getByLabelText("Correo institucional")).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("Contraseña")).toHaveAttribute("type", "password");
    expect(screen.getByRole("img", { name: "PrediCitas CRP" })).toBeInTheDocument();
    expect(rutas[0]?.ruta).toBe("/login");
    expect(rutas[0]?.roles).toEqual(["publico"]);
  });

  it("muestra la espera de restauración y no pide credenciales antes de terminar", () => {
    mostrar(sesion({ cargando: true }));
    expect(screen.getByRole("status")).toHaveTextContent("Verificando sesión…");
    expect(screen.queryByLabelText("Correo institucional")).not.toBeInTheDocument();
  });

  it("redirige a citas si ya hay un usuario autenticado", () => {
    const usuario: Usuario = {
      id_usuario: 1, nombre_completo: "Usuario sintético", correo_institucional: "recepcion@predicitas.crp",
      rol: "RECEPCION", activo: true, creado_en: "2026-10-18T10:00:00-05:00", actualizado_en: null,
    };
    mostrar(sesion({ usuario }));
    expect(screen.getByText("Bandeja de citas")).toBeInTheDocument();
  });

  it("presenta el aviso de sesión expirada con un estado accesible", () => {
    mostrar(sesion({ mensajeSesion: "Tu sesión expiró. Inicia sesión nuevamente." }));
    expect(screen.getByRole("status")).toHaveTextContent("Tu sesión expiró. Inicia sesión nuevamente.");
  });

  it("envía las credenciales y bloquea el formulario mientras espera", async () => {
    let terminar: (() => void) | undefined;
    const iniciarSesion = vi.fn(() => new Promise<void>((resolver) => { terminar = resolver; }));
    mostrar(sesion({ iniciarSesion }));
    await completarFormulario();
    expect(iniciarSesion).toHaveBeenCalledWith("recepcion@predicitas.crp", "Clave123");
    expect(screen.getByRole("button", { name: "Ingresando…" })).toBeDisabled();
    expect(screen.getByLabelText("Correo institucional")).toBeDisabled();
    const formulario = screen.getByLabelText("Correo institucional").closest("form");
    if (!formulario) throw new Error("Falta el formulario de acceso");
    fireEvent.submit(formulario);
    expect(iniciarSesion).toHaveBeenCalledTimes(1);
    await act(async () => { terminar?.(); });
    expect(screen.getByRole("button", { name: "Ingresar" })).toBeEnabled();
  });

  it("muestra el mensaje actual de credenciales incorrectas ante 401", async () => {
    mostrar(sesion({ iniciarSesion: vi.fn().mockRejectedValue(new ApiError(401, "NO_AUTENTICADO", "Credenciales inválidas")) }));
    await completarFormulario();
    expect(await screen.findByRole("alert")).toHaveTextContent("Correo o contraseña incorrectos.");
    expect(screen.getByRole("button", { name: "Ingresar" })).toBeEnabled();
  });

  it("presenta el bloqueo 429 exactamente con la duración informada por la API", async () => {
    const mensaje = "Demasiados intentos fallidos. Vuelve a intentarlo en 15 minutos.";
    mostrar(sesion({ iniciarSesion: vi.fn().mockRejectedValue(new ApiError(429, "DEMASIADOS_INTENTOS", mensaje)) }));
    await completarFormulario();
    expect(await screen.findByRole("alert")).toHaveTextContent(mensaje);
  });

  it("presenta los errores de conexión de forma legible", async () => {
    mostrar(sesion({ iniciarSesion: vi.fn().mockRejectedValue(new Error("No se pudo conectar con el servidor.")) }));
    await completarFormulario();
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar con el servidor.");
  });

  it("usa un mensaje general para un rechazo que no contiene un Error", async () => {
    mostrar(sesion({ iniciarSesion: vi.fn().mockRejectedValue(null) }));
    await completarFormulario();
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo completar la solicitud.");
  });
});
