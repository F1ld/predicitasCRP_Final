import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import Detalle from "./Detalle";
import type { CitaDetalleOut, IntervencionOut, PrediccionOut } from "./tipos";
import type { Rol } from "../../nucleo/api/tipos";

const permisos = vi.hoisted(() => ({ escritura: true }));
vi.mock("../../nucleo/auth/useAuth", () => ({ useAuth: () => ({ tieneRol: (...roles: Rol[]) => roles.includes(permisos.escritura ? "RECEPCION" : "TECNICO_IA") }) }));
const fetchSimulado = vi.fn<typeof fetch>();
const prediccion: PrediccionOut = {
  id_prediccion: 27, id_cita: 324, version_modelo: "SIMULADOR_v0.1.0", probabilidad_no_show: 0.712,
  nivel_riesgo: "ALTO", umbral_aplicado: 0.45, features_snapshot: { antelacion_dias: 8, confirmada: false },
  explicabilidad_resumen: "Mayor antelación y antecedentes de inasistencia sintéticos.",
  fecha_hora_inferencia: "2026-10-20T08:30:00-05:00", resultado_simulado: true, ya_existia: false,
};
const intervencion: IntervencionOut = {
  id_intervencion: 17, id_cita: 324, id_cita_externa: "CIT-SIM-000324", id_operador: 5,
  canal_contacto: "WHATSAPP", plantilla_mensaje: "RECORDATORIO_SIMULADO", consentimiento_optout: false,
  estado_intervencion: "RESPONDIDA", respuesta_paciente: "CONFIRMA", fecha_hora_envio: "2026-10-19T11:00:00-05:00",
  fecha_hora_respuesta: "2026-10-19T11:10:00-05:00", acciones_disponibles: ["CONFIRMAR_CITA"],
};
const detalle: CitaDetalleOut = {
  id_cita: 324, id_cita_externa: "CIT-SIM-000324", paciente_anon_id: "PAC-SIM-000021", sede: "SAN_ISIDRO",
  especialidad: "CARDIOLOGIA", medico: "MED-SIM-01", fecha_hora_cita: "2026-10-20T10:00:00-05:00",
  fecha_registro_cita: "2026-10-12T08:00:00-05:00", antelacion_dias: 8, tipo_paciente: "NUEVO", canal_origen: "WEB",
  franja_horaria: "MANANA", dia_semana: "MARTES", inasistencias_previas: 1, reprogramaciones_prev: 0,
  asistencias_previas: 2, estado_actual: "RECIBIDA", target_no_show: null,
  historial: [{ id_historial: 3, id_usuario_actor: null, estado_anterior: null, estado_nuevo: "RECIBIDA", motivo_cambio: null, fecha_hora_evento: "2026-10-12T08:00:00-05:00" }],
  check_in: null, predicciones: [], intervenciones: [], cupo_liberado: null, reasignacion: null,
};
const cupo: NonNullable<CitaDetalleOut["cupo_liberado"]> = {
  id_cupo_liberado: 31, id_cita_origen: 324, id_cita_externa_origen: "CIT-SIM-000324", especialidad: "CARDIOLOGIA",
  medico: "MED-SIM-01", fecha_hora_cupo: detalle.fecha_hora_cita, franja_horaria: "MANANA", estado_cupo: "EN_OFERTA",
  origen_liberacion: "CANCELACION_EXTERNA", liberado_en: "2026-10-19T14:00:00-05:00",
  oferta_vigente: { id_candidato: 83, paciente_anon_id: "PAC-SIM-000083", id_operador: 8, fecha_hora_oferta: "2026-10-19T14:10:00-05:00" },
};
const reasignacion: NonNullable<CitaDetalleOut["reasignacion"]> = {
  id_reasignacion: 41, id_cupo_liberado: 31, id_candidato: 83, paciente_anon_id: "PAC-SIM-000083",
  id_operador_confirma: 9, confirmacion_humana: true, medio_confirmacion: "LLAMADA_CONFIRMADA",
  observaciones: "Confirmación sintética revisada", fecha_hora_reasigna: "2026-10-19T14:20:00-05:00",
};

