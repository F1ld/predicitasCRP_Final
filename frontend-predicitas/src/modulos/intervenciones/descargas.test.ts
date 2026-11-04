import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, SESION_EXPIRADA, token } from "../../nucleo/api/cliente";
import { descargarReporte } from "./descargas";

const fetchSimulado = vi.fn<typeof fetch>();
const crearObjeto = vi.fn(() => "blob:rep-02-sintetico");
const revocarObjeto = vi.fn();

beforeEach(() => {
  sessionStorage.clear();
  fetchSimulado.mockReset();
  crearObjeto.mockClear();
  revocarObjeto.mockClear();
  vi.stubGlobal("fetch", fetchSimulado);
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: crearObjeto });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revocarObjeto });
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });

// REP-02, RNF-004, RNF-007: descarga servidor, credencial y errores del contrato común.
describe("Descargas auditadas REP-02", () => {
  it.each(["csv", "xlsx"] as const)("descarga %s desde el endpoint con formato, filtros y Bearer", async (formato) => {
    token.guardar("credencial-sintetica");
    fetchSimulado.mockResolvedValue(new Response("id_intervencion\n9", { headers: { "Content-Disposition": `attachment; filename="rep-02_2026-10-18.${formato}"`, "Content-Type": "text/csv" } }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.download).toBe(`rep-02_2026-10-18.${formato}`);
      expect(this.href).toBe("blob:rep-02-sintetico");
      expect(document.body).toContainElement(this);
    });
    await descargarReporte(new URLSearchParams({ desde: "2026-10-01", canal_contacto: "SMS", especialidad: "" }), formato);
    const [entrada, opciones] = fetchSimulado.mock.calls[0];
    const url = new URL(String(entrada));
    expect(url.pathname).toBe("/reportes/rep-02");
    expect(Object.fromEntries(url.searchParams)).toEqual({ desde: "2026-10-01", canal_contacto: "SMS", formato });
    expect(opciones).toEqual({ method: "GET", headers: { Authorization: "Bearer credencial-sintetica" } });
    expect(click).toHaveBeenCalledOnce();
    expect(crearObjeto).toHaveBeenCalledOnce();
    expect(revocarObjeto).toHaveBeenCalledWith("blob:rep-02-sintetico");
    expect(document.querySelector('a[download]')).toBeNull();
  });

  it("usa un nombre local cuando falta la cabecera y omite Bearer si no hay credencial", async () => {
    fetchSimulado.mockResolvedValue(new Response("archivo"));
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { expect(this.download).toBe("rep-02.xlsx"); });
    await descargarReporte(new URLSearchParams(), "xlsx");
    expect(fetchSimulado.mock.calls[0][1]?.headers).toEqual({});
  });

  it("elimina las rutas del nombre sugerido por el servidor", async () => {
    fetchSimulado.mockResolvedValue(new Response("archivo", { headers: { "Content-Disposition": 'attachment; filename="/carpeta/rep.csv"' } }));
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { expect(this.download).toBe("rep.csv"); });
    await descargarReporte(new URLSearchParams(), "csv");
  });

  it("libera el recurso temporal aunque falle el clic", async () => {
    fetchSimulado.mockResolvedValue(new Response("archivo"));
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => { throw new Error("No se pudo descargar"); });
    await expect(descargarReporte(new URLSearchParams(), "csv")).rejects.toThrow("No se pudo descargar");
    expect(revocarObjeto).toHaveBeenCalledWith("blob:rep-02-sintetico");
    expect(document.querySelector('a[download]')).toBeNull();
  });

  it("conserva el código, mensaje y errores por campo en 422 VALIDACION", async () => {
    fetchSimulado.mockResolvedValue(new Response(JSON.stringify({ error: { codigo: "VALIDACION", mensaje: "Revisa las fechas.", campos: { hasta: "Debe ser posterior a desde." } } }), { status: 422 }));
    await expect(descargarReporte(new URLSearchParams(), "csv")).rejects.toMatchObject({ status: 422, codigo: "VALIDACION", mensaje: "Revisa las fechas.", campos: { hasta: "Debe ser posterior a desde." } });
  });

  it.each([
    ["HTML sin JSON", "<html>Error</html>"],
    ["sin sobre error", JSON.stringify({ detail: "Fallo" })],
    ["con código de tipo inválido", JSON.stringify({ error: { codigo: 3, mensaje: "Fallo" } })],
    ["con campos de tipo inválido", JSON.stringify({ error: { codigo: "VALIDACION", mensaje: "Fallo", campos: { desde: 3 } } })],
    ["con campos como lista", JSON.stringify({ error: { codigo: "VALIDACION", mensaje: "Fallo", campos: [] } })],
  ])("usa el error genérico cuando llega %s", async (_nombre, cuerpo) => {
    fetchSimulado.mockResolvedValue(new Response(cuerpo, { status: 500 }));
    await expect(descargarReporte(new URLSearchParams(), "xlsx")).rejects.toMatchObject({ status: 500, codigo: "ERROR_DESCONOCIDO", mensaje: "No se pudo completar la solicitud.", campos: {} });
  });

  it.each([[401, "NO_AUTENTICADO"], [403, "SESION_INVALIDA"]] as const)("invalida la credencial vigente en %s %s", async (status, codigo) => {
    token.guardar("credencial-vencida");
    const aviso = vi.fn();
    window.addEventListener(SESION_EXPIRADA, aviso);
    fetchSimulado.mockResolvedValue(new Response(JSON.stringify({ error: { codigo, mensaje: "Sesión finalizada." } }), { status }));
    await expect(descargarReporte(new URLSearchParams(), "csv")).rejects.toBeInstanceOf(ApiError);
    expect(token.leer()).toBeNull();
    expect(aviso).toHaveBeenCalledOnce();
    window.removeEventListener(SESION_EXPIRADA, aviso);
  });

  it("una respuesta 401 anterior conserva una credencial nueva", async () => {
    token.guardar("credencial-anterior");
    fetchSimulado.mockImplementation(async () => {
      token.guardar("credencial-nueva");
      return new Response(JSON.stringify({ error: { codigo: "SESION_INVALIDA", mensaje: "Sesión antigua vencida." } }), { status: 401 });
    });
    await expect(descargarReporte(new URLSearchParams(), "csv")).rejects.toBeInstanceOf(ApiError);
    expect(token.leer()).toBe("credencial-nueva");
  });

  it("traduce los fallos de red y conserva las cancelaciones", async () => {
    fetchSimulado.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(descargarReporte(new URLSearchParams(), "csv")).rejects.toMatchObject({ status: 0, codigo: "ERROR_CONEXION" });
    const cancelacion = new DOMException("Cancelado", "AbortError");
    fetchSimulado.mockRejectedValueOnce(cancelacion);
    await expect(descargarReporte(new URLSearchParams(), "csv")).rejects.toBe(cancelacion);
  });
});
