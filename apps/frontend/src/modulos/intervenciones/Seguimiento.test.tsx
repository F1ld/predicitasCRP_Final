import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { Rol } from "../../nucleo/api/tipos";
import Seguimiento from "./Seguimiento";
import type { AccionIntervencion, CupoOut, IntervencionOut, RespuestaPaciente } from "./tipos";

const permisos = vi.hoisted(() => ({ escritura: true }));
vi.mock("../../nucleo/auth/useAuth", () => ({ useAuth: () => ({ tieneRol: (...roles: Rol[]) => roles.includes(permisos.escritura ? "RECEPCION" : "TECNICO_IA") }) }));
const fetchSimulado = vi.fn<typeof fetch>();
const intervencion: IntervencionOut = {
  id_intervencion: 17, id_cita: 324, id_cita_externa: "CIT-SIM-000324", id_operador: 5,
  canal_contacto: "WHATSAPP", plantilla_mensaje: "RECORDATORIO_SIMULADO", consentimiento_optout: false,
  estado_intervencion: "PENDIENTE", respuesta_paciente: null, fecha_hora_envio: "2026-10-19T11:00:00-05:00",
  fecha_hora_respuesta: null, acciones_disponibles: ["REGISTRAR_ENVIO", "REGISTRAR_FALLO"],
};
const cupo: CupoOut = {
  id_cupo_liberado: 31, id_cita_origen: 324, id_cita_externa_origen: "CIT-SIM-000324", especialidad: "CARDIOLOGIA",
  medico: "MED-SIM-01", fecha_hora_cupo: "2026-10-20T10:00:00-05:00", franja_horaria: "MANANA", estado_cupo: "DISPONIBLE",
  origen_liberacion: "INTERVENCION_VOLUNTARIA", liberado_en: "2026-10-19T14:00:00-05:00", oferta_vigente: null,
};
const solicitada: IntervencionOut = { ...intervencion, estado_intervencion: "RESPONDIDA", respuesta_paciente: "SOLICITA_LIBERACION", acciones_disponibles: ["LIBERAR_CUPO", "REGISTRAR_OPTOUT"] };
function respuesta(datos: unknown, status = 200) { return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } }); }
function errorApi(codigo: string, status = 409) { return respuesta({ error: { codigo, mensaje: `Detalle del servidor: ${codigo}.` } }, status); }
function montar() { return render(<MemoryRouter initialEntries={["/intervenciones/17"]}><Routes><Route path="/intervenciones/:id" element={<Seguimiento />} /></Routes></MemoryRouter>); }
function cuerpo(indice = 1): unknown { return JSON.parse(String(fetchSimulado.mock.calls[indice][1]?.body)); }
async function abrirLiberacion() { await userEvent.click(await screen.findByRole("button", { name: "Liberar cupo" })); return screen.getByRole("dialog"); }
async function confirmarLiberacion() { await userEvent.click(screen.getByRole("button", { name: "Confirmar liberación" })); }

beforeEach(() => { fetchSimulado.mockReset(); vi.stubGlobal("fetch", fetchSimulado); permisos.escritura = true; });

