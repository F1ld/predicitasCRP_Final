import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Rol } from "../../nucleo/api/tipos";
import Reporte from "./Reporte";
import type { Rep02Out } from "./tipos";

const permisos = vi.hoisted(() => ({ rol: "RECEPCION" as Rol }));
vi.mock("../../nucleo/auth/useAuth", () => ({ useAuth: () => ({ tieneRol: (...roles: Rol[]) => roles.includes(permisos.rol) }) }));
const fetchSimulado = vi.fn<typeof fetch>();

const reporte: Rep02Out = {
  resumen: { enviadas: 12, entregadas: 10, respondidas: 6, confirmaciones: 3, liberaciones: 1, tasa_respuesta: 0.5 },
  por_canal: [
    { canal_contacto: "WHATSAPP", respuesta_paciente: "CONFIRMA", cantidad: 3 },
    { canal_contacto: "WHATSAPP", respuesta_paciente: "SOLICITA_LIBERACION", cantidad: 1 },
    { canal_contacto: "SMS", respuesta_paciente: "CONFIRMA", cantidad: 1 },
    { canal_contacto: "LLAMADA_TELEFONICA", respuesta_paciente: null, cantidad: 2 },
  ],
  filas: [
    { id_intervencion: 7, id_cita_externa: "CIT-SIM-007", especialidad: "CARDIOLOGIA", nivel_riesgo: "ALTO", canal_contacto: "WHATSAPP", estado_intervencion: "RESPONDIDA", respuesta_paciente: "CONFIRMA", tiempo_respuesta_minutos: 0, cupo_liberado: false },
    { id_intervencion: 8, id_cita_externa: "CIT-SIM-008", especialidad: "PEDIATRIA", nivel_riesgo: null, canal_contacto: "SMS", estado_intervencion: "ENVIADA", respuesta_paciente: null, tiempo_respuesta_minutos: null, cupo_liberado: true },
  ],
  resultado_simulado: true,
};
function respuesta(datos: unknown, status = 200) { return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } }); }
function Ubicacion() { const lugar = useLocation(); return <output aria-label="URL actual">{lugar.pathname}{lugar.search}</output>; }
function montar(ruta = "/reportes/intervenciones") { return render(<MemoryRouter initialEntries={[ruta]}><Ubicacion /><Reporte /></MemoryRouter>); }
function ultimaConsulta() { return new URL(String(fetchSimulado.mock.calls.at(-1)?.[0])); }
beforeEach(() => {
  permisos.rol = "RECEPCION";
  fetchSimulado.mockReset();
  fetchSimulado.mockImplementation(() => Promise.resolve(respuesta(reporte)));
  vi.stubGlobal("fetch", fetchSimulado);
  sessionStorage.clear();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });

