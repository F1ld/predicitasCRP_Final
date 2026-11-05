import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { token } from "../../nucleo/api/cliente";
import type { Usuario } from "../../nucleo/api/tipos";
import { iniciarGestorSesion } from "../../nucleo/sesion/controlador";
import MiCuenta from "./MiCuenta";
import { errorClave } from "./politicaClave";
import menu from "./menu";
import rutas from "./rutas";

const usuario: Usuario = { id_usuario: 1, nombre_completo: "Cuenta sintética", correo_institucional: "recepcion@predicitas.crp", rol: "RECEPCION", activo: true, creado_en: "2026-10-18T09:00:00-05:00", actualizado_en: null };
const fetchSimulado = vi.fn<typeof fetch>();
const respuesta = (datos: unknown, status = 200) => new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } });

beforeEach(() => {
  fetchSimulado.mockReset();
  vi.stubGlobal("fetch", fetchSimulado);
  token.guardar("credencial-sintetica-anterior");
});

async function completar(nueva = "NuevaClave123", confirmacion = nueva, actual = "Anterior123") {
  const persona = userEvent.setup();
  await persona.type(screen.getByLabelText("Contraseña actual"), actual);
  await persona.type(screen.getByLabelText("Nueva contraseña"), nueva);
  await persona.type(screen.getByLabelText("Confirmar nueva contraseña"), confirmacion);
  return persona;
}

