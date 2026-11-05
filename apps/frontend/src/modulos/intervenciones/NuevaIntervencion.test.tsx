import { useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ContextoAuth } from "../../nucleo/auth/contexto";
import { ContextoSesion } from "../../nucleo/auth/contexto";
import NuevaIntervencion from "./NuevaIntervencion";
import type { IntervencionOut, PlantillaOut } from "./tipos";

const usuario = { id_usuario: 1, nombre_completo: "Recepción sintética", correo_institucional: "recepcion@predicitas.crp", rol: "RECEPCION" as const, activo: true, creado_en: "2026-10-18T09:00:00-05:00", actualizado_en: null };
const sesion: ContextoAuth = { usuario, cargando: false, mensajeSesion: "", iniciarSesion: vi.fn(), cerrarSesion: vi.fn(), tieneRol: (...roles) => roles.includes(usuario.rol) };
const plantillas: PlantillaOut[] = [
  { id: "RECORDATORIO_WHATSAPP", canal_contacto: "WHATSAPP", descripcion: "Recordatorio sintético WhatsApp", contenido: "[PENDIENTE: contenido aprobado]" },
  { id: "RECORDATORIO_SMS", canal_contacto: "SMS", descripcion: "Recordatorio sintético SMS", contenido: "Contenido sintético de SMS recibido de la API." },
];
const intervencion: IntervencionOut = { id_intervencion: 5, id_cita: 10, id_cita_externa: "CITA-SINT-10", id_operador: 1, canal_contacto: "WHATSAPP", plantilla_mensaje: plantillas[0].id, consentimiento_optout: false, estado_intervencion: "PENDIENTE", respuesta_paciente: null, fecha_hora_envio: "2026-10-18T09:00:00-05:00", fecha_hora_respuesta: null, acciones_disponibles: ["REGISTRAR_ENVIO", "REGISTRAR_FALLO"] };
const respuesta = (datos: unknown, estado = 200) => new Response(JSON.stringify(datos), { status: estado, headers: { "Content-Type": "application/json" } });
type Servidor = (url: URL, init?: RequestInit) => Response | Promise<Response>;
const normal: Servidor = (_url, init) => respuesta(init?.method === "POST" ? intervencion : plantillas, init?.method === "POST" ? 201 : 200);
const consentimiento = "El paciente cuenta con consentimiento para recibir comunicaciones";

function mostrar(servidor: Servidor = normal) {
  const completado = vi.fn();
  const cerrar = vi.fn();
  const fetchSimulado = vi.fn(async (entrada: RequestInfo | URL, init?: RequestInit) => servidor(new URL(String(entrada)), init));
  vi.stubGlobal("fetch", fetchSimulado);
  function Banco() {
    const [abierto, abrir] = useState(true);
    return <><button type="button" onClick={() => abrir(true)}>Abrir intervención</button>{abierto && <NuevaIntervencion idCita={10} referenciaCita="CITA-SINT-10" cerrar={() => { cerrar(); abrir(false); }} completado={completado} />}</>;
  }
  const vista = render(<ContextoSesion.Provider value={sesion}><MemoryRouter><Banco /></MemoryRouter></ContextoSesion.Provider>);
  return { ...vista, fetchSimulado, completado, cerrar };
}

async function formularioListo() {
  await screen.findByLabelText("Plantilla");
  await waitFor(() => expect(screen.getByLabelText("Plantilla")).not.toBeDisabled());
  return within(screen.getByRole("dialog"));
}