describe("M05-V03 consulta del seguimiento (RF-059 a RF-065, RNF-016)", () => {
  it("anuncia la carga y presenta datos seudonimizados, nulos y acciones del servidor", async () => {
    fetchSimulado.mockResolvedValue(respuesta({ ...intervencion, id_operador: null })); montar();
    expect(screen.getByText("Cargando seguimiento…")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Seguimiento de intervención #17" })).toBeInTheDocument();
    expect(screen.getByText("WhatsApp")).toBeInTheDocument();
    expect(screen.getByText("RECORDATORIO_SIMULADO")).toBeInTheDocument();
    expect(screen.getAllByText("Sin respuesta registrada")).toHaveLength(2);
    expect(screen.getAllByText("No registrado")).toHaveLength(2);
    expect(screen.getByRole("link", { name: intervencion.id_cita_externa })).toHaveAttribute("href", "/citas/324");
    expect(screen.getByRole("link", { name: /Volver a intervenciones/ })).toHaveAttribute("href", "/intervenciones");
    expect(screen.getByRole("button", { name: "Registrar envío" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Registrar entrega" })).not.toBeInTheDocument();
  });

  it("explica la ausencia de acciones y muestra fechas, operador y opt-out", async () => {
    fetchSimulado.mockResolvedValue(respuesta({ ...intervencion, estado_intervencion: "RESPONDIDA", respuesta_paciente: "SIN_RESPUESTA", fecha_hora_respuesta: "2026-10-19T11:30:00-05:00", consentimiento_optout: true, acciones_disponibles: [] })); montar();
    expect(await screen.findByText("No hay acciones disponibles para esta intervención.")).toBeInTheDocument();
    expect(screen.getByText("Usuario #5")).toBeInTheDocument(); expect(screen.getByText("Sin respuesta")).toBeInTheDocument();
    expect(screen.getByText("Sí · bloquea nuevos contactos del paciente")).toBeInTheDocument();
    expect(screen.getByText(/11:30/)).toBeInTheDocument(); expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("presenta error de consulta con reintento y la respuesta sin datos", async () => {
    fetchSimulado.mockResolvedValueOnce(errorApi("NO_ENCONTRADO", 404)).mockResolvedValueOnce(new Response(null, { status: 204 })); montar();
    expect(await screen.findByRole("alert")).toHaveTextContent("Detalle del servidor: NO_ENCONTRADO.");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("No se encontró la intervención.")).toBeInTheDocument();
  });

  it("TECNICO_IA solo consulta incluso si la respuesta expone todas las acciones", async () => {
    permisos.escritura = false;
    const acciones: AccionIntervencion[] = ["REGISTRAR_ENVIO", "REGISTRAR_ENTREGA", "REGISTRAR_FALLO", "REGISTRAR_RESPUESTA", "REGISTRAR_OPTOUT", "CONFIRMAR_CITA", "LIBERAR_CUPO"];
    fetchSimulado.mockResolvedValue(respuesta({ ...intervencion, respuesta_paciente: "CONFIRMA", acciones_disponibles: acciones })); montar();
    expect(await screen.findByText(/Tu rol permite consultar el seguimiento/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument(); expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Ir a confirmar la cita" })).not.toBeInTheDocument();
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
  });
});

describe("Registro explícito del envío (RF-059, RF-061)", () => {
  it.each([
    ["REGISTRAR_ENVIO", "Registrar envío", "ENVIADA"], ["REGISTRAR_ENTREGA", "Registrar entrega", "ENTREGADA"], ["REGISTRAR_FALLO", "Registrar fallo", "FALLIDA"],
  ] as const)("%s envía el campo exacto y aplica las nuevas acciones", async (accion, boton, estado) => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ ...intervencion, acciones_disponibles: [accion] }))
      .mockResolvedValueOnce(respuesta({ ...intervencion, estado_intervencion: estado, acciones_disponibles: [] })); montar();
    await userEvent.click(await screen.findByRole("button", { name: boton }));
    expect(await screen.findByText("Estado de la intervención actualizado.")).toBeInTheDocument();
    expect(cuerpo()).toEqual({ estado_intervencion: estado });
    expect(String(fetchSimulado.mock.calls[1][0])).toContain("/intervenciones/17/estado");
    expect(fetchSimulado.mock.calls[1][1]?.method).toBe("POST"); expect(screen.queryByRole("button", { name: boton })).not.toBeInTheDocument();
  });

  it("evita el doble envío y bloquea las demás acciones mientras espera", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(intervencion)).mockImplementation(() => new Promise<Response>(() => undefined)); montar();
    await userEvent.dblClick(await screen.findByRole("button", { name: "Registrar envío" }));
    expect(screen.getByRole("button", { name: "Registrar envío" })).toBeDisabled(); expect(screen.getByRole("button", { name: "Registrar fallo" })).toBeDisabled();
    expect(fetchSimulado).toHaveBeenCalledTimes(2);
  });

  it("explica TRANSICION_INVALIDA y actualiza las acciones desde el servidor", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(intervencion)).mockResolvedValueOnce(errorApi("TRANSICION_INVALIDA"))
      .mockResolvedValueOnce(respuesta({ ...intervencion, acciones_disponibles: [] })); montar();
    await userEvent.click(await screen.findByRole("button", { name: "Registrar envío" }));
    expect(await screen.findByText(/La acción no está permitida en el estado actual/)).toBeInTheDocument();
    expect(screen.getByText("No hay acciones disponibles para esta intervención.")).toBeInTheDocument(); expect(fetchSimulado).toHaveBeenCalledTimes(3);
  });

  it("informa respuesta vacía sin declarar un envío exitoso", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(intervencion)).mockResolvedValueOnce(new Response(null, { status: 204 })); montar();
    await userEvent.click(await screen.findByRole("button", { name: "Registrar envío" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El servidor no devolvió la intervención actualizada.");
    expect(screen.queryByText("Estado de la intervención actualizado.")).not.toBeInTheDocument();
  });
});