// M01-V05, CP-M01-10, RF-008, RNF-002/RNF-004: datos y claves solo sintéticos.
describe("Mi cuenta y cambio de contraseña", () => {
  it("declara ruta y menú para los tres roles del contrato", () => {
    const roles = ["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"];
    expect(rutas.find((ruta) => ruta.ruta === "/mi-cuenta")?.roles).toEqual(roles);
    expect(menu.find((entrada) => entrada.ruta === "/mi-cuenta")?.roles).toEqual(roles);
  });

  it("muestra la espera mientras obtiene la cuenta", () => {
    fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined));
    render(<MiCuenta />);
    expect(screen.getByRole("status")).toHaveTextContent("Cargando mi cuenta…");
  });

  it("muestra datos propios y campos etiquetados", async () => {
    fetchSimulado.mockResolvedValue(respuesta(usuario));
    render(<MiCuenta />);
    expect(await screen.findByText(usuario.nombre_completo)).toBeInTheDocument();
    expect(screen.getByText(usuario.correo_institucional)).toBeInTheDocument();
    expect(screen.getByText("Recepción")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña actual")).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByLabelText("Nueva contraseña")).toHaveAttribute("autocomplete", "new-password");
    expect(screen.getByRole("button", { name: "Cambiar contraseña" })).toBeDisabled();
  });

  it("explica una respuesta sin datos", async () => {
    fetchSimulado.mockResolvedValue(new Response(null, { status: 204 }));
    render(<MiCuenta />);
    expect(await screen.findByText("No se recibieron los datos de tu cuenta.")).toBeInTheDocument();
  });

  it("muestra el error y permite reintentar", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo: "ERROR_INTERNO", mensaje: "No se pudo consultar la cuenta." } }, 500)).mockResolvedValueOnce(respuesta(usuario));
    render(<MiCuenta />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo consultar la cuenta.");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText(usuario.nombre_completo)).toBeInTheDocument();
  });

  it("valida en vivo longitud, letra, número, diferencia y confirmación sin enviar", async () => {
    fetchSimulado.mockResolvedValue(respuesta(usuario));
    render(<MiCuenta />);
    await screen.findByText(usuario.nombre_completo);
    const persona = await completar("corta", "distinta");
    expect(screen.getByText("Usa entre 8 y 128 caracteres.")).toBeInTheDocument();
    expect(screen.getByText("Las contraseñas nuevas deben coincidir.")).toBeInTheDocument();
    await persona.clear(screen.getByLabelText("Nueva contraseña"));
    await persona.type(screen.getByLabelText("Nueva contraseña"), "sinNumeros");
    expect(screen.getByText("Incluye al menos una letra y un número.")).toBeInTheDocument();
    await persona.clear(screen.getByLabelText("Nueva contraseña"));
    await persona.type(screen.getByLabelText("Nueva contraseña"), "Anterior123");
    expect(screen.getByText("La nueva contraseña debe ser distinta de la actual.")).toBeInTheDocument();
    expect(fetchSimulado.mock.calls).toHaveLength(1);
    expect(errorClave("12345678")).toBeTruthy();
    expect(errorClave("a1" + "a".repeat(127))).toBeTruthy();
    expect(errorClave("Árbol123")).toBe("");
  });

  it("envía solo campos del contrato, guarda el token nuevo y limpia las claves", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(usuario)).mockResolvedValueOnce(respuesta({ access_token: "credencial-sintetica-nueva", token_type: "bearer", expires_in: 1800 })).mockResolvedValueOnce(respuesta({ ...usuario, actualizado_en: "2026-10-18T10:00:00-05:00" }));
    render(<MiCuenta />);
    await screen.findByText(usuario.nombre_completo);
    const persona = await completar();
    await persona.click(screen.getByRole("button", { name: "Cambiar contraseña" }));
    expect(await screen.findByText("Contraseña actualizada.")).toBeInTheDocument();
    expect(token.leer()).toBe("credencial-sintetica-nueva");
    const [url, opciones] = fetchSimulado.mock.calls[1];
    expect(new URL(String(url)).pathname).toBe("/auth/cambiar-clave");
    expect(opciones?.method).toBe("POST");
    expect(JSON.parse(String(opciones?.body))).toEqual({ clave_actual: "Anterior123", clave_nueva: "NuevaClave123" });
    await waitFor(() => expect(screen.getByLabelText("Contraseña actual")).toHaveValue(""));
    expect(screen.getByLabelText("Nueva contraseña")).toHaveValue("");
    expect(screen.getByLabelText("Confirmar nueva contraseña")).toHaveValue("");
    expect(opciones?.headers).toMatchObject({ Authorization: "Bearer credencial-sintetica-anterior" });
  });

  it.each([
    [409, "CLAVE_ACTUAL_INCORRECTA", "La contraseña actual no es correcta."],
    [500, "ERROR_INTERNO", "No se pudo cambiar la clave."],
  ])("presenta el error %s sin cambiar la credencial", async (status, codigo, mensaje) => {
    fetchSimulado.mockResolvedValueOnce(respuesta(usuario)).mockResolvedValueOnce(respuesta({ error: { codigo, mensaje: "No se pudo cambiar la clave." } }, status));
    render(<MiCuenta />);
    await screen.findByText(usuario.nombre_completo);
    const persona = await completar();
    await persona.click(screen.getByRole("button", { name: "Cambiar contraseña" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(mensaje);
    expect(token.leer()).toBe("credencial-sintetica-anterior");
  });

  it("vincula los errores 422 con el campo del contrato", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(usuario)).mockResolvedValueOnce(respuesta({ error: { codigo: "VALIDACION", mensaje: "Revisa los campos.", campos: { clave_nueva: "La clave no cumple la política del servidor." } } }, 422));
    render(<MiCuenta />);
    await screen.findByText(usuario.nombre_completo);
    const persona = await completar();
    await persona.click(screen.getByRole("button", { name: "Cambiar contraseña" }));
    expect(await screen.findByText("La clave no cumple la política del servidor.")).toBeInTheDocument();
    expect(screen.getByLabelText("Nueva contraseña")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Nueva contraseña")).toHaveAccessibleDescription("La clave no cumple la política del servidor.");
  });

  it("RF-008, RNF-004: conserva el token del cambio de clave si una renovación termina durante el POST", async () => {
    const ahora = Date.now();
    const jwt = (emitido: number) => `cabecera.${btoa(JSON.stringify({ sub: "1", iat: emitido / 1000, exp: emitido / 1000 + 1800 }))}.firma`;
    const anterior = jwt(ahora - 26 * 60_000);
    const deRenovacion = jwt(ahora);
    const deCambioClave = jwt(ahora + 1);
    const tokenOut = (access_token: string) => ({ access_token, token_type: "bearer", expires_in: 1800 });
    let resolverRenovacion: ((respuesta: Response) => void) | undefined;
    let resolverCambio: ((respuesta: Response) => void) | undefined;
    fetchSimulado.mockImplementation((url) => {
      const ruta = new URL(String(url)).pathname;
      if (ruta === "/auth/renovar") return new Promise((completar) => { resolverRenovacion = completar; });
      if (ruta === "/auth/cambiar-clave") return new Promise((completar) => { resolverCambio = completar; });
      return Promise.resolve(respuesta(usuario));
    });
    vi.stubGlobal("BroadcastChannel", undefined);
    token.guardar(anterior);
    const limpiar = iniciarGestorSesion(1, vi.fn());
    try {
      render(<MiCuenta />);
      await screen.findByText(usuario.nombre_completo);
      const persona = await completar();
      expect(resolverRenovacion).toBeDefined();
      await persona.click(screen.getByRole("button", { name: "Cambiar contraseña" }));
      const peticionRenovacion = fetchSimulado.mock.calls.find(([url]) => new URL(String(url)).pathname === "/auth/renovar");
      expect(peticionRenovacion?.[1]?.signal?.aborted).toBe(true);
      await act(async () => { resolverRenovacion?.(respuesta(tokenOut(deRenovacion))); });
      expect(token.leer()).toBe(anterior);
      await act(async () => { resolverCambio?.(respuesta(tokenOut(deCambioClave))); });
      expect(await screen.findByText("Contraseña actualizada.")).toBeInTheDocument();
      expect(token.leer()).toBe(deCambioClave);
    } finally { limpiar(); }
  });

  it.each(["cerrada", "reemplazada"])("bloquea envíos duplicados y descarta la respuesta de una sesión %s", async (estado) => {
    let resolver: ((respuesta: Response) => void) | undefined;
    fetchSimulado.mockResolvedValueOnce(respuesta(usuario)).mockImplementationOnce(() => new Promise<Response>((completarPeticion) => { resolver = completarPeticion; }));
    render(<MiCuenta />);
    await screen.findByText(usuario.nombre_completo);
    const persona = await completar();
    await persona.click(screen.getByRole("button", { name: "Cambiar contraseña" }));
    const formulario = screen.getByLabelText("Contraseña actual").closest("form");
    if (!formulario) throw new Error("Falta el formulario");
    fireEvent.submit(formulario);
    expect(fetchSimulado).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("button", { name: "Guardando…" })).toBeDisabled();
    if (estado === "cerrada") token.borrar();
    else token.guardar("otra-sesion-sintetica");
    await act(async () => { resolver?.(respuesta({ access_token: "respuesta-antigua", token_type: "bearer", expires_in: 1800 })); });
    expect(token.leer()).toBe(estado === "cerrada" ? null : "otra-sesion-sintetica");
    expect(screen.queryByText("Contraseña actualizada.")).not.toBeInTheDocument();
  });
});