// RF-058, RF-063, RF-065, RF-066, RN07, RN13; CP-M05-01, 05, 06, 08.
// Solo seudónimos y contenido devuelto por la API: nunca se inventa una plantilla clínica.
describe("M05-V02: nueva intervención y consentimiento", () => {
  it("muestra carga y el catálogo recibido, incluido su contenido pendiente literal", async () => {
    let resolver: ((valor: Response) => void) | undefined;
    mostrar(() => new Promise<Response>((cumplir) => { resolver = cumplir; }));
    expect(screen.getByRole("status")).toHaveTextContent(/Cargando/i);
    await act(async () => resolver?.(respuesta(plantillas)));
    await formularioListo();
    expect(screen.getByText("[PENDIENTE: contenido aprobado]")).toBeInTheDocument();
    expect(screen.getByLabelText(consentimiento)).not.toBeChecked();
    expect(screen.getByLabelText("Plantilla")).toHaveValue(plantillas[0].id);
  });

  it("filtra plantillas por el canal y muestra solamente el contenido de la selección", async () => {
    const persona = userEvent.setup();
    mostrar(); await formularioListo();
    await persona.selectOptions(screen.getByLabelText("Canal"), "SMS");
    expect(screen.getByLabelText("Plantilla")).toHaveValue(plantillas[1].id);
    expect(screen.queryByRole("option", { name: plantillas[0].descripcion })).not.toBeInTheDocument();
    expect(screen.getByText(plantillas[1].contenido)).toBeInTheDocument();
    expect(screen.queryByText(plantillas[0].contenido)).not.toBeInTheDocument();
  });

  it("impide el POST sin consentimiento y crea con nombres exactos y true literal", async () => {
    const persona = userEvent.setup();
    const { fetchSimulado, completado } = mostrar();
    await formularioListo();
    const formulario = screen.getByLabelText(consentimiento).closest("form");
    if (!formulario) throw new Error("Falta el formulario de intervención.");
    fireEvent.submit(formulario);
    expect(await screen.findByRole("alert")).toHaveTextContent(/consentimiento/i);
    expect(fetchSimulado.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
    await persona.click(screen.getByLabelText(consentimiento));
    await persona.click(screen.getByRole("button", { name: "Crear intervención" }));
    await waitFor(() => expect(completado).toHaveBeenCalledWith(intervencion));
    const envio = fetchSimulado.mock.calls.find(([, init]) => init?.method === "POST");
    expect(new URL(String(envio?.[0])).pathname).toBe("/intervenciones");
    expect(JSON.parse(String(envio?.[1]?.body))).toEqual({ id_cita: 10, canal_contacto: "WHATSAPP", plantilla_mensaje: plantillas[0].id, consentimiento_confirmado: true });
  });

  it.each([
    [409, "MODO_SOMBRA", /modo sombra/i],
    [409, "OPTOUT_VIGENTE", /Ninguna de sus citas admite nuevas intervenciones/],
    [409, "LIMITE_INTERVENCION", /un único reintento/],
    [409, "NO_ELEGIBLE", /futura.*estado no final.*riesgo alto o medio/],
    [422, "CONSENTIMIENTO_REQUERIDO", /consentimiento/],
    [403, "SIN_PERMISO", /Permiso denegado por la API/],
    [404, "NO_ENCONTRADO", /Cita no encontrada por la API/],
  ])("explica HTTP %s %s y conserva la selección", async (estado, codigo, texto) => {
    const persona = userEvent.setup();
    mostrar((url, init) => init?.method === "POST" ? respuesta({ error: { codigo, mensaje: codigo === "SIN_PERMISO" ? "Permiso denegado por la API" : codigo === "NO_ENCONTRADO" ? "Cita no encontrada por la API" : "Conflicto de negocio" } }, estado) : normal(url, init));
    await formularioListo();
    await persona.click(screen.getByLabelText(consentimiento));
    await persona.click(screen.getByRole("button", { name: "Crear intervención" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(texto);
    expect(screen.getByLabelText("Plantilla")).toHaveValue(plantillas[0].id);
    expect(screen.getByLabelText(consentimiento)).toBeChecked();
  });

  it("presenta los errores VALIDACION por campo sin perder el consentimiento", async () => {
    const persona = userEvent.setup();
    mostrar((url, init) => init?.method === "POST" ? respuesta({ error: { codigo: "VALIDACION", mensaje: "Revisa la plantilla y el canal.", campos: { "body.plantilla_mensaje": "Plantilla fuera del catálogo.", canal_contacto: "Canal inválido." } } }, 422) : normal(url, init));
    await formularioListo();
    await persona.click(screen.getByLabelText(consentimiento));
    await persona.click(screen.getByRole("button", { name: "Crear intervención" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Revisa la plantilla y el canal.");
    expect(screen.getByLabelText("Plantilla")).toHaveAccessibleDescription("Plantilla fuera del catálogo.");
    expect(screen.getByLabelText("Canal")).toHaveAccessibleDescription("Canal inválido.");
    expect(screen.getByLabelText(consentimiento)).toBeChecked();
  });

  it("muestra el error del catálogo y permite reintentar", async () => {
    const persona = userEvent.setup();
    let disponible = false;
    mostrar(() => disponible ? respuesta(plantillas) : respuesta({ error: { codigo: "SIN_PERMISO", mensaje: "El catálogo no está disponible." } }, 403));
    expect(await screen.findByRole("alert")).toHaveTextContent("El catálogo no está disponible.");
    disponible = true;
    await persona.click(screen.getByRole("button", { name: "Reintentar" }));
    await formularioListo();
    expect(screen.getByText(plantillas[0].contenido)).toBeInTheDocument();
  });

  it("informa un catálogo vacío y evita crear sin plantilla del canal", async () => {
    mostrar(() => respuesta([]));
    expect(await screen.findByText(/No hay plantillas/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Crear intervención" })).toBeDisabled();
  });

  it("no duplica el POST y aborta el envío al cerrar sin aplicar la respuesta tardía", async () => {
    const persona = userEvent.setup();
    let resolver: ((valor: Response) => void) | undefined;
    const { fetchSimulado, completado } = mostrar((url, init) => init?.method === "POST" ? new Promise<Response>((cumplir) => { resolver = cumplir; }) : normal(url, init));
    await formularioListo();
    await persona.click(screen.getByLabelText(consentimiento));
    const formulario = screen.getByLabelText(consentimiento).closest("form");
    if (!formulario) throw new Error("Falta el formulario de intervención.");
    fireEvent.submit(formulario); fireEvent.submit(formulario);
    expect(fetchSimulado.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
    expect(screen.getByRole("button", { name: /Creando|Guardando|Enviando/ })).toBeDisabled();
    await persona.click(screen.getByRole("button", { name: "Cerrar diálogo" }));
    const envio = fetchSimulado.mock.calls.find(([, init]) => init?.method === "POST");
    expect(envio?.[1]?.signal?.aborted).toBe(true);
    await act(async () => resolver?.(respuesta(intervencion, 201)));
    expect(completado).not.toHaveBeenCalled();
  });

  it("rechaza una confirmación vacía del servidor", async () => {
    const persona = userEvent.setup();
    const { completado } = mostrar((url, init) => init?.method === "POST" ? new Response(null, { status: 204 }) : normal(url, init));
    await formularioListo();
    await persona.click(screen.getByLabelText(consentimiento));
    await persona.click(screen.getByRole("button", { name: "Crear intervención" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/no confirmó/i);
    expect(completado).not.toHaveBeenCalled();
  });

  // RNF-016: foco visible, recorrido con teclado y cancelación de lectura al desmontar.
  it("atrapa Tab y Mayús+Tab, cierra con Escape y restaura el foco", async () => {
    const persona = userEvent.setup();
    mostrar(); await formularioListo();
    await persona.keyboard("{Escape}");
    const activador = screen.getByRole("button", { name: "Abrir intervención" });
    await persona.click(activador); await formularioListo();
    const dialogo = within(screen.getByRole("dialog"));
    expect(dialogo.getByRole("button", { name: "Cerrar diálogo" })).toHaveFocus();
    await persona.tab({ shift: true });
    expect(dialogo.getByRole("button", { name: "Crear intervención" })).toHaveFocus();
    await persona.tab();
    expect(dialogo.getByRole("button", { name: "Cerrar diálogo" })).toHaveFocus();
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    await persona.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(activador).toHaveFocus();
    expect(document.body.style.overflow).toBe("");
  });

  it("cancela la carga del catálogo cuando se desmonta el diálogo", () => {
    const { unmount, fetchSimulado } = mostrar(() => new Promise<Response>(() => undefined));
    unmount();
    expect(fetchSimulado.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
    expect(document.body.style.overflow).toBe("");
  });
});