describe("Respuesta y consentimiento (RF-062, RF-064, RF-065, RF-067, RN02, RN03)", () => {
  it.each(["CONFIRMA", "SOLICITA_LIBERACION", "SOLICITA_REPROG", "SIN_RESPUESTA"] as const)("registra %s sin enviar ninguna transición a la cita", async (eleccion: RespuestaPaciente) => {
    const acciones: AccionIntervencion[] = eleccion === "CONFIRMA" ? ["CONFIRMAR_CITA"] : eleccion === "SOLICITA_LIBERACION" ? ["LIBERAR_CUPO"] : [];
    fetchSimulado.mockResolvedValueOnce(respuesta({ ...intervencion, estado_intervencion: "ENTREGADA", acciones_disponibles: ["REGISTRAR_RESPUESTA"] }))
      .mockResolvedValueOnce(respuesta({ ...intervencion, estado_intervencion: "RESPONDIDA", respuesta_paciente: eleccion, acciones_disponibles: acciones })); montar();
    await userEvent.selectOptions(await screen.findByLabelText("Respuesta del paciente"), eleccion);
    await userEvent.click(screen.getByRole("button", { name: "Registrar respuesta" }));
    expect(await screen.findByText(/Respuesta registrada. El estado de la cita se conserva/)).toBeInTheDocument();
    expect(cuerpo()).toEqual({ respuesta_paciente: eleccion, optout: false });
    expect(String(fetchSimulado.mock.calls[1][0])).toContain("/intervenciones/17/respuesta");
    expect(fetchSimulado.mock.calls.every(([url]) => !String(url).includes("/citas/"))).toBe(true); expect(fetchSimulado).toHaveBeenCalledTimes(2);
    if (eleccion === "CONFIRMA") {
      expect(screen.getByRole("link", { name: "Ir a confirmar la cita" })).toHaveAttribute("href", "/citas/324?id_intervencion=17");
      expect(screen.getByText(/selecciona la intervención #17/)).toBeInTheDocument();
    }
    if (eleccion === "SOLICITA_LIBERACION") expect(screen.getByRole("button", { name: "Liberar cupo" })).toBeInTheDocument();
    if (eleccion === "SOLICITA_REPROG") expect(screen.getByText("Gestiónalo en el sistema de agendamiento")).toBeInTheDocument();
  });

  it("la llamada enviada admite respuesta cuando lo habilita la API; exige elegir una y admite opt-out", async () => {
    const llamada: IntervencionOut = { ...intervencion, canal_contacto: "LLAMADA_TELEFONICA", estado_intervencion: "ENVIADA", acciones_disponibles: ["REGISTRAR_RESPUESTA"] };
    fetchSimulado.mockResolvedValueOnce(respuesta(llamada)).mockResolvedValueOnce(respuesta({ ...llamada, estado_intervencion: "RESPONDIDA", respuesta_paciente: "SIN_RESPUESTA", consentimiento_optout: true, acciones_disponibles: [] })); montar();
    await userEvent.click(await screen.findByRole("button", { name: "Registrar respuesta" })); expect(fetchSimulado).toHaveBeenCalledTimes(1);
    await userEvent.selectOptions(screen.getByLabelText("Respuesta del paciente"), "SIN_RESPUESTA");
    await userEvent.click(screen.getByRole("checkbox", { name: /solicita no recibir más comunicaciones/ }));
    await userEvent.click(screen.getByRole("button", { name: "Registrar respuesta" }));
    expect(await screen.findByText("Sí · bloquea nuevos contactos del paciente")).toBeInTheDocument(); expect(cuerpo()).toEqual({ respuesta_paciente: "SIN_RESPUESTA", optout: true });
  });

  it("registra opt-out posterior por su endpoint sin cambiar la cita", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ ...intervencion, acciones_disponibles: ["REGISTRAR_OPTOUT"] }))
      .mockResolvedValueOnce(respuesta({ ...intervencion, consentimiento_optout: true, acciones_disponibles: [] })); montar();
    await userEvent.click(await screen.findByRole("button", { name: "Registrar opt-out" }));
    expect(await screen.findByText(/Opt-out registrado. El paciente no recibirá nuevas intervenciones/)).toBeInTheDocument();
    expect(String(fetchSimulado.mock.calls[1][0])).toContain("/intervenciones/17/optout"); expect(fetchSimulado.mock.calls[1][1]?.body).toBeUndefined();
    expect(screen.queryByRole("button", { name: "Registrar opt-out" })).not.toBeInTheDocument();
  });

  it("no crea acciones de confirmación o liberación solo a partir de la respuesta", async () => {
    fetchSimulado.mockResolvedValue(respuesta({ ...intervencion, respuesta_paciente: "CONFIRMA", acciones_disponibles: [] })); montar();
    await screen.findByText("No hay acciones disponibles para esta intervención.");
    expect(screen.queryByRole("link", { name: "Ir a confirmar la cita" })).not.toBeInTheDocument();
  });

  it("muestra TRANSICION_INVALIDA al registrar una respuesta y permite consultar el estado actual", async () => {
    const actual = { ...intervencion, acciones_disponibles: ["REGISTRAR_RESPUESTA"] };
    fetchSimulado.mockResolvedValueOnce(respuesta(actual)).mockResolvedValueOnce(errorApi("TRANSICION_INVALIDA")).mockResolvedValueOnce(respuesta(actual)); montar();
    await userEvent.selectOptions(await screen.findByLabelText("Respuesta del paciente"), "CONFIRMA");
    await userEvent.click(screen.getByRole("button", { name: "Registrar respuesta" }));
    expect(await screen.findByText(/La acción no está permitida en el estado actual/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Ir a confirmar la cita" })).not.toBeInTheDocument();
  });

  it("bloquea el envío duplicado del formulario y su edición mientras espera", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ ...intervencion, acciones_disponibles: ["REGISTRAR_RESPUESTA", "REGISTRAR_OPTOUT"] })).mockImplementation(() => new Promise<Response>(() => undefined)); montar();
    const campo = await screen.findByLabelText("Respuesta del paciente"); await userEvent.selectOptions(campo, "CONFIRMA");
    const formulario = campo.closest("form")!; fireEvent.submit(formulario); fireEvent.submit(formulario);
    expect(screen.getByRole("button", { name: "Guardando…" })).toBeDisabled(); expect(campo).toBeDisabled(); expect(fetchSimulado).toHaveBeenCalledTimes(2);
  });
});