// REP-02, RF-003, RF-056, RN16, RNF-007 y RNF-016: M05-V04 con datos sintéticos del contrato.
describe("Reporte de intervenciones M05-V04", () => {
  it("anuncia la carga y deshabilita los filtros mientras espera", () => {
    fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined));
    montar();
    expect(screen.getByText("Cargando reporte…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeDisabled();
  });

  it("muestra indicadores, barras accesibles y filas con ausencia de riesgo o respuesta", async () => {
    montar();
    await screen.findByText("CIT-SIM-007");
    expect(screen.getByText("Resultado simulado: no es desempeño real")).toBeInTheDocument();
    expect(screen.getByLabelText("Indicadores de intervenciones")).toHaveTextContent("50 %");
    const canales = within(screen.getByRole("region", { name: "Intervenciones por canal" }));
    expect(canales.getByText("WhatsApp").parentElement).toHaveTextContent("4");
    const respuestas = within(screen.getByRole("region", { name: "Intervenciones por respuesta" }));
    expect(respuestas.getByText("Confirma").parentElement).toHaveTextContent("4");
    expect(respuestas.getByText("Sin respuesta registrada").parentElement).toHaveTextContent("2");
    const tabla = within(screen.getByRole("table"));
    expect(tabla.getByText("0 min")).toBeInTheDocument();
    expect(tabla.getByText("Sin predicción")).toBeInTheDocument();
    expect(tabla.getByText("Sí")).toBeInTheDocument();
    expect(tabla.getByText("No")).toBeInTheDocument();
    expect(tabla.getByRole("link", { name: "#7" })).toHaveAttribute("href", "/intervenciones/7");
    expect(screen.getByRole("link", { name: "Ver intervenciones" })).toHaveAttribute("href", "/intervenciones");
  });

  it("omite el rótulo en métricas reales y explica distribuciones sin registros", async () => {
    fetchSimulado.mockResolvedValue(respuesta({ ...reporte, resultado_simulado: false, por_canal: [] }));
    montar();
    await screen.findByText("CIT-SIM-007");
    expect(screen.queryByText("Resultado simulado: no es desempeño real")).not.toBeInTheDocument();
    expect(screen.getAllByText("Sin registros para esta distribución.")).toHaveLength(2);
  });

  it.each([null, { ...reporte, filas: [] }])("presenta el estado vacío sin permitir archivos o impresión", async (datos) => {
    fetchSimulado.mockResolvedValue(respuesta(datos));
    montar();
    expect(await screen.findByText("No hay intervenciones con esos filtros.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exportar CSV" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Exportar Excel" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Imprimir / Guardar PDF" })).toBeDisabled();
  });

  it.each([[422, "VALIDACION", "El rango de fechas no es válido."], [403, "SIN_PERMISO", "No tienes acceso a este reporte."]] as const)("muestra el error %s %s y permite reintentar", async (status, codigo, mensaje) => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo, mensaje } }, status));
    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent(mensaje);
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("CIT-SIM-007")).toBeInTheDocument();
  });

  it("recupera filtros de la URL y envía solo los nombres del contrato", async () => {
    const filtros = { desde: "2026-10-01", hasta: "2026-10-30", canal_contacto: "WHATSAPP", nivel_riesgo: "ALTO", especialidad: "CARDIOLOGIA" };
    montar(`/reportes/intervenciones?${new URLSearchParams({ ...filtros, parametro_desconocido: "omitido" })}`);
    await screen.findByText("CIT-SIM-007");
    expect(ultimaConsulta().pathname).toBe("/reportes/rep-02");
    expect(Object.fromEntries(ultimaConsulta().searchParams)).toEqual(filtros);
    expect(screen.getByLabelText("Canal de contacto")).toHaveValue("WHATSAPP");
    expect(screen.getByLabelText("Nivel de riesgo")).toHaveValue("ALTO");
  });

  it("combina filtros, conserva la URL y limpia un borrador y los filtros aplicados", async () => {
    montar();
    await screen.findByText("CIT-SIM-007");
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-10-30" } });
    await userEvent.selectOptions(screen.getByLabelText("Canal de contacto"), "SMS");
    await userEvent.selectOptions(screen.getByLabelText("Nivel de riesgo"), "MEDIO");
    await userEvent.selectOptions(screen.getByLabelText("Especialidad"), "PEDIATRIA");
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(2));
    expect(Object.fromEntries(ultimaConsulta().searchParams)).toEqual({ desde: "2026-10-01", hasta: "2026-10-30", canal_contacto: "SMS", nivel_riesgo: "MEDIO", especialidad: "PEDIATRIA" });
    await screen.findByText("CIT-SIM-007");
    expect(screen.getByLabelText("URL actual")).toHaveTextContent("canal_contacto=SMS");
    await userEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(3));
    expect(ultimaConsulta().search).toBe("");
    expect(screen.getByLabelText("Canal de contacto")).toHaveValue("");
    await screen.findByText("CIT-SIM-007");
    await userEvent.selectOptions(screen.getByLabelText("Especialidad"), "TRAUMATOLOGIA");
    await userEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    expect(screen.getByLabelText("Especialidad")).toHaveValue("");
    expect(fetchSimulado).toHaveBeenCalledTimes(3);
  });

  it("impide consultar un rango de fechas invertido", async () => {
    montar();
    await screen.findByText("CIT-SIM-007");
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-10-30" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-10-01" } });
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    expect(screen.getByRole("alert")).toHaveTextContent("La fecha inicial no puede ser posterior a la fecha final.");
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
  });

  it.each(["CSV", "Excel"])("exporta %s del servidor con filtros aplicados y credencial", async (etiqueta) => {
    sessionStorage.setItem("predicitas_token", "credencial-reporte");
    const crear = vi.fn(() => "blob:archivo");
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: crear });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    fetchSimulado.mockImplementation((entrada) => Promise.resolve(new URL(String(entrada)).searchParams.has("formato") ? new Response("archivo-servidor") : respuesta(reporte)));
    montar("/reportes/intervenciones?desde=2026-10-01&canal_contacto=WHATSAPP");
    await screen.findByText("CIT-SIM-007");
    await userEvent.click(screen.getByRole("button", { name: `Exportar ${etiqueta}` }));
    await waitFor(() => expect(crear).toHaveBeenCalledOnce());
    expect(Object.fromEntries(ultimaConsulta().searchParams)).toEqual({ desde: "2026-10-01", canal_contacto: "WHATSAPP", formato: etiqueta === "CSV" ? "csv" : "xlsx" });
    expect(fetchSimulado.mock.calls.at(-1)?.[1]?.headers).toEqual({ Authorization: "Bearer credencial-reporte" });
  });

  it("indica descarga en curso y evita acciones simultáneas", async () => {
    fetchSimulado.mockImplementation((entrada) => new URL(String(entrada)).searchParams.has("formato") ? new Promise<Response>(() => undefined) : Promise.resolve(respuesta(reporte)));
    montar();
    await screen.findByText("CIT-SIM-007");
    await userEvent.click(screen.getByRole("button", { name: "Exportar CSV" }));
    expect(screen.getByRole("button", { name: "Descargando CSV…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Exportar Excel" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeDisabled();
  });

  it.each([
    ["FORMATO_NO_DISPONIBLE", "El formato solicitado no está disponible.", undefined],
    ["VALIDACION", "Revisa los filtros para exportar.", { desde: "Fecha fuera de rango." }],
  ])("explica el error de exportación %s sin ocultar datos", async (codigo, mensaje, campos) => {
    fetchSimulado.mockImplementation((entrada) => Promise.resolve(new URL(String(entrada)).searchParams.has("formato") ? respuesta({ error: { codigo, mensaje, campos } }, 422) : respuesta(reporte)));
    montar();
    await screen.findByText("CIT-SIM-007");
    await userEvent.click(screen.getByRole("button", { name: "Exportar Excel" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(mensaje);
    if (campos) expect(screen.getByRole("alert")).toHaveTextContent("desde: Fecha fuera de rango.");
    expect(screen.getByText("CIT-SIM-007")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exportar Excel" })).toBeEnabled();
  });

  it("muestra error genérico cuando falla la descarga sin respuesta estructurada", async () => {
    fetchSimulado.mockImplementation((entrada) => new URL(String(entrada)).searchParams.has("formato") ? Promise.reject(new Error("Fallo de red")) : Promise.resolve(respuesta(reporte)));
    montar();
    await screen.findByText("CIT-SIM-007");
    await userEvent.click(screen.getByRole("button", { name: "Exportar CSV" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar con el servidor. Comprueba que el backend está encendido.");
  });

  it("invoca la impresión del navegador para guardar PDF", async () => {
    const imprimir = vi.spyOn(window, "print").mockImplementation(() => undefined);
    montar();
    await screen.findByText("CIT-SIM-007");
    await userEvent.click(screen.getByRole("button", { name: "Imprimir / Guardar PDF" }));
    expect(imprimir).toHaveBeenCalledOnce();
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
  });

  it("impide cualquier consulta y exportación para TECNICO_IA", () => {
    permisos.rol = "TECNICO_IA";
    montar();
    expect(screen.getByRole("alert")).toHaveTextContent("No tienes permiso para consultar el reporte de intervenciones.");
    expect(fetchSimulado).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Exportar CSV" })).not.toBeInTheDocument();
  });

  it("permite el reporte al administrador", async () => {
    permisos.rol = "ADMINISTRADOR";
    montar();
    expect(await screen.findByText("CIT-SIM-007")).toBeInTheDocument();
  });
});
