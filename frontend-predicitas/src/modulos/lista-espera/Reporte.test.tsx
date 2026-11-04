import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Rol } from "../../nucleo/api/tipos";
import Reporte from "./Reporte";
import type { Rep03Out } from "./tipos";

const permisos = vi.hoisted(() => ({ rol: "RECEPCION" as Rol }));
vi.mock("../../nucleo/auth/useAuth", () => ({ useAuth: () => ({ tieneRol: (...roles: Rol[]) => roles.includes(permisos.rol) }) }));
const fetchSimulado = vi.fn<typeof fetch>();
const crearObjeto = vi.fn(() => "blob:rep03-sintetico");
const revocarObjeto = vi.fn();
const imprimir = vi.fn();
let clicDescarga: ReturnType<typeof vi.spyOn>;

// REP-03, RF-094, RNF-007: forma exacta M06-E10 y datos exclusivamente sintéticos.
const reporte: Rep03Out = {
  resumen: { cupos_liberados: 4, cupos_reasignados: 1, tasa_recuperacion: 0.25, horas_promedio_matching: 1.75 },
  por_especialidad: [{ especialidad: "CARDIOLOGIA", liberados: 4, reasignados: 1 }],
  filas: [
    { id_cupo_liberado: 51, fecha_hora_cupo: "2026-10-23T14:00:00Z", especialidad: "CARDIOLOGIA", medico: "Profesional sintético 1", horas_disponible: 1.75, paciente_anon_id_asignado: "PAC-SIM-0088", id_operador_confirma: 9, estado_cupo: "REASIGNADO" },
    { id_cupo_liberado: 52, fecha_hora_cupo: "2026-10-24T14:00:00Z", especialidad: "CARDIOLOGIA", medico: "Profesional sintético 2", horas_disponible: 0, paciente_anon_id_asignado: null, id_operador_confirma: null, estado_cupo: "DISPONIBLE" },
  ],
};
function respuesta(datos: unknown, status = 200) { return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } }); }
function Ubicacion() { return <output aria-label="URL vigente">{useLocation().search}</output>; }
function montar(ruta = "/reportes/reasignaciones") { return render(<MemoryRouter initialEntries={[ruta]}><Reporte /><Ubicacion /></MemoryRouter>); }
async function cargar(ruta?: string) { fetchSimulado.mockResolvedValueOnce(respuesta(reporte)); montar(ruta); await screen.findByText("Profesional sintético 1"); }
beforeEach(() => {
  permisos.rol = "RECEPCION"; fetchSimulado.mockReset(); sessionStorage.clear();
  crearObjeto.mockClear(); revocarObjeto.mockClear(); imprimir.mockClear();
  vi.stubGlobal("fetch", fetchSimulado);
  vi.stubGlobal("URL", class extends URL { static createObjectURL = crearObjeto; static revokeObjectURL = revocarObjeto; });
  clicDescarga = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  vi.spyOn(window, "print").mockImplementation(imprimir);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("REP-03: consulta, filtros y presentación (RF-094, RNF-016)", () => {
  it("anuncia carga sin mostrar datos anteriores", () => {
    fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined)); montar();
    expect(screen.getByText("Cargando reporte de reasignaciones…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Exportar CSV" })).not.toBeInTheDocument();
  });

  it("muestra resumen, porcentaje, horas, avance accesible y todas las columnas", async () => {
    await cargar();
    expect(screen.getByText(/^25\s?%$/)).toBeInTheDocument();
    expect(screen.getAllByText("1.75 h")).toHaveLength(2);
    expect(screen.getByRole("progressbar", { name: "Recuperación en Cardiología" })).toHaveAttribute("value", "1");
    expect(screen.getByRole("progressbar")).toHaveAttribute("max", "4");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuetext", "1 de 4 cupos reasignados");
    const tabla = screen.getByRole("table");
    expect(within(tabla).getAllByRole("columnheader")).toHaveLength(8);
    expect(within(tabla).getByText("PAC-SIM-0088")).toBeInTheDocument();
    expect(within(tabla).getByText("Sin asignar")).toBeInTheDocument();
    expect(within(tabla).getByText("Sin confirmación")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cupo 51" })).toHaveAttribute("href", "/cupos/51");
    expect(within(tabla).getAllByText(/9:00/)).toHaveLength(2);
    expect(new URL(String(fetchSimulado.mock.calls[0][0])).searchParams.get("formato")).toBe("json");
  });

  it("distingue null de cero en horas y mantiene 0 %", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ ...reporte, resumen: { ...reporte.resumen, tasa_recuperacion: 0, horas_promedio_matching: null }, por_especialidad: [{ especialidad: "PEDIATRIA", liberados: 0, reasignados: 0 }] }));
    montar(); await screen.findByText("Sin reasignaciones");
    expect(screen.getByText(/^0\s?%$/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("max", "1");
    cleanup();
    fetchSimulado.mockResolvedValueOnce(respuesta({ ...reporte, resumen: { ...reporte.resumen, horas_promedio_matching: 0 } }));
    montar(); await screen.findByText("Profesional sintético 1");
    expect(screen.queryByText("Sin reasignaciones")).not.toBeInTheDocument();
    expect(screen.getAllByText("0 h")).toHaveLength(2);
  });

  it("presenta vacío con ayuda para ampliar y sin inventar filas", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ resumen: { cupos_liberados: 0, cupos_reasignados: 0, tasa_recuperacion: 0, horas_promedio_matching: null }, por_especialidad: [], filas: [] }));
    montar();
    expect(await screen.findByText("No hay cupos en el reporte con esos filtros.")).toBeInTheDocument();
    expect(screen.getByText("Sin cupos por especialidad en este periodo.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("muestra error de contrato y reintenta", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo: "ERROR_INTERNO", mensaje: "Reporte temporalmente no disponible." } }, 500)).mockResolvedValueOnce(respuesta(reporte));
    montar(); expect(await screen.findByText("Reporte temporalmente no disponible.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Profesional sintético 1")).toBeInTheDocument();
  });

  it("aplica todos los filtros a URL/API y limpia la consulta", async () => {
    await cargar(); fetchSimulado.mockResolvedValue(respuesta(reporte));
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-10-31" } });
    await userEvent.selectOptions(screen.getByLabelText("Especialidad"), "CARDIOLOGIA");
    await userEvent.type(screen.getByLabelText("ID del operador"), "9");
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(2));
    const consulta = new URL(String(fetchSimulado.mock.calls[1][0])).searchParams;
    expect(Object.fromEntries(consulta)).toEqual({ formato: "json", desde: "2026-10-01", hasta: "2026-10-31", especialidad: "CARDIOLOGIA", id_operador: "9" });
    expect(screen.getByLabelText("URL vigente")).toHaveTextContent("id_operador=9");
    await userEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(3));
    expect(screen.getByLabelText("URL vigente")).toHaveTextContent("");
    expect(new URL(String(fetchSimulado.mock.calls[2][0])).search).toBe("?formato=json");
  });

  it.each(["0", "-1", "1.5", "abc", "9007199254740992"])("no consulta operador inválido %s desde URL", (id) => {
    montar(`/reportes/reasignaciones?id_operador=${id}`);
    expect(screen.getByText("El ID del operador debe ser un número entero mayor que 0.")).toBeInTheDocument();
    expect(fetchSimulado).not.toHaveBeenCalled();
  });

  it("rechaza rango invertido sin alterar filtros aplicados ni consultar", async () => {
    await cargar();
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-10-31" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-10-01" } });
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    expect(screen.getByText("La fecha inicial no puede ser posterior a la fecha final.")).toBeInTheDocument();
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
  });

  it.each(["desde=2026-02-30", "hasta=invalida", "especialidad=OTRA", "desde=2026-10-31&hasta=2026-10-01"])("bloquea filtros URL inválidos: %s", (consulta) => {
    montar(`/reportes/reasignaciones?${consulta}`);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(fetchSimulado).not.toHaveBeenCalled();
  });

  it.each(["ADMINISTRADOR", "RECEPCION"] as const)("permite consultar a %s", async (rol) => {
    permisos.rol = rol; await cargar(); expect(fetchSimulado).toHaveBeenCalledTimes(1);
  });

  it("no muestra el módulo ni consulta para TECNICO_IA", () => {
    permisos.rol = "TECNICO_IA"; montar();
    expect(screen.getByText(/Tu rol no tiene permiso/)).toBeInTheDocument();
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(fetchSimulado).not.toHaveBeenCalled();
  });
});