function respuesta(datos: unknown, status = 200) {
  return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } });
}
function montar(volver: unknown = "/citas?medico=MED-SIM-01") {
  return render(<MemoryRouter initialEntries={[{ pathname: "/citas/324", state: { volver } }]}><Routes><Route path="/citas/:id" element={<Detalle />} /></Routes></MemoryRouter>);
}
function errorApi(codigo: string, status = 409) { return respuesta({ error: { codigo, mensaje: `Detalle del servidor: ${codigo}.` } }, status); }
function cuerpo(indice = 1): unknown { return JSON.parse(String(fetchSimulado.mock.calls[indice][1]?.body)); }
async function abrirCambio(nombre = "Confirmada") { await userEvent.click(await screen.findByRole("button", { name: `Marcar como ${nombre}` })); }
async function confirmar() { await userEvent.click(screen.getByRole("button", { name: "Confirmar cambio" })); }

beforeEach(() => {
  fetchSimulado.mockReset(); vi.stubGlobal("fetch", fetchSimulado); permisos.escritura = true; sessionStorage.clear();
  vi.spyOn(Date, "now").mockReturnValue(new Date("2026-10-20T09:00:00-05:00").getTime());
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value(this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value(this: HTMLDialogElement) { this.removeAttribute("open"); } });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("M02-V02 consulta completa (RF-018, RF-025, RNF-007, RNF-016)", () => {
  it("anuncia la carga y luego cada sección vacía sin inventar información", async () => {
    fetchSimulado.mockResolvedValue(respuesta(detalle)); montar();
    expect(screen.getByText("Cargando detalle…")).toBeInTheDocument();
    expect(await screen.findByText(detalle.paciente_anon_id)).toBeInTheDocument();
    for (const texto of ["No hay llegada registrada.", "No hay predicciones registradas.", "No hay intervenciones registradas.", "No hay cupo liberado para esta cita.", "No hay reasignación registrada.", "Sin motivo registrado"]) expect(screen.getByText(texto)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Volver a la bandeja/ })).toHaveAttribute("href", "/citas?medico=MED-SIM-01");
    expect(screen.getByRole("link", { name: "Ver trazabilidad" })).toHaveAttribute("href", "/citas/324/trazabilidad");
  });

  it("muestra versión, probabilidad, umbral, explicación y snapshot, contactos, llegada, oferta y reasignación", async () => {
    fetchSimulado.mockResolvedValue(respuesta({ ...detalle, predicciones: [prediccion], intervenciones: [intervencion], cupo_liberado: cupo, reasignacion,
      check_in: { fecha_hora_check_in: "2026-10-20T08:50:00-05:00", id_usuario: 6 } })); montar();
    expect(await screen.findByText("Versión SIMULADOR_v0.1.0")).toBeInTheDocument();
    expect(screen.getByText(/71[.,]2 %/)).toBeInTheDocument();
    expect(screen.getByText("0.45")).toBeInTheDocument();
    expect(screen.getByText(prediccion.explicabilidad_resumen!)).toBeInTheDocument();
    expect(screen.getByText("Resultado simulado: no es desempeño real")).toBeInTheDocument();
    expect(screen.getByLabelText("Riesgo de inasistencia: ALTO")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Variables conservadas al calcular el riesgo"));
    expect(screen.getByText("antelacion_dias")).toBeVisible();
    expect(screen.getByText("false")).toBeVisible();
    for (const texto of ["Intervención #17", "CONFIRMA", "Usuario #6", "Oferta vigente", "Confirmación sintética revisada", "LLAMADA_CONFIRMADA"]) expect(screen.getByText(texto)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Registrar llegada (check-in)" })).not.toBeInTheDocument();
    expect(screen.getByText(/no es una decisión clínica/)).toBeInTheDocument();
    expect(screen.getByText(/La nueva cita se agenda en el sistema externo/)).toBeInTheDocument();
  });

  it("explica datos opcionales ausentes, cupo sin oferta y predicción real sin rótulo simulado", async () => {
    fetchSimulado.mockResolvedValue(respuesta({ ...detalle, predicciones: [{ ...prediccion, resultado_simulado: false, explicabilidad_resumen: null, features_snapshot: { ejemplo: { valor: 1 } } }],
      intervenciones: [{ ...intervencion, id_operador: null, respuesta_paciente: null, fecha_hora_respuesta: null, consentimiento_optout: true }],
      cupo_liberado: { ...cupo, oferta_vigente: null }, reasignacion: { ...reasignacion, observaciones: null }, historial: [] })); montar();
    expect(await screen.findByText("Sin explicación registrada")).toBeInTheDocument();
    for (const texto of ["Sin respuesta registrada", "No hay oferta vigente.", "Sin observaciones", "No hay transiciones registradas.", "Sí · no admite nuevos contactos"]) expect(screen.getByText(texto)).toBeInTheDocument();
    expect(screen.queryByText("Resultado simulado: no es desempeño real")).not.toBeInTheDocument();
    await userEvent.click(screen.getByText("Variables conservadas al calcular el riesgo"));
    expect(screen.getByText('{"valor":1}')).toBeVisible();
  });

  it("presenta un error recuperable de consulta y conserva una vuelta segura", async () => {
    fetchSimulado.mockResolvedValueOnce(errorApi("NO_ENCONTRADO", 404)).mockResolvedValueOnce(respuesta(detalle)); montar("https://example.invalid");
    expect(await screen.findByRole("alert")).toHaveTextContent("Detalle del servidor: NO_ENCONTRADO.");
    expect(screen.getByRole("link", { name: /Volver a la bandeja/ })).toHaveAttribute("href", "/citas");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText(detalle.paciente_anon_id)).toBeInTheDocument();
  });

  it("muestra cita no encontrada también ante una respuesta vacía", async () => {
    fetchSimulado.mockResolvedValue(new Response(null, { status: 204 })); montar(null);
    expect(await screen.findByText("No se encontró la cita.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Volver a la bandeja/ })).toHaveAttribute("href", "/citas");
  });

  it("TECNICO_IA consulta todas las secciones sin ninguna acción de escritura", async () => {
    permisos.escritura = false; fetchSimulado.mockResolvedValue(respuesta({ ...detalle, predicciones: [prediccion] })); montar();
    expect(await screen.findByText(/Tu rol permite consultar/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Marcar como|Calcular riesgo|Registrar llegada/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Crear intervención" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Observación de llegada (opcional)")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver trazabilidad" })).toBeInTheDocument();
  });
});

describe("Cambio de estado con campos exactos (RF-019 a RF-024, RF-027, RN01, RN02)", () => {
  it("REPROGRAMADA exige fecha y envía la fecha acordada con zona Lima", async () => {
    const nueva = { ...detalle, estado_actual: "REPROGRAMADA", reprogramaciones_prev: 1, fecha_hora_cita: "2026-10-22T09:30:00-05:00" };
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockResolvedValueOnce(respuesta(nueva)).mockResolvedValueOnce(respuesta(nueva)); montar();
    await abrirCambio("Reprogramada");
    const fecha = screen.getByLabelText("Nueva fecha y hora de cita (Lima)");
    expect(fecha).toBeRequired();
    await confirmar(); expect(fetchSimulado).toHaveBeenCalledTimes(1);
    fireEvent.change(fecha, { target: { value: "2026-10-22T09:30" } });
    await userEvent.type(screen.getByLabelText("Motivo (opcional)"), " Cambio sintético acordado ");
    await confirmar();
    expect(await screen.findByText("Estado actualizado a Reprogramada.")).toBeInTheDocument();
    expect(cuerpo()).toEqual({ estado_nuevo: "REPROGRAMADA", motivo: "Cambio sintético acordado", nueva_fecha_hora_cita: "2026-10-22T09:30:00-05:00" });
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(3));
    expect(screen.getByRole("button", { name: "Marcar como Reprogramada" })).toBeInTheDocument();
  });

  it("CONFIRMADA permite asociar solo una intervención de la misma cita", async () => {
    const conIntervencion = { ...detalle, intervenciones: [intervencion] };
    const nueva = { ...conIntervencion, estado_actual: "CONFIRMADA" };
    fetchSimulado.mockResolvedValueOnce(respuesta(conIntervencion)).mockResolvedValueOnce(respuesta(nueva)).mockResolvedValueOnce(respuesta(nueva)); montar();
    await abrirCambio();
    await userEvent.selectOptions(screen.getByLabelText("Intervención que obtuvo la confirmación (opcional)"), "17");
    expect(screen.queryByLabelText("Nueva fecha y hora de cita (Lima)")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Liberar cupo para reasignación")).not.toBeInTheDocument();
    await confirmar(); await screen.findByText("Estado actualizado a Confirmada.");
    expect(cuerpo()).toEqual({ estado_nuevo: "CONFIRMADA", motivo: null, id_intervencion: 17 });
  });

  it("CANCELADA futura permite liberar el cupo en la misma petición", async () => {
    const nueva = { ...detalle, estado_actual: "CANCELADA", cupo_liberado: cupo };
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockResolvedValueOnce(respuesta(nueva)).mockResolvedValueOnce(respuesta(nueva)); montar();
    await abrirCambio("Cancelada");
    await userEvent.click(screen.getByLabelText("Liberar cupo para reasignación")); await confirmar();
    expect(await screen.findByText("Estado actualizado a Cancelada.")).toBeInTheDocument();
    expect(cuerpo()).toEqual({ estado_nuevo: "CANCELADA", motivo: null, liberar_cupo: true });
    expect(screen.getByText("CANCELACION_EXTERNA")).toBeInTheDocument();
  });

  it("no ofrece liberar una cita pasada y no filtra campos de otro destino", async () => {
    const pasada = { ...detalle, fecha_hora_cita: "2026-10-19T10:00:00-05:00" };
    fetchSimulado.mockResolvedValueOnce(respuesta(pasada)).mockResolvedValueOnce(respuesta({ ...pasada, estado_actual: "CANCELADA" })).mockResolvedValueOnce(respuesta({ ...pasada, estado_actual: "CANCELADA" })); montar();
    await abrirCambio("Reprogramada"); fireEvent.change(screen.getByLabelText("Nueva fecha y hora de cita (Lima)"), { target: { value: "2026-10-22T09:30" } });
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancelar" }));
    await abrirCambio("Cancelada");
    expect(screen.queryByLabelText("Liberar cupo para reasignación")).not.toBeInTheDocument();
    await confirmar(); await screen.findByText("Estado actualizado a Cancelada.");
    expect(cuerpo()).toEqual({ estado_nuevo: "CANCELADA", motivo: null });
  });

  it.each([
    ["DESENLACE_ANTICIPADO", 409, /No se puede registrar el desenlace de una cita futura/],
    ["CHECK_IN_REGISTRADO", 409, /La cita tiene una llegada registrada/],
    ["TRANSICION_INVALIDA", 409, /La cita ya no admite ese cambio/],
    ["CITA_PASADA", 409, /No se puede liberar el cupo de una cita pasada/],
    ["SIN_PERMISO", 403, /Tu rol no tiene permiso/],
    ["NO_ENCONTRADO", 404, /No se encontró la cita/],
    ["VALIDACION", 422, /Detalle del servidor: VALIDACION/],
    ["FUERA_DE_PERIMETRO", 422, /Revisa el perímetro del piloto/],
  ] as const)("explica %s y refresca los conflictos", async (codigo, status, texto) => {
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockResolvedValueOnce(errorApi(codigo, status)).mockResolvedValue(respuesta(detalle)); montar();
    await abrirCambio(); await confirmar(); expect(await screen.findByText(texto)).toBeInTheDocument();
    expect(fetchSimulado).toHaveBeenCalledTimes(status === 409 ? 3 : 2);
    expect(screen.queryByText(/Estado actualizado a/)).not.toBeInTheDocument();
  });

  it("mantiene el diálogo abierto y evita envíos duplicados mientras guarda", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockImplementation(() => new Promise<Response>(() => undefined)); montar();
    await abrirCambio(); const formulario = screen.getByRole("dialog").querySelector("form")!;
    fireEvent.submit(formulario); fireEvent.submit(formulario);
    expect(screen.getByRole("button", { name: "Guardando…" })).toBeDisabled();
    expect(screen.getByLabelText("Motivo (opcional)")).toBeDisabled();
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-labelledby", "titulo-cambio");
    const cancelar = new Event("cancel", { cancelable: true }); screen.getByRole("dialog").dispatchEvent(cancelar);
    expect(cancelar.defaultPrevented).toBe(true); expect(fetchSimulado).toHaveBeenCalledTimes(2);
  });

  it.each(["ATENDIDA", "NO_SHOW"] as const)("presenta el desenlace final %s sin acciones", async (estado) => {
    fetchSimulado.mockResolvedValue(respuesta({ ...detalle, estado_actual: estado, target_no_show: estado === "ATENDIDA" ? 0 : 1 })); montar();
    expect(await screen.findByText("Estado final: no admite más cambios.")).toBeInTheDocument();
    expect(screen.getByText(estado === "ATENDIDA" ? "0 · Asistió" : "1 · No asistió")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Marcar como|Calcular riesgo|Registrar llegada/ })).not.toBeInTheDocument();
  });
});