describe("Liberación voluntaria con confirmación (RF-068, RN04, CP-M05-07)", () => {
  it.each(["", " Solicitud sintética del paciente "])("exige confirmación y envía el motivo opcional %j", async (motivo) => {
    fetchSimulado.mockResolvedValueOnce(respuesta(solicitada)).mockResolvedValueOnce(respuesta(cupo, 201)); montar();
    const dialogo = await abrirLiberacion(); expect(fetchSimulado).toHaveBeenCalledTimes(1);
    expect(within(dialogo).getByText(/La cita quedará Liberada y su cupo quedará Disponible/)).toBeInTheDocument();
    const campo = within(dialogo).getByLabelText("Motivo de liberación (opcional)"); expect(campo).toHaveAttribute("maxlength", "255");
    if (motivo) await userEvent.type(campo, motivo);
    await confirmarLiberacion();
    expect(await screen.findByText(/Cupo #31 liberado/)).toBeInTheDocument();
    expect(cuerpo()).toEqual(motivo ? { motivo: motivo.trim() } : {}); expect(String(fetchSimulado.mock.calls[1][0])).toContain("/intervenciones/17/liberar-cupo");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); expect(screen.queryByRole("button", { name: "Liberar cupo" })).not.toBeInTheDocument();
  });

  it("cancelar no libera y regresa el foco al botón", async () => {
    fetchSimulado.mockResolvedValue(respuesta(solicitada)); montar(); await abrirLiberacion();
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); expect(screen.getByRole("button", { name: "Liberar cupo" })).toHaveFocus(); expect(fetchSimulado).toHaveBeenCalledTimes(1);
  });

  it("durante la liberación impide repetirla y cerrar el diálogo con Escape", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(solicitada)).mockImplementation(() => new Promise<Response>(() => undefined)); montar(); await abrirLiberacion();
    const campo = screen.getByLabelText("Motivo de liberación (opcional)"); const formulario = campo.closest("form")!;
    fireEvent.submit(formulario); fireEvent.submit(formulario); await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("dialog")).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Liberando…" })).toBeDisabled(); expect(campo).toBeDisabled(); expect(fetchSimulado).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["SIN_SOLICITUD_LIBERACION", /Solo puedes liberar un cupo si el paciente solicitó su liberación/],
    ["TRANSICION_INVALIDA", /La acción no está permitida en el estado actual/],
    ["CITA_PASADA", /No se puede liberar el cupo de una cita que ya pasó/],
    ["CUPO_YA_LIBERADO", /El cupo de esta cita ya fue liberado/],
  ] as const)("explica %s sin declarar una liberación exitosa", async (codigo, mensaje) => {
    fetchSimulado.mockResolvedValueOnce(respuesta(solicitada)).mockResolvedValueOnce(errorApi(codigo)).mockResolvedValueOnce(respuesta(solicitada)); montar(); await abrirLiberacion(); await confirmarLiberacion();
    expect(await screen.findByText(mensaje)).toBeInTheDocument(); expect(screen.queryByText(/Cupo #31 liberado/)).not.toBeInTheDocument();
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(3));
  });

  it("explica la respuesta vacía del cupo y no asume la liberación", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(solicitada)).mockResolvedValueOnce(new Response(null, { status: 204 })); montar(); await abrirLiberacion(); await confirmarLiberacion();
    expect(await screen.findByRole("alert")).toHaveTextContent("El servidor no devolvió el cupo liberado."); expect(screen.getByRole("button", { name: "Liberar cupo" })).toBeEnabled();
  });

  it.each(["estado", "respuesta", "optout", "liberar-cupo"])("maneja NO_ENCONTRADO en %s", async (endpoint) => {
    const acciones: AccionIntervencion[] = endpoint === "estado" ? ["REGISTRAR_ENVIO"] : endpoint === "respuesta" ? ["REGISTRAR_RESPUESTA"] : endpoint === "optout" ? ["REGISTRAR_OPTOUT"] : ["LIBERAR_CUPO"];
    fetchSimulado.mockResolvedValueOnce(respuesta({ ...solicitada, acciones_disponibles: acciones })).mockResolvedValueOnce(errorApi("NO_ENCONTRADO", 404)); montar();
    if (endpoint === "liberar-cupo") { await abrirLiberacion(); await confirmarLiberacion(); }
    else if (endpoint === "respuesta") { await userEvent.selectOptions(await screen.findByLabelText("Respuesta del paciente"), "CONFIRMA"); await userEvent.click(screen.getByRole("button", { name: "Registrar respuesta" })); }
    else await userEvent.click(await screen.findByRole("button", { name: endpoint === "estado" ? "Registrar envío" : "Registrar opt-out" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Detalle del servidor: NO_ENCONTRADO."); expect(fetchSimulado).toHaveBeenCalledTimes(2);
  });
});
