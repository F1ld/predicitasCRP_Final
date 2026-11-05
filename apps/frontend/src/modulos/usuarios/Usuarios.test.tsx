import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../nucleo/api/cliente";
import type { ContextoAuth } from "../../nucleo/auth/contexto";
import { ContextoSesion } from "../../nucleo/auth/contexto";
import { menuPorRol } from "../../nucleo/layout/ranuras";
import menu from "./menu";
import rutas from "./rutas";
import { camposError, errorCorreo, errorNombre, mensajeError, politicaClave } from "./validacion";
import Usuarios from "./Usuarios";
import type { UsuarioOut } from "./tipos";

const administrador: UsuarioOut = {
  id_usuario: 1, nombre_completo: "Administrador sintético", correo_institucional: "admin@predicitas.crp",
  rol: "ADMINISTRADOR", activo: true, creado_en: "2026-10-18T10:00:00-05:00", actualizado_en: null,
};
const recepcion: UsuarioOut = { ...administrador, id_usuario: 2, nombre_completo: "Recepción sintética", correo_institucional: "recepcion@predicitas.crp", rol: "RECEPCION" };
const pagina = (items = [recepcion], total = items.length) => ({ items, total, limite: 50, desplazamiento: 0 });
const respuesta = (datos: unknown, estado = 200): Response => new Response(JSON.stringify(datos), { status: estado, headers: { "Content-Type": "application/json" } });
const fallo = (codigo: string, mensaje: string, campos?: Record<string, string>) => respuesta({ error: { codigo, mensaje, campos } }, codigo === "VALIDACION" ? 422 : 409);
type Servidor = (url: URL, opciones?: RequestInit) => Response | Promise<Response>;
const normal: Servidor = (url) => respuesta(url.pathname === "/usuarios" ? pagina() : recepcion);

function contexto(cambios: Partial<ContextoAuth> = {}): ContextoAuth {
  return { usuario: administrador, cargando: false, mensajeSesion: "", iniciarSesion: vi.fn(), cerrarSesion: vi.fn(), tieneRol: (...roles) => roles.includes(administrador.rol), ...cambios };
}

function Direccion() { const lugar = useLocation(); return <span data-testid="direccion">{lugar.pathname}{lugar.search}</span>; }

function mostrar(servidor: Servidor = normal, opciones: { sesion?: ContextoAuth; url?: string } = {}) {
  const fetchSimulado = vi.fn(async (entrada: RequestInfo | URL, init?: RequestInit) => servidor(new URL(String(entrada)), init));
  vi.stubGlobal("fetch", fetchSimulado);
  const vista = render(<ContextoSesion.Provider value={opciones.sesion ?? contexto()}><MemoryRouter initialEntries={[opciones.url ?? "/usuarios"]}>
    <Routes><Route path="/usuarios" element={<Usuarios />} /><Route path="/" element={<p>Inicio autorizado</p>} /></Routes><Direccion />
  </MemoryRouter></ContextoSesion.Provider>);
  return { ...vista, fetchSimulado };
}

async function esperarLista() { await screen.findByRole("table"); }

async function abrirCrear(persona = userEvent.setup()) {
  await persona.click(screen.getByRole("button", { name: "Crear usuario" }));
  return within(screen.getByRole("dialog", { name: "Crear usuario" }));
}

async function rellenarCrear(persona = userEvent.setup()) {
  const dialogo = await abrirCrear(persona);
  await persona.type(dialogo.getByLabelText("Nombre completo"), "Usuario sintético nuevo");
  await persona.type(dialogo.getByLabelText("Correo institucional"), "NUEVO@PREDICITAS.CRP");
  await persona.type(dialogo.getByLabelText("Contraseña inicial"), "ClaveSegura2026");
  return dialogo;
}