describe("Llegada y validaciones de Lima (RF-104, RN01)", () => {
  it("envía observación opcional, informa operador y conserva el estado", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockResolvedValueOnce(respuesta({ fecha_hora_check_in: "2026-10-20T09:00:00-05:00", id_usuario: 12 }, 201)); montar();
    await userEvent.type(await screen.findByLabelText("Observación de llegada (opcional)"), " Llegada sintética ");
    await userEvent.click(screen.getByRole("button", { name: "Registrar llegada (check-in)" }));
    expect(await screen.findByText(/Llegada registrada \(check-in\)/)).toBeInTheDocument();
    expect(screen.getByText("Usuario #12")).toBeInTheDocument();
    expect(cuerpo()).toEqual({ observacion: "Llegada sintética" });
    expect(String(fetchSimulado.mock.calls[1][0])).toContain("/citas/324/check-in");
    expect(screen.getByRole("button", { name: "Marcar como Confirmada" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Registrar llegada (check-in)" })).not.toBeInTheDocument();
  });

  it("usa el día de Lima aunque el instante UTC ya sea el día siguiente", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-10-21T03:00:00Z").getTime());
    fetchSimulado.mockResolvedValue(respuesta(detalle)); montar();
    expect(await screen.findByRole("button", { name: "Registrar llegada (check-in)" })).toBeEnabled();
  });

  it("deshabilita check-in fuera del día de la cita con una explicación", async () => {
    fetchSimulado.mockResolvedValue(respuesta({ ...detalle, fecha_hora_cita: "2026-10-21T10:00:00-05:00" })); montar();
    expect(await screen.findByRole("button", { name: "Registrar llegada (check-in)" })).toBeDisabled();
    expect(screen.getByText(/El check-in solo se registra el día/)).toBeInTheDocument();
  });

  it.each([
    ["CHECK_IN_DUPLICADO", 409, /La llegada \(check-in\) ya fue registrada/],
    ["FUERA_DE_FECHA", 409, /El check-in solo se puede registrar el día/],
    ["ESTADO_FINAL", 409, /Esta cita tiene un estado final/],
    ["SIN_PERMISO", 403, /Tu rol no tiene permiso/],
    ["NO_ENCONTRADO", 404, /No se encontró la cita/],
  ] as const)("explica %s sin declarar un check-in exitoso", async (codigo, status, texto) => {
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockResolvedValueOnce(errorApi(codigo, status)).mockResolvedValue(respuesta(detalle)); montar();
    await userEvent.click(await screen.findByRole("button", { name: "Registrar llegada (check-in)" }));
    expect(await screen.findByText(texto)).toBeInTheDocument(); expect(cuerpo()).toEqual({ observacion: null });
    expect(fetchSimulado).toHaveBeenCalledTimes(status === 409 ? 3 : 2);
  });

  it("impide doble check-in y edición mientras espera", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockImplementation(() => new Promise<Response>(() => undefined)); montar();
    const observacion = await screen.findByLabelText("Observación de llegada (opcional)"); const formulario = observacion.closest("form")!;
    fireEvent.submit(formulario); fireEvent.submit(formulario);
    expect(screen.getByRole("button", { name: "Registrando llegada…" })).toBeDisabled(); expect(observacion).toBeDisabled();
    expect(fetchSimulado).toHaveBeenCalledTimes(2);
  });
});

