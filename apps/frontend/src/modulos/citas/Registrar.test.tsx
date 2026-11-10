import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Rol } from "../../nucleo/api/tipos";
import type { ContextoAuth } from "../../nucleo/auth/contexto";
import Registrar from "./Registrar";
import type { CatalogosOut, CitaDetalleOut } from "./tipos";

const permisos = vi.hoisted(() => ({ rol: "RECEPCION" as Rol }));
const tieneRolSimulado = vi.hoisted(() => vi.fn<ContextoAuth["tieneRol"]>());
vi.mock("../../nucleo/auth/useAuth", () => ({ useAuth: () => ({ tieneRol: tieneRolSimulado }) }));

// RF-010, RN03, RN17 y RNF-007: fixtures sintéticos del contrato M02-E03/E07.
const catalogos: CatalogosOut = {
  especialidades: ["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"], estados: ["RECIBIDA"], niveles_riesgo: ["BAJO", "MEDIO", "ALTO"],
  medicos: ["Profesional sintético 1"], canales_origen: ["WEB", "CALL_CENTER", "PRESENCIAL"], tipos_paciente: ["NUEVO", "CONTINUADOR"],
};
const cita: CitaDetalleOut = {
  id_cita: 324, id_cita_externa: "CIT-SIM-000324", paciente_anon_id: "PAC-SIM-0007", sede: "SAN_ISIDRO", especialidad: "CARDIOLOGIA",
  medico: "Profesional sintético 1", fecha_hora_cita: new Date("2026-10-20T09:00").toISOString(), fecha_registro_cita: new Date("2026-10-01T10:00").toISOString(),
  antelacion_dias: 19, tipo_paciente: "CONTINUADOR", canal_origen: "WEB", franja_horaria: "MANANA", dia_semana: "MARTES",
  inasistencias_previas: 0, reprogramaciones_prev: 0, asistencias_previas: 1, estado_actual: "RECIBIDA", target_no_show: null,
  historial: [{ id_historial: 1, estado_anterior: null, estado_nuevo: "RECIBIDA", id_usuario_actor: 2, motivo_cambio: null, fecha_hora_evento: "2026-10-18T10:00:00-05:00" }],
  check_in: null, predicciones: [], intervenciones: [], cupo_liberado: null, reasignacion: null,
};
const fetchSimulado = vi.fn<typeof fetch>();
function respuesta(datos: unknown, status = 200) {
  return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } });
}
function montar() {
  return render(<MemoryRouter initialEntries={["/citas/nueva"]}><Routes><Route path="/citas/nueva" element={<Registrar />} /><Route path="/citas/:id" element={<p>Detalle de la cita incorporada</p>} /><Route path="/citas" element={<p>Bandeja de citas</p>} /></Routes></MemoryRouter>);
}
async function cargar() {
  fetchSimulado.mockResolvedValueOnce(respuesta(catalogos));
  montar();
  await screen.findByRole("form", { name: "Registrar cita existente" });
}
function completar() {
  fireEvent.change(screen.getByLabelText("ID de cita externa *"), { target: { value: " CIT-SIM-000324 " } });
  fireEvent.change(screen.getByLabelText("ID seudonimizado del paciente *"), { target: { value: " PAC-SIM-0007 " } });
  fireEvent.change(screen.getByLabelText("Especialidad *"), { target: { value: "CARDIOLOGIA" } });
  fireEvent.change(screen.getByLabelText("Médico *"), { target: { value: " Profesional sintético 1 " } });
  fireEvent.change(screen.getByLabelText("Fecha y hora de la cita *"), { target: { value: "2026-10-20T09:00" } });
  fireEvent.change(screen.getByLabelText("Fecha y hora de registro original *"), { target: { value: "2026-10-01T10:00" } });
  fireEvent.change(screen.getByLabelText("Tipo de paciente *"), { target: { value: "CONTINUADOR" } });
  fireEvent.change(screen.getByLabelText("Canal de origen *"), { target: { value: "WEB" } });
}
beforeEach(() => {
  permisos.rol = "RECEPCION";
  tieneRolSimulado.mockReset().mockImplementation((...roles) => roles.includes(permisos.rol));
  fetchSimulado.mockReset(); vi.stubGlobal("fetch", fetchSimulado); sessionStorage.clear();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Registro manual M02-V03 (RF-010, RN03, RN17, RNF-016)", () => {
  it.each(["ADMINISTRADOR", "RECEPCION"] as const)("permite registrar a %s usando la firma real de tieneRol", async (rol) => {
    permisos.rol = rol;
    await cargar();
    expect(tieneRolSimulado).toHaveBeenCalledWith("ADMINISTRADOR", "RECEPCION");
    expect(screen.getByRole("button", { name: "Registrar cita" })).toBeEnabled();
  });

  it("anuncia carga de catálogos y mantiene el aviso literal RN03", () => {
    fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined));
    montar();
    expect(screen.getByText("Cargando catálogos…")).toBeInTheDocument();
    expect(screen.getByText("Solo incorpora al piloto una cita que ya existe; no agenda")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Registrar cita" })).not.toBeInTheDocument();
  });

  it("carga opciones del contrato, mantiene sede y permite un médico nuevo", async () => {
    await cargar();
    expect(screen.getByLabelText("Sede")).toHaveValue("San Isidro");
    expect(screen.getByLabelText("Sede")).toHaveAttribute("readonly");
    expect(screen.getByRole("option", { name: "Cardiología" })).toHaveValue("CARDIOLOGIA");
    expect(screen.getByRole("option", { name: "Call center" })).toHaveValue("CALL_CENTER");
    expect(screen.getByLabelText("Médico *")).toHaveAttribute("list", "registro-medicos");
    fireEvent.change(screen.getByLabelText("Médico *"), { target: { value: "Profesional sintético nuevo" } });
    expect(screen.getByLabelText("Médico *")).toHaveAttribute("aria-invalid", "false");
    expect(String(fetchSimulado.mock.calls[0][0])).toContain("/citas/catalogos");
  });

  it("presenta catálogo vacío y vuelve a cargarlo", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ ...catalogos, especialidades: [] })).mockResolvedValueOnce(respuesta(catalogos));
    montar();
    expect(await screen.findByText(/No hay opciones en los catálogos/)).toBeInTheDocument();
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Actualizar catálogos" }));
    expect(await screen.findByRole("form")).toBeInTheDocument();
  });

  it("presenta fallo de catálogo y permite reintentar", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo: "ERROR_INTERNO", mensaje: "Catálogos no disponibles." } }, 500)).mockResolvedValueOnce(respuesta(catalogos));
    montar();
    expect(await screen.findByText("Catálogos no disponibles.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("form")).toBeInTheDocument();
  });

  it("valida obligatorios, anuncia errores asociados y enfoca el primero", async () => {
    await cargar();
    fireEvent.change(screen.getByLabelText("ID de cita externa *"), { target: { value: "" } });
    await userEvent.click(screen.getByRole("button", { name: "Registrar cita" }));
    expect(screen.getByText("Revisa los campos indicados antes de incorporar la cita.")).toBeInTheDocument();
    expect(screen.getByLabelText("ID de cita externa *")).toHaveFocus();
    expect(screen.getByLabelText("ID de cita externa *")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("ID de cita externa *")).toHaveAttribute("aria-describedby", "error-id_cita_externa");
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("ID de cita externa *"), { target: { value: "CIT-SIM-000324" } });
    expect(screen.getByLabelText("ID de cita externa *")).toHaveAttribute("aria-invalid", "false");
  });

  it("valida en vivo domingos, secuencia de fechas y contadores enteros", async () => {
    await cargar(); completar();
    fireEvent.change(screen.getByLabelText("Fecha y hora de la cita *"), { target: { value: "2026-10-18T09:00" } });
    expect(screen.getByText(/Los domingos están fuera del piloto/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Fecha y hora de la cita *"), { target: { value: "2026-10-20T09:00" } });
    fireEvent.change(screen.getByLabelText("Fecha y hora de registro original *"), { target: { value: "2026-10-21T09:00" } });
    expect(screen.getByText("El registro debe ser anterior o igual a la fecha y hora de la cita.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Inasistencias previas"), { target: { value: "-1" } });
    fireEvent.change(screen.getByLabelText("Asistencias previas"), { target: { value: "1.5" } });
    fireEvent.change(screen.getByLabelText("Reprogramaciones previas"), { target: { value: "1.5" } });
    expect(screen.getAllByText("Usa un número entero mayor o igual a 0.")).toHaveLength(3);
    await userEvent.click(screen.getByRole("button", { name: "Registrar cita" }));
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
  });

  it("no confunde una entrada numérica incompleta con un contador omitido (RN17)", async () => {
    await cargar(); completar();
    const contador = screen.getByLabelText("Inasistencias previas") as HTMLInputElement;
    // Los navegadores representan '-' o 'e' con value='' y badInput=true.
    Object.defineProperty(contador, "validity", { configurable: true, value: { badInput: true } });
    fireEvent.input(contador, { target: { value: "" } });
    expect(contador).toHaveAttribute("aria-invalid", "true");
    await userEvent.click(screen.getByRole("button", { name: "Registrar cita" }));
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
    Object.defineProperty(contador, "validity", { configurable: true, value: { badInput: false } });
    fireEvent.input(contador, { target: { value: "0" } });
    expect(contador).toHaveAttribute("aria-invalid", "false");
    fetchSimulado.mockResolvedValueOnce(respuesta(cita, 201));
    await userEvent.click(screen.getByRole("button", { name: "Registrar cita" }));
    expect(await screen.findByText("Detalle de la cita incorporada")).toBeInTheDocument();
    expect(JSON.parse(String(fetchSimulado.mock.calls[1][1]?.body))).toHaveProperty("inasistencias_previas", 0);
  });

  it("envía nombres exactos, horas locales, omite contadores RN17 y abre el detalle", async () => {
    await cargar(); completar();
    fetchSimulado.mockResolvedValueOnce(respuesta(cita, 201));
    await userEvent.click(screen.getByRole("button", { name: "Registrar cita" }));
    expect(await screen.findByText("Detalle de la cita incorporada")).toBeInTheDocument();
    const [url, opciones] = fetchSimulado.mock.calls[1];
    expect(new URL(String(url)).pathname).toBe("/citas");
    expect(opciones?.method).toBe("POST");
    expect(JSON.parse(String(opciones?.body))).toEqual({
      id_cita_externa: "CIT-SIM-000324", paciente_anon_id: "PAC-SIM-0007", sede: "SAN_ISIDRO", especialidad: "CARDIOLOGIA",
      medico: "Profesional sintético 1", fecha_hora_cita: new Date("2026-10-20T09:00").toISOString(), fecha_registro_cita: new Date("2026-10-01T10:00").toISOString(),
      tipo_paciente: "CONTINUADOR", canal_origen: "WEB", reprogramaciones_prev: 0,
    });
  });

  it("respeta contadores explícitos y bloquea doble envío", async () => {
    await cargar(); completar();
    fireEvent.change(screen.getByLabelText("Inasistencias previas"), { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText("Asistencias previas"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Reprogramaciones previas"), { target: { value: "2" } });
    fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined));
    fireEvent.submit(screen.getByRole("form")); fireEvent.submit(screen.getByRole("form"));
    expect(screen.getByText("Incorporando la cita al piloto…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardando…" })).toBeDisabled();
    expect(screen.getByLabelText("ID de cita externa *")).toBeDisabled();
    expect(fetchSimulado).toHaveBeenCalledTimes(2);
    const peticion = JSON.parse(String(fetchSimulado.mock.calls[1][1]?.body));
    expect(peticion).toMatchObject({ inasistencias_previas: 0, asistencias_previas: 3, reprogramaciones_prev: 2 });
    await userEvent.click(screen.getByRole("link", { name: "Cancelar" }));
    expect(screen.queryByText("Bandeja de citas")).not.toBeInTheDocument();
  });

  it.each([
    ["CITA_DUPLICADA", 409, "ID de cita externa *", "Ya existe una cita con este identificador externo."],
    ["FUERA_DE_PERIMETRO", 422, "Especialidad *", "Revisa que la especialidad pertenezca al piloto."],
    ["FECHAS_INCONSISTENTES", 422, "Fecha y hora de registro original *", "El registro debe ser anterior o igual a la fecha y hora de la cita."],
  ])("muestra %s y el error en su campo", async (codigo, status, etiqueta, texto) => {
    await cargar(); completar();
    fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo, mensaje: "Revisa los datos de la cita." } }, Number(status)));
    await userEvent.click(screen.getByRole("button", { name: "Registrar cita" }));
    expect(await screen.findByText(texto)).toBeInTheDocument();
    expect(screen.getByLabelText(etiqueta)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("button", { name: "Registrar cita" })).toBeEnabled();
    expect(screen.getByLabelText("ID de cita externa *")).toHaveValue(" CIT-SIM-000324 ");
  });

  it("asocia errores VALIDACION por campo y permite corregir y reenviar", async () => {
    await cargar(); completar();
    fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo: "VALIDACION", mensaje: "Revisa los campos.", campos: { "body.medico": "Médico inválido en la fuente." } } }, 422));
    await userEvent.click(screen.getByRole("button", { name: "Registrar cita" }));
    expect(await screen.findByText("Médico inválido en la fuente.")).toBeInTheDocument();
    expect(screen.getByLabelText("Médico *")).toHaveAttribute("aria-describedby", "error-medico");
    fireEvent.change(screen.getByLabelText("Médico *"), { target: { value: "Profesional sintético 2" } });
    expect(screen.queryByText("Médico inválido en la fuente.")).not.toBeInTheDocument();
    fetchSimulado.mockResolvedValueOnce(respuesta(cita, 201));
    await userEvent.click(screen.getByRole("button", { name: "Registrar cita" }));
    expect(await screen.findByText("Detalle de la cita incorporada")).toBeInTheDocument();
  });

  it("explica SIN_PERMISO devuelto al guardar", async () => {
    await cargar(); completar();
    fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo: "SIN_PERMISO", mensaje: "Acceso restringido." } }, 403));
    await userEvent.click(screen.getByRole("button", { name: "Registrar cita" }));
    expect(await screen.findByText("Tu rol no tiene permiso para realizar esta acción.")).toBeInTheDocument();
  });

  it("aplica defensa local: TECNICO_IA no ve acciones ni solicita catálogos", async () => {
    permisos.rol = "TECNICO_IA"; montar();
    expect(screen.getByText(/Tu rol permite consultar las citas/)).toBeInTheDocument();
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    await waitFor(() => expect(fetchSimulado).not.toHaveBeenCalled());
  });
});