// RF-003 a RF-008, RNF-001, RNF-016; CP-M01-04 a 09: contrato y datos sintéticos.
describe("Usuarios: acceso, consulta y filtros", () => {
  it("registra ruta y menú exclusivamente para ADMINISTRADOR", () => {
    expect(rutas[0]?.ruta).toBe("/usuarios");
    expect(rutas[0]?.roles).toEqual(["ADMINISTRADOR"]);
    expect(menuPorRol({ usuarios: { default: menu } }, "ADMINISTRADOR")[0]?.etiqueta).toBe("Usuarios");
    expect(menuPorRol({ usuarios: { default: menu } }, "RECEPCION")).toEqual([]);
    expect(menuPorRol({ usuarios: { default: menu } }, "TECNICO_IA")).toEqual([]);
  });

  it.each(["RECEPCION", "TECNICO_IA"] as const)("devuelve al inicio al rol %s sin consultar usuarios ni mostrar acciones", (rol) => {
    const { fetchSimulado } = mostrar(normal, { sesion: contexto({ usuario: { ...administrador, rol } }) });
    expect(screen.getByText("Inicio autorizado")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Crear usuario" })).not.toBeInTheDocument();
    expect(fetchSimulado).not.toHaveBeenCalled();
  });

  it("espera la autenticación sin consultar datos y evita acceso sin sesión", () => {
    const { fetchSimulado } = mostrar(normal, { sesion: contexto({ usuario: null, cargando: true }) });
    expect(screen.getByRole("status")).toHaveTextContent("Verificando sesión");
    expect(fetchSimulado).not.toHaveBeenCalled();
  });

  it("redirige si no hay usuario", () => {
    mostrar(normal, { sesion: contexto({ usuario: null }) });
    expect(screen.getByText("Inicio autorizado")).toBeInTheDocument();
  });

  it("presenta carga, datos y acciones accesibles", async () => {
    let resolver: ((valor: Response) => void) | undefined;
    mostrar(() => new Promise<Response>((cumplir) => { resolver = cumplir; }));
    expect(screen.getByRole("status")).toHaveTextContent("Cargando usuarios");
    await act(async () => resolver?.(respuesta(pagina())));
    expect(screen.getByRole("table")).toHaveAccessibleName("Usuarios que cumplen los filtros aplicados");
    expect(screen.getByRole("rowheader")).toHaveTextContent(recepcion.nombre_completo);
    expect(screen.getByRole("button", { name: `Editar a ${recepcion.nombre_completo}` })).toBeEnabled();
    expect(screen.getByText("Activo", { selector: "span" })).toBeInTheDocument();
  });

  it("presenta la lista vacía", async () => {
    mostrar(() => respuesta(pagina([])));
    expect(await screen.findByText("No hay usuarios con esos filtros.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  });

  it("presenta un error y permite reintentar", async () => {
    let falla = true;
    mostrar(() => falla ? respuesta({ error: { codigo: "ERROR_INTERNO", mensaje: "Consulta no disponible." } }, 500) : respuesta(pagina()));
    expect(await screen.findByRole("alert")).toHaveTextContent("Consulta no disponible.");
    falla = false;
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await esperarLista();
  });

  it("detecta una respuesta sin datos", async () => {
    mostrar(() => new Response(null, { status: 204 }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El servidor no devolvió la lista de usuarios.");
  });

  it("envía q, rol, activo y límite exactos; reinicia el desplazamiento y conserva filtros al paginar", async () => {
    const persona = userEvent.setup();
    const { fetchSimulado } = mostrar(() => respuesta(pagina([recepcion], 25)), { url: "/usuarios?desplazamiento=20&limite=10" });
    await esperarLista();
    await persona.type(screen.getByLabelText("Nombre o correo"), "  sintético  ");
    await persona.selectOptions(screen.getByLabelText("Rol"), "RECEPCION");
    await persona.selectOptions(screen.getByLabelText("Estado"), "false");
    await persona.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await esperarLista();
    const filtrada = new URL(String(fetchSimulado.mock.calls.at(-1)?.[0]));
    expect(Object.fromEntries(filtrada.searchParams)).toEqual({ q: "sintético", rol: "RECEPCION", activo: "false", limite: "10", desplazamiento: "0" });
    expect(screen.getByTestId("direccion")).not.toHaveTextContent("desplazamiento=20");
    await persona.click(screen.getByRole("button", { name: "Siguiente" }));
    await esperarLista();
    expect(screen.getByTestId("direccion")).toHaveTextContent("desplazamiento=10");
    expect(screen.getByTestId("direccion")).toHaveTextContent("rol=RECEPCION");
    await persona.click(screen.getByRole("button", { name: "Anterior" }));
    await esperarLista();
    expect(screen.getByTestId("direccion")).toHaveTextContent("desplazamiento=0");
    await persona.click(screen.getByRole("button", { name: "Limpiar" }));
    await esperarLista();
    expect(screen.getByTestId("direccion")).toHaveTextContent(/^\/usuarios$/);
  });

  it("normaliza parámetros de paginación inválidos e ignora filtros que no están en el contrato", async () => {
    const { fetchSimulado } = mostrar(normal, { url: "/usuarios?limite=999&desplazamiento=-1&rol=OTRO&activo=quizas" });
    await esperarLista();
    expect(new URL(String(fetchSimulado.mock.calls[0]?.[0])).search).toBe("?limite=50&desplazamiento=0");
  });
});

describe("Usuarios: crear y editar", () => {
  it("crea con nombres exactos del contrato y correo normalizado sin conservar la clave", async () => {
    const persona = userEvent.setup();
    const { fetchSimulado } = mostrar((url, init) => url.pathname === "/usuarios" && init?.method === "POST" ? respuesta({ ...recepcion, id_usuario: 3 }, 201) : normal(url));
    await esperarLista();
    const dialogo = await rellenarCrear(persona);
    expect(dialogo.getByText("✓ Entre 8 y 128 caracteres")).toBeInTheDocument();
    await persona.click(dialogo.getByRole("button", { name: "Crear usuario" }));
    expect(await screen.findByText("Usuario creado correctamente.")).toBeInTheDocument();
    const envio = fetchSimulado.mock.calls.find(([, opciones]) => opciones?.method === "POST");
    expect(JSON.parse(String(envio?.[1]?.body))).toEqual({ nombre_completo: "Usuario sintético nuevo", correo_institucional: "nuevo@predicitas.crp", rol: "RECEPCION", clave_inicial: "ClaveSegura2026" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(sessionStorage.length).toBe(0);
  });

  it("valida campos y política en vivo; no envía datos inválidos", async () => {
    const persona = userEvent.setup();
    const { fetchSimulado } = mostrar();
    await esperarLista();
    const dialogo = await abrirCrear(persona);
    await persona.click(dialogo.getByRole("button", { name: "Crear usuario" }));
    expect(dialogo.getByLabelText("Nombre completo")).toHaveAttribute("aria-invalid", "true");
    expect(dialogo.getByLabelText("Nombre completo")).toHaveFocus();
    expect(dialogo.getByLabelText("Correo institucional")).toHaveAccessibleDescription("Escribe un correo válido de hasta 100 caracteres.");
    await persona.type(dialogo.getByLabelText("Contraseña inicial"), "sololetras");
    expect(dialogo.getByText("✓ Al menos una letra")).toBeInTheDocument();
    expect(dialogo.getByText("○ Al menos un número")).toBeInTheDocument();
    expect(fetchSimulado.mock.calls.every(([, init]) => init?.method === "GET")).toBe(true);
  });

  it("asocia errores 422 por campo y permite corregirlos", async () => {
    const persona = userEvent.setup();
    mostrar((url, init) => init?.method === "POST" ? fallo("VALIDACION", "Revisa los datos.", { "body.nombre_completo": "Nombre rechazado por el servidor.", correo_institucional: "Correo rechazado.", rol: "Rol inválido.", clave_inicial: "Clave rechazada." }) : normal(url));
    await esperarLista();
    const dialogo = await rellenarCrear(persona);
    await persona.click(dialogo.getByRole("button", { name: "Crear usuario" }));
    expect(await dialogo.findByRole("alert")).toHaveTextContent("Revisa los datos.");
    expect(dialogo.getByLabelText("Nombre completo")).toHaveAccessibleDescription("Nombre rechazado por el servidor.");
    expect(dialogo.getByLabelText("Rol")).toHaveAccessibleDescription("Rol inválido.");
    expect(dialogo.getByLabelText("Correo institucional")).toHaveAttribute("aria-invalid", "true");
    await persona.type(dialogo.getByLabelText("Nombre completo"), " adicional");
    expect(dialogo.queryByText("Nombre rechazado por el servidor.")).not.toBeInTheDocument();
  });

  it("explica CORREO_DUPLICADO sin perder el formulario", async () => {
    const persona = userEvent.setup();
    mostrar((url, init) => init?.method === "POST" ? fallo("CORREO_DUPLICADO", "Duplicado") : normal(url));
    await esperarLista();
    const dialogo = await rellenarCrear(persona);
    await persona.click(dialogo.getByRole("button", { name: "Crear usuario" }));
    expect(await dialogo.findByRole("alert")).toHaveTextContent("Ya existe un usuario con ese correo institucional");
    expect(dialogo.getByLabelText("Nombre completo")).toHaveValue("Usuario sintético nuevo");
  });

  it("edita después de consultar el detalle y solo envía nombre_completo y rol", async () => {
    const persona = userEvent.setup();
    const { fetchSimulado } = mostrar((url, init) => init?.method === "PATCH" ? respuesta({ ...recepcion, nombre_completo: "Nombre actualizado" }) : normal(url));
    await esperarLista();
    await persona.click(screen.getByRole("button", { name: `Editar a ${recepcion.nombre_completo}` }));
    const dialogo = within(screen.getByRole("dialog"));
    await dialogo.findByLabelText("Nombre completo");
    expect(dialogo.getByLabelText("Correo institucional")).toHaveAttribute("readonly");
    expect(dialogo.queryByLabelText("Contraseña inicial")).not.toBeInTheDocument();
    await persona.clear(dialogo.getByLabelText("Nombre completo"));
    await persona.type(dialogo.getByLabelText("Nombre completo"), "Nombre actualizado");
    await persona.selectOptions(dialogo.getByLabelText("Rol"), "TECNICO_IA");
    await persona.click(dialogo.getByRole("button", { name: "Guardar cambios" }));
    expect(await screen.findByText("Usuario actualizado correctamente.")).toBeInTheDocument();
    expect(fetchSimulado.mock.calls.some(([url, init]) => new URL(String(url)).pathname === "/usuarios/2" && init?.method === "GET")).toBe(true);
    const envio = fetchSimulado.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(JSON.parse(String(envio?.[1]?.body))).toEqual({ nombre_completo: "Nombre actualizado", rol: "TECNICO_IA" });
  });

  it.each([
    ["AUTOMODIFICACION_ROL", "No puedes cambiar tu propio rol."],
    ["ULTIMO_ADMINISTRADOR", "Debe quedar al menos un administrador activo."],
  ])("explica %s al editar", async (codigo, mensaje) => {
    const persona = userEvent.setup();
    mostrar((url, init) => init?.method === "PATCH" ? fallo(codigo, "Conflicto") : normal(url));
    await esperarLista();
    await persona.click(screen.getByRole("button", { name: `Editar a ${recepcion.nombre_completo}` }));
    await screen.findByLabelText("Nombre completo");
    await persona.click(screen.getByRole("button", { name: "Guardar cambios" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(mensaje);
  });

  it("muestra error de detalle y reintenta antes de editar", async () => {
    const persona = userEvent.setup();
    let fallaDetalle = true;
    mostrar((url) => url.pathname !== "/usuarios" && fallaDetalle ? respuesta({ error: { codigo: "NO_ENCONTRADO", mensaje: "Usuario no disponible." } }, 404) : normal(url));
    await esperarLista();
    await persona.click(screen.getByRole("button", { name: `Editar a ${recepcion.nombre_completo}` }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Usuario no disponible.");
    fallaDetalle = false;
    await persona.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByLabelText("Nombre completo")).toHaveValue(recepcion.nombre_completo);
  });

  it("evita envíos duplicados y cancela la respuesta al cerrar durante el envío", async () => {
    const persona = userEvent.setup();
    let resolver: ((valor: Response) => void) | undefined;
    const { fetchSimulado } = mostrar((url, init) => init?.method === "POST" ? new Promise<Response>((cumplir) => { resolver = cumplir; }) : normal(url));
    await esperarLista();
    const dialogo = await rellenarCrear(persona);
    const formulario = dialogo.getByLabelText("Nombre completo").closest("form");
    if (!formulario) throw new Error("Falta formulario");
    fireEvent.submit(formulario); fireEvent.submit(formulario);
    expect(dialogo.getByRole("button", { name: "Guardando…" })).toBeDisabled();
    expect(fetchSimulado.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
    await persona.click(dialogo.getByRole("button", { name: "Cerrar diálogo" }));
    const envio = fetchSimulado.mock.calls.find(([, init]) => init?.method === "POST");
    expect(envio?.[1]?.signal?.aborted).toBe(true);
    await act(async () => resolver?.(respuesta(recepcion, 201)));
    expect(screen.queryByText("Usuario creado correctamente.")).not.toBeInTheDocument();
  });

  it("detecta una confirmación de guardado sin datos", async () => {
    const persona = userEvent.setup();
    mostrar((url, init) => init?.method === "POST" ? new Response(null, { status: 204 }) : normal(url));
    await esperarLista();
    const dialogo = await rellenarCrear(persona);
    await persona.click(dialogo.getByRole("button", { name: "Crear usuario" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El servidor no confirmó los datos del usuario.");
  });
});

describe("Usuarios: estados y restablecimiento", () => {
  it.each([true, false])("confirma y cambia estado activo=%s sin eliminar al usuario", async (activo) => {
    const persona = userEvent.setup();
    const usuario = { ...recepcion, activo };
    const { fetchSimulado } = mostrar((_url, init) => init?.method === "POST" ? respuesta({ ...usuario, activo: !activo }) : respuesta(pagina([usuario])));
    await esperarLista();
    const accion = activo ? "Desactivar" : "Activar";
    await persona.click(screen.getByRole("button", { name: `${accion} a ${usuario.nombre_completo}` }));
    expect(fetchSimulado.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
    await persona.click(screen.getByRole("button", { name: `${accion} usuario` }));
    expect(await screen.findByText(activo ? "Usuario desactivado correctamente." : "Usuario activado correctamente.")).toBeInTheDocument();
    const envio = fetchSimulado.mock.calls.find(([, init]) => init?.method === "POST");
    expect(new URL(String(envio?.[0])).pathname).toBe("/usuarios/2/estado");
    expect(JSON.parse(String(envio?.[1]?.body))).toEqual({ activo: !activo });
  });

  it.each([
    ["AUTODESACTIVACION", "No puedes desactivar tu propia cuenta."],
    ["ULTIMO_ADMINISTRADOR", "Debe quedar al menos un administrador activo."],
  ])("explica %s al desactivar y permite cancelar", async (codigo, texto) => {
    const persona = userEvent.setup();
    mostrar((url, init) => init?.method === "POST" ? fallo(codigo, "Conflicto") : normal(url));
    await esperarLista();
    await persona.click(screen.getByRole("button", { name: `Desactivar a ${recepcion.nombre_completo}` }));
    await persona.click(screen.getByRole("button", { name: "Desactivar usuario" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(texto);
    await persona.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("genera la clave una vez, permite copiar y la descarta al cerrar y reabrir", async () => {
    const persona = userEvent.setup();
    const copiar = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    const clave = "ClaveTmp2026X";
    const { fetchSimulado } = mostrar((url, init) => init?.method === "POST" ? respuesta({ id_usuario: 2, clave_temporal: clave }) : normal(url));
    await esperarLista();
    const activador = screen.getByRole("button", { name: `Restablecer acceso de ${recepcion.nombre_completo}` });
    await persona.click(activador);
    expect(fetchSimulado.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
    await persona.click(screen.getByRole("button", { name: "Generar contraseña temporal" }));
    expect(await screen.findByLabelText("Contraseña temporal")).toHaveTextContent(clave);
    expect(screen.getByRole("button", { name: "Copiar contraseña" })).toHaveFocus();
    expect(screen.getByText(/Al cerrar no se volverá a ver/)).toBeInTheDocument();
    await persona.click(screen.getByRole("button", { name: "Copiar contraseña" }));
    expect(copiar).toHaveBeenCalledWith(clave);
    expect(await screen.findByText("Contraseña temporal copiada.")).toBeInTheDocument();
    expect(fetchSimulado.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
    expect(sessionStorage.length).toBe(0);
    await persona.click(screen.getByRole("button", { name: "Cerrar y descartar" }));
    expect(screen.queryByText(clave)).not.toBeInTheDocument();
    expect(activador).toHaveFocus();
    await persona.click(activador);
    expect(screen.queryByLabelText("Contraseña temporal")).not.toBeInTheDocument();
    expect(fetchSimulado.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
    await persona.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("permite copiar manualmente si el portapapeles falla", async () => {
    const persona = userEvent.setup();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("Bloqueado"));
    mostrar((url, init) => init?.method === "POST" ? respuesta({ id_usuario: 2, clave_temporal: "Temporal12345" }) : normal(url));
    await esperarLista();
    await persona.click(screen.getByRole("button", { name: `Restablecer acceso de ${recepcion.nombre_completo}` }));
    await persona.click(screen.getByRole("button", { name: "Generar contraseña temporal" }));
    await screen.findByLabelText("Contraseña temporal");
    await persona.click(screen.getByRole("button", { name: "Copiar contraseña" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("cópiala manualmente");
  });

  it("muestra errores de restablecimiento y limpia todo al salir de la vista", async () => {
    const persona = userEvent.setup();
    let disponible = false;
    const { unmount } = mostrar((url, init) => init?.method === "POST" ? disponible ? respuesta({ id_usuario: 2, clave_temporal: "Efimera12345X" }) : respuesta({ error: { codigo: "NO_ENCONTRADO", mensaje: "El usuario no existe." } }, 404) : normal(url));
    await esperarLista();
    await persona.click(screen.getByRole("button", { name: `Restablecer acceso de ${recepcion.nombre_completo}` }));
    await persona.click(screen.getByRole("button", { name: "Generar contraseña temporal" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El usuario no existe.");
    disponible = true;
    await persona.click(screen.getByRole("button", { name: "Generar contraseña temporal" }));
    await screen.findByLabelText("Contraseña temporal");
    unmount();
    expect(screen.queryByText("Efimera12345X")).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
  });
});

describe("Usuarios: teclado y validadores", () => {
  it("atrapa Tab y Mayús+Tab, restaura el foco y cierra con Escape", async () => {
    const persona = userEvent.setup();
    mostrar();
    await esperarLista();
    const activador = screen.getByRole("button", { name: "Crear usuario" });
    const dialogo = await abrirCrear(persona);
    expect(dialogo.getByRole("button", { name: "Cerrar diálogo" })).toHaveFocus();
    await persona.tab({ shift: true });
    expect(dialogo.getByRole("button", { name: "Crear usuario" })).toHaveFocus();
    await persona.tab();
    expect(dialogo.getByRole("button", { name: "Cerrar diálogo" })).toHaveFocus();
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    await persona.keyboard("{Escape}");
    expect(activador).toHaveFocus();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
    expect(activador.closest("[aria-hidden]" )).toBeNull();
  });

  it("conserva los límites del contrato y mensajes de errores conocidos o desconocidos", () => {
    expect(errorNombre("A")).not.toBe("");
    expect(errorNombre(" Nombre")).not.toBe("");
    expect(errorNombre("A".repeat(121))).not.toBe("");
    expect(errorNombre("Usuario válido")).toBe("");
    expect(errorCorreo("incorrecto")).not.toBe("");
    expect(errorCorreo(`${"a".repeat(101)}@predicitas.crp`)).not.toBe("");
    expect(errorCorreo("test@predicitas.crp")).toBe("");
    expect(Object.values(politicaClave("Áéíóú123")).every(Boolean)).toBe(true);
    expect(politicaClave("a1".repeat(65)).longitud).toBe(false);
    expect(mensajeError(new ApiError(403, "SIN_PERMISO", "Sin permiso."))).toBe("Sin permiso.");
    expect(mensajeError(new Error("Fallo legible"))).toBe("Fallo legible");
    expect(mensajeError(null)).toBe("No se pudo completar la solicitud.");
    expect(camposError(null)).toEqual({});
  });

  it("permite cancelar la creación sin enviar datos", async () => {
    mostrar();
    await esperarLista();
    const dialogo = await abrirCrear();
    await userEvent.click(dialogo.getByRole("button", { name: "Cancelar" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