describe("Inferencia local al detalle (RF-052, RF-056, RF-098, RF-099, RF-103, RN16)", () => {
  it.each([false, true])("muestra predicción nueva o existente (ya_existia=%s) sin duplicarla", async (yaExistia) => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ ...detalle, predicciones: yaExistia ? [prediccion] : [] })).mockResolvedValueOnce(respuesta({ ...prediccion, ya_existia: yaExistia }, yaExistia ? 200 : 201)); montar();
    await userEvent.click(await screen.findByRole("button", { name: "Calcular riesgo" }));
    expect(await screen.findByText(yaExistia ? /Se muestra la predicción existente/ : /Riesgo calculado/)).toBeInTheDocument();
    expect(screen.getAllByRole("article", { name: "Predicción #27" })).toHaveLength(1);
    expect(screen.getByText("Resultado simulado: no es desempeño real")).toBeInTheDocument();
    expect(fetchSimulado.mock.calls[1][1]?.method).toBe("POST");
    expect(String(fetchSimulado.mock.calls[1][0])).toContain("/citas/324/prediccion");
    expect(screen.getByRole("link", { name: "Crear intervención" })).toHaveAttribute("href", "/intervenciones?id_cita=324");
  });

  it.each([
    ["MOTOR_IA_NO_DISPONIBLE", 503, /Motor de IA no disponible/],
    ["CITA_NO_ELEGIBLE", 409, /Cita no elegible/],
    ["MODELO_NO_HABILITADO", 409, /Modelo no habilitado/],
    ["NO_ENCONTRADO", 404, /No se encontró la cita/],
  ] as const)("muestra %s sin modificar la cita", async (codigo, status, texto) => {
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockResolvedValueOnce(errorApi(codigo, status)); montar();
    await userEvent.click(await screen.findByRole("button", { name: "Calcular riesgo" }));
    expect(await screen.findByText(texto)).toBeInTheDocument();
    expect(screen.getByText("No hay predicciones registradas.")).toBeInTheDocument();
    expect(screen.queryByText(/Riesgo calculado/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Calcular riesgo" })).toBeEnabled();
  });

  it("conserva el último riesgo y la elegibilidad al recuperar una predicción existente anterior (RF-018, RF-057, RF-099)", async () => {
    const anterior = { ...prediccion, fecha_hora_inferencia: "2026-10-18T08:30:00-05:00" };
    const reciente = { ...prediccion, id_prediccion: 28, version_modelo: "SIMULADOR_v0.2.0", nivel_riesgo: "BAJO", probabilidad_no_show: 0.15 };
    fetchSimulado.mockResolvedValueOnce(respuesta({ ...detalle, predicciones: [reciente, anterior] }))
      .mockResolvedValueOnce(respuesta({ ...anterior, ya_existia: true })); montar();
    await userEvent.click(await screen.findByRole("button", { name: "Calcular riesgo" }));
    expect(await screen.findByText(/Se muestra la predicción existente/)).toBeInTheDocument();
    expect(screen.getAllByRole("article").map((articulo) => articulo.getAttribute("aria-label"))).toEqual(["Predicción #28", "Predicción #27"]);
    expect(screen.queryByRole("link", { name: "Crear intervención" })).not.toBeInTheDocument();
    expect(screen.getAllByText("Versión SIMULADOR_v0.1.0")).toHaveLength(1);
  });

  it("bloquea un cálculo duplicado y las otras escrituras mientras espera", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockImplementation(() => new Promise<Response>(() => undefined)); montar();
    await userEvent.dblClick(await screen.findByRole("button", { name: "Calcular riesgo" }));
    expect(screen.getByRole("button", { name: "Calculando riesgo…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Marcar como Confirmada" })).toBeDisabled(); expect(fetchSimulado).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["sin predicción", { predicciones: [] }, false],
    ["riesgo bajo", { predicciones: [{ ...prediccion, nivel_riesgo: "BAJO" }] }, false],
    ["riesgo medio", { predicciones: [{ ...prediccion, nivel_riesgo: "MEDIO" }] }, true],
    ["envío pendiente", { predicciones: [prediccion], intervenciones: [{ ...intervencion, estado_intervencion: "PENDIENTE" }] }, false],
    ["único reintento fallido", { predicciones: [prediccion], intervenciones: [{ ...intervencion, estado_intervencion: "FALLIDA" }] }, true],
    ["dos envíos fallidos", { predicciones: [prediccion], intervenciones: [{ ...intervencion, estado_intervencion: "FALLIDA" }, { ...intervencion, id_intervencion: 18, estado_intervencion: "FALLIDA" }] }, false],
    ["opt-out", { predicciones: [prediccion], intervenciones: [{ ...intervencion, estado_intervencion: "FALLIDA", consentimiento_optout: true }] }, false],
    ["cita pasada", { predicciones: [prediccion], fecha_hora_cita: "2026-10-19T10:00:00-05:00" }, false],
    ["estado final", { predicciones: [prediccion], estado_actual: "CANCELADA" }, false],
  ])("ofrece Crear intervención según %s (RF-057, RN07)", async (_caso, cambios, visible) => {
    fetchSimulado.mockResolvedValue(respuesta({ ...detalle, ...cambios })); montar();
    await screen.findByText(detalle.paciente_anon_id);
    if (visible) expect(screen.getByRole("link", { name: "Crear intervención" })).toBeInTheDocument();
    else expect(screen.queryByRole("link", { name: "Crear intervención" })).not.toBeInTheDocument();
  });

  describe("T-053 Observación 1: preselección de intervención desde ?id_intervencion=", () => {
    function montarConQuery(query = "") {
      return render(
        <MemoryRouter initialEntries={[`/citas/324${query}`]}>
          <Routes>
            <Route path="/citas/:id" element={<Detalle />} />
          </Routes>
        </MemoryRouter>,
      );
    }

    it("a) con ?id_intervencion= de una intervención de la cita: se ve el aviso y, al abrir «Cambiar estado» y elegir Confirmada, el selector tiene preseleccionado ese id", async () => {
      fetchSimulado.mockResolvedValueOnce(respuesta({ ...detalle, intervenciones: [intervencion] }));
      montarConQuery("?id_intervencion=17");
      expect(await screen.findByText('Vienes de la intervención #17. Para registrar la confirmación, usa "Cambiar estado" → Confirmada.')).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Marcar como Confirmada" }));
      const selector = screen.getByLabelText("Intervención que obtuvo la confirmación (opcional)") as HTMLSelectElement;
      expect(selector.value).toBe("17");
    });

    it("b) con un id que no pertenece a la cita: no hay aviso y el selector queda en «Sin intervención asociada»", async () => {
      fetchSimulado.mockResolvedValueOnce(respuesta({ ...detalle, intervenciones: [intervencion] }));
      montarConQuery("?id_intervencion=999");
      await screen.findByText(detalle.paciente_anon_id);
      expect(screen.queryByText(/Vienes de la intervención/)).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Marcar como Confirmada" }));
      const selector = screen.getByLabelText("Intervención que obtuvo la confirmación (opcional)") as HTMLSelectElement;
      expect(selector.value).toBe("");
    });

    it("c) con un valor no numérico (?id_intervencion=abc): no hay aviso", async () => {
      fetchSimulado.mockResolvedValueOnce(respuesta({ ...detalle, intervenciones: [intervencion] }));
      montarConQuery("?id_intervencion=abc");
      await screen.findByText(detalle.paciente_anon_id);
      expect(screen.queryByText(/Vienes de la intervención/)).not.toBeInTheDocument();
    });

    it("d) en los tres casos, fetch solo se llama para leer el detalle (ninguna escritura)", async () => {
      for (const query of ["?id_intervencion=17", "?id_intervencion=999", "?id_intervencion=abc"]) {
        fetchSimulado.mockReset();
        fetchSimulado.mockResolvedValueOnce(respuesta({ ...detalle, intervenciones: [intervencion] }));
        const { unmount } = montarConQuery(query);
        await screen.findByText(detalle.paciente_anon_id);
        expect(fetchSimulado).toHaveBeenCalledTimes(1);
        const [url, init] = fetchSimulado.mock.calls[0];
        expect(String(url)).toContain("/citas/324");
        expect(init?.method ?? "GET").toBe("GET");
        unmount();
      }
    });
  });
});

