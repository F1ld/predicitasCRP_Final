import { describe, expect, it, vi } from "vitest";
import { api, ApiError, SESION_EXPIRADA, token } from "./cliente";

// D-017, RNF-004: contrato de errores, credenciales y respuestas sin cuerpo.
describe("cliente API tipado", () => {
  it("preserva codigo, mensaje y campos del contrato", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { codigo: "VALIDACION", mensaje: "Revisa los campos.", campos: { "filas.3.sede": "Fuera de perímetro" } } }), { status: 422 })));
    await expect(api("/citas")).rejects.toMatchObject({ name: "ApiError", status: 422, codigo: "VALIDACION", mensaje: "Revisa los campos.", message: "Revisa los campos.", campos: { "filas.3.sede": "Fuera de perímetro" } });
  });
  it.each(["<html>Error</html>", JSON.stringify({ detalle: "Formato viejo" }), JSON.stringify({ error: { codigo: "VALIDACION", mensaje: "No", campos: { campo: 1 } } }), JSON.stringify({ error: null })])("usa el mensaje genérico para un formato ajeno: %s", async (cuerpo) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(cuerpo, { status: 500 })));
    await expect(api("/citas")).rejects.toMatchObject({ status: 500, mensaje: "No se pudo completar la solicitud.", campos: {} });
  });
  it.each([401, 409])("invalida la sesión por status/codigo (%s)", async (status) => {
    token.guardar("sintetico");
    const listener = vi.fn();
    window.addEventListener(SESION_EXPIRADA, listener, { once: true });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { codigo: "SESION_INVALIDA", mensaje: "Sesión vencida" } }), { status })));
    await expect(api("/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(token.leer()).toBeNull();
    expect(listener).toHaveBeenCalledOnce();
  });
  it("un login rechazado no emite sesión expirada", async () => {
    const listener = vi.fn();
    window.addEventListener(SESION_EXPIRADA, listener);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 401 })));
    await expect(api("/auth/login")).rejects.toBeInstanceOf(ApiError);
    expect(listener).not.toHaveBeenCalled();
    window.removeEventListener(SESION_EXPIRADA, listener);
  });
  it("un 401 atrasado no elimina una credencial nueva", async () => {
    token.guardar("anterior");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => { token.guardar("nueva"); return new Response("{}", { status: 401 }); }));
    await expect(api("/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(token.leer()).toBe("nueva");
  });
  it("devuelve null para 204 sin intentar leer JSON", async () => {
    const respuesta = new Response(null, { status: 204 });
    const json = vi.spyOn(respuesta, "json");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuesta));
    expect(await api<null>("/auth/logout", { metodo: "POST" })).toBeNull();
    expect(json).not.toHaveBeenCalled();
  });
  it("envía parámetros definidos, bearer y JSON", async () => {
    token.guardar("sintetico");
    const fetch = vi.fn().mockResolvedValue(new Response("{\"ok\":true}"));
    vi.stubGlobal("fetch", fetch);
    expect(await api<{ ok: boolean }>("/citas", { metodo: "POST", params: { q: "abc", limite: 50, activo: false, vacio: "", nulo: null, omitido: undefined }, json: { estado_nuevo: "CONFIRMADA" } })).toEqual({ ok: true });
    const [url, opciones] = fetch.mock.calls[0] as [URL, RequestInit];
    expect(url.search).toBe("?q=abc&limite=50&activo=false");
    expect(opciones.headers).toEqual({ Authorization: "Bearer sintetico", "Content-Type": "application/json" });
    expect(opciones.body).toBe('{"estado_nuevo":"CONFIRMADA"}');
  });
  it("envía login urlencoded y archivos sin fijar boundary", async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    await api("/auth/login", { metodo: "POST", form: { username: "demo", password: "sintetica" } });
    const opcionesLogin = fetch.mock.calls[0][1] as RequestInit;
    expect(opcionesLogin.body?.toString()).toBe("username=demo&password=sintetica");
    const archivo = new FormData();
    archivo.append("archivo", new File(["csv"], "sintetico.csv"));
    await api("/citas/importar", { metodo: "POST", archivo });
    const opcionesArchivo = fetch.mock.calls[1][1] as RequestInit;
    expect(opcionesArchivo.body).toBe(archivo);
    expect(opcionesArchivo.headers).toEqual({});
  });
  it("distingue red caída de cancelación", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api("/citas")).rejects.toMatchObject({ status: 0, codigo: "ERROR_CONEXION" });
    const cancelado = new DOMException("Cancelado", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(cancelado));
    await expect(api("/citas")).rejects.toBe(cancelado);
  });
});
