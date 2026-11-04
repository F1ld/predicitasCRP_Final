import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, SESION_EXPIRADA, token } from "../../nucleo/api/cliente";
import { descargarRep03 } from "./exportar";

const fetchSimulado = vi.fn<typeof fetch>();
const crearObjeto = vi.fn<(objeto?: Blob | MediaSource) => string>(() => "blob:rep03-sintetico");
const revocarObjeto = vi.fn();
let descargar: ReturnType<typeof vi.spyOn>;
function respuesta(datos: unknown, status = 200) { return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } }); }
beforeEach(() => {
  sessionStorage.clear(); fetchSimulado.mockReset(); crearObjeto.mockClear(); revocarObjeto.mockClear();
  vi.stubGlobal("fetch", fetchSimulado);
  vi.stubGlobal("URL", class extends URL { static createObjectURL = crearObjeto; static revokeObjectURL = revocarObjeto; });
  descargar = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

// REP-03, RF-094 y RNF-004: descarga binaria remota con la misma política de sesión del núcleo.
describe("Descarga REP-03", () => {
  it("descarga exactamente el Blob recibido, usa nombre fijo y limpia recurso/enlace", async () => {
    let nombre = "";
    descargar.mockImplementation(function (this: HTMLAnchorElement) { nombre = this.download; });
    fetchSimulado.mockResolvedValueOnce(new Response("contenido;remoto", { status: 200, headers: { "Content-Disposition": 'attachment; filename="../../peligro.html"' } }));
    await expect(descargarRep03("csv", {})).resolves.toBe("rep-03_reasignaciones.csv");
    expect(nombre).toBe("rep-03_reasignaciones.csv");
    const blob = crearObjeto.mock.calls[0][0] as unknown as Blob;
    expect(await blob.text()).toBe("contenido;remoto");
    expect(document.querySelector('a[download]')).toBeNull();
    expect(revocarObjeto).toHaveBeenCalledWith("blob:rep03-sintetico");
    expect(fetchSimulado.mock.calls[0][1]?.headers).toEqual({});
  });

  it("revoca también cuando no se puede iniciar la descarga", async () => {
    descargar.mockImplementation(() => { throw new Error("Descarga bloqueada."); });
    fetchSimulado.mockResolvedValueOnce(new Response("contenido", { status: 200 }));
    await expect(descargarRep03("xlsx", {})).rejects.toThrow("Descarga bloqueada.");
    expect(revocarObjeto).toHaveBeenCalledOnce(); expect(document.querySelector("a[download]")).toBeNull();
  });

  it("convierte errores VALIDACION y conserva sus campos", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo: "VALIDACION", mensaje: "Revisa los filtros.", campos: { id_operador: "Debe ser entero." } } }, 422));
    await expect(descargarRep03("csv", {})).rejects.toMatchObject({ status: 422, codigo: "VALIDACION", campos: { id_operador: "Debe ser entero." } });
    expect(crearObjeto).not.toHaveBeenCalled();
  });

  it("expira la sesión actual ante 401 y anuncia el evento común", async () => {
    token.guardar("sesion-sintetica"); const evento = vi.fn(); window.addEventListener(SESION_EXPIRADA, evento);
    try {
      fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo: "SESION_INVALIDA", mensaje: "La sesión venció." } }, 401));
      await expect(descargarRep03("csv", {})).rejects.toBeInstanceOf(ApiError);
      expect(token.leer()).toBeNull(); expect(evento).toHaveBeenCalledOnce();
    } finally { window.removeEventListener(SESION_EXPIRADA, evento); }
  });

  it("un 401 tardío no borra una sesión posterior", async () => {
    token.guardar("sesion-anterior");
    fetchSimulado.mockImplementationOnce(() => {
      token.guardar("sesion-nueva");
      return Promise.resolve(respuesta({ error: { codigo: "SESION_INVALIDA", mensaje: "Sesión antigua." } }, 401));
    });
    await expect(descargarRep03("csv", {})).rejects.toMatchObject({ status: 401 });
    expect(token.leer()).toBe("sesion-nueva");
  });

  it("conserva sesión ante 403 y ante error no JSON", async () => {
    token.guardar("sesion-sintetica");
    fetchSimulado.mockResolvedValueOnce(new Response("<html>denegado</html>", { status: 403 }));
    await expect(descargarRep03("csv", {})).rejects.toMatchObject({ status: 403, codigo: "ERROR_DESCONOCIDO", mensaje: "No se pudo completar la solicitud." });
    expect(token.leer()).toBe("sesion-sintetica");
  });

  it("presenta error de conexión y propaga cancelación", async () => {
    fetchSimulado.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(descargarRep03("csv", {})).rejects.toMatchObject({ codigo: "ERROR_CONEXION" });
    fetchSimulado.mockRejectedValueOnce(new DOMException("cancelado", "AbortError"));
    await expect(descargarRep03("csv", {})).rejects.toMatchObject({ name: "AbortError" });
    expect(crearObjeto).not.toHaveBeenCalled();
  });

  it("no descarga una respuesta cancelada al cambiar filtros", async () => {
    const controlador = new AbortController();
    fetchSimulado.mockImplementationOnce(() => { controlador.abort(); return Promise.resolve(new Response("archivo", { status: 200 })); });
    await expect(descargarRep03("xlsx", {}, controlador.signal)).rejects.toMatchObject({ name: "AbortError" });
    expect(crearObjeto).not.toHaveBeenCalled();
  });
});