describe("Exportación remota e impresión REP-03 (RF-094)", () => {
  it.each([["CSV", "csv"], ["Excel", "xlsx"]] as const)("descarga %s autenticado con los mismos filtros", async (nombre, formato) => {
    sessionStorage.setItem("predicitas_token", "credencial-sintetica");
    await cargar("/reportes/reasignaciones?desde=2026-10-01&hasta=2026-10-31&especialidad=CARDIOLOGIA&id_operador=9");
    fetchSimulado.mockResolvedValueOnce(new Response("archivo del servidor", { status: 200 }));
    await userEvent.click(screen.getByRole("button", { name: `Exportar ${nombre}` }));
    expect(await screen.findByText(`Descarga preparada: rep-03_reasignaciones.${formato}`)).toBeInTheDocument();
    const [url, opciones] = fetchSimulado.mock.calls[1];
    expect(Object.fromEntries(new URL(String(url)).searchParams)).toEqual({ desde: "2026-10-01", hasta: "2026-10-31", especialidad: "CARDIOLOGIA", id_operador: "9", formato });
    expect(opciones?.headers).toEqual({ Authorization: "Bearer credencial-sintetica" });
    expect(crearObjeto).toHaveBeenCalledOnce(); expect(revocarObjeto).toHaveBeenCalledWith("blob:rep03-sintetico");
    expect(clicDescarga).toHaveBeenCalledOnce();
  });

  it("bloquea descargas simultáneas mientras espera", async () => {
    await cargar(); fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined));
    await userEvent.click(screen.getByRole("button", { name: "Exportar CSV" }));
    expect(screen.getByRole("button", { name: "Exportando CSV…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Exportar Excel" })).toBeDisabled();
    expect(screen.getByText("Preparando la exportación…")).toBeInTheDocument();
    expect(fetchSimulado).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["FORMATO_NO_DISPONIBLE", "Formato ausente.", "El formato de exportación no está disponible. Prueba otro formato."],
    ["VALIDACION", "Revisa el periodo del reporte.", "Revisa el periodo del reporte."],
  ])("presenta %s sin descargar archivo", async (codigo, mensaje, visible) => {
    await cargar(); fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo, mensaje, campos: codigo === "VALIDACION" ? { desde: "Fecha no válida" } : undefined } }, 422));
    await userEvent.click(screen.getByRole("button", { name: "Exportar Excel" }));
    expect(await screen.findByText(visible)).toBeInTheDocument();
    expect(crearObjeto).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Exportar Excel" })).toBeEnabled();
  });

  it("imprime el reporte sin consultar un endpoint PDF", async () => {
    await cargar(); await userEvent.click(screen.getByRole("button", { name: "Imprimir" }));
    expect(imprimir).toHaveBeenCalledOnce(); expect(fetchSimulado).toHaveBeenCalledTimes(1);
  });
});
