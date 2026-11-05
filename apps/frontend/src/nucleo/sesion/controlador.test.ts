import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SESION_EXPIRADA, token } from "../api/cliente";
import type { TokenOut } from "../api/tipos";
import { iniciarGestorSesion, leerJwt } from "./controlador";
import { guardarTokenRenovado, leerMotivoSesion, limpiarMotivoSesion, MENSAJE_INACTIVIDAD, renovacionSuspendida, suspenderRenovacion } from "./credenciales";

const MINUTO = 60_000;
const BASE = Date.parse("2026-10-18T15:00:00Z");
function jwt(usuario = 7, emitido = BASE, minutos = 30) {
  return `cabecera.${btoa(JSON.stringify({ sub: String(usuario), iat: emitido / 1000, exp: (emitido + minutos * MINUTO) / 1000 }))}.firma`;
}
function datosToken(credencial: string): TokenOut {
  return { access_token: credencial, token_type: "bearer", expires_in: 1800 };
}
function respuesta(datos: unknown, estado = 200) {
  return new Response(estado === 204 ? null : JSON.stringify(datos), { status: estado, headers: { "Content-Type": "application/json" } });
}

class CanalFalso {
  static canales: CanalFalso[] = [];
  readonly mensajes: unknown[] = [];
  readonly oyentes = new Set<(evento: MessageEvent<unknown>) => void>();
  cerrado = false;
  constructor(readonly name: string) { CanalFalso.canales.push(this); }
  postMessage(datos: unknown) {
    this.mensajes.push(datos);
    CanalFalso.canales.filter((canal) => canal !== this && canal.name === this.name && !canal.cerrado)
      .forEach((canal) => canal.recibir(datos));
  }
  recibir(datos: unknown) {
    const mensaje = typeof datos === "object" && datos !== null ? { emitidoEn: Date.now(), ...datos } : datos;
    this.oyentes.forEach((oyente) => oyente(new MessageEvent("message", { data: mensaje })));
  }
  addEventListener(_tipo: string, oyente: (evento: MessageEvent<unknown>) => void) { this.oyentes.add(oyente); }
  removeEventListener(_tipo: string, oyente: (evento: MessageEvent<unknown>) => void) { this.oyentes.delete(oyente); }
  close() { this.cerrado = true; }
}

// RF-002, RF-090, RNF-004, D-010: reloj y API sintéticos, sin esperas reales ni JWT guardados fuera de sessionStorage.
describe("Gestión de sesión por actividad", () => {
  const fetchMock = vi.fn<typeof fetch>();
  const alCerrar = vi.fn();
  let limpiar: (() => void) | undefined;
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(BASE);
    sessionStorage.clear();
    fetchMock.mockReset();
    alCerrar.mockReset();
    CanalFalso.canales = [];
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("BroadcastChannel", CanalFalso);
  });
  afterEach(() => { limpiar?.(); limpiar = undefined; vi.useRealTimers(); });
  function iniciar(credencial = jwt()) {
    token.guardar(credencial);
    limpiar = iniciarGestorSesion(7, alCerrar);
  }
  const actividad = () => window.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));

  it("no hace solicitudes ni escucha actividad sin una sesión", async () => {
    limpiar = iniciarGestorSesion(7, alCerrar);
    actividad();
    await vi.advanceTimersByTimeAsync(31 * MINUTO);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(CanalFalso.canales).toHaveLength(0);
  });

  it("renueva únicamente con actividad cuando faltan menos de cinco minutos", async () => {
    iniciar();
    fetchMock.mockResolvedValue(respuesta(datosToken(jwt(7, BASE + 26 * MINUTO))));
    await vi.advanceTimersByTimeAsync(25 * MINUTO);
    actividad();
    expect(fetchMock).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(MINUTO);
    actividad();
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/auth/renovar");
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("POST");
    expect(token.leer()).toBe(jwt(7, BASE + 26 * MINUTO));
  });

  it.each(["mousedown", "mousemove", "pointerdown", "touchstart"])("considera %s actividad sin renovar anticipadamente", async (tipo) => {
    iniciar();
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    fetchMock.mockResolvedValue(respuesta(datosToken(jwt(7, BASE + 26 * MINUTO))));
    window.dispatchEvent(new Event(tipo));
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("no renueva por tiempo ni por abrir la pestaña; audita logout al cumplir 30 minutos inactivo", async () => {
    iniciar();
    fetchMock.mockResolvedValue(respuesta(null, 204));
    await vi.advanceTimersByTimeAsync(30 * MINUTO - 1);
    expect(fetchMock).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/auth/logout");
    expect(fetchMock.mock.calls[0]?.[1]?.headers).toEqual({ Authorization: `Bearer ${jwt()}` });
    expect(token.leer()).toBeNull();
    expect(alCerrar).toHaveBeenCalledTimes(1);
    expect(leerMotivoSesion()).toBe(MENSAJE_INACTIVIDAD);
    expect(leerMotivoSesion()).toBe(MENSAJE_INACTIVIDAD);
    limpiarMotivoSesion();
    expect(leerMotivoSesion()).toBe("");
  });

  it("no espera la respuesta de logout para borrar el token y volver al login", async () => {
    iniciar();
    fetchMock.mockImplementation(() => new Promise(() => undefined));
    await vi.advanceTimersByTimeAsync(30 * MINUTO);
    expect(token.leer()).toBeNull();
    expect(alCerrar).toHaveBeenCalledOnce();
  });

  it("cierra localmente aunque logout falle por red", async () => {
    iniciar();
    fetchMock.mockRejectedValue(new TypeError("Sin conexión"));
    await vi.advanceTimersByTimeAsync(30 * MINUTO);
    expect(token.leer()).toBeNull();
    expect(alCerrar).toHaveBeenCalledOnce();
  });

  it("deriva el límite de inactividad del TTL real configurado", async () => {
    iniciar(jwt(7, BASE, 10));
    fetchMock.mockResolvedValue(respuesta(null, 204));
    await vi.advanceTimersByTimeAsync(10 * MINUTO);
    expect(alCerrar).toHaveBeenCalledOnce();
    expect(leerMotivoSesion()).toBe(MENSAJE_INACTIVIDAD);
  });

  it("usa 30 minutos si el JWT no incluye fechas legibles", async () => {
    iniciar("token-opaco");
    fetchMock.mockResolvedValue(respuesta(null, 204));
    await vi.advanceTimersByTimeAsync(30 * MINUTO);
    expect(alCerrar).toHaveBeenCalledOnce();
  });

  it("cierra el token vencido sin renovarlo al regresar tras suspensión", async () => {
    iniciar();
    await vi.advanceTimersByTimeAsync(20 * MINUTO);
    actividad();
    await vi.advanceTimersByTimeAsync(10 * MINUTO);
    expect(alCerrar).toHaveBeenCalledOnce();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(leerMotivoSesion()).toBe("");
  });

  it("una actividad tardía no recupera una sesión inactiva con temporizadores suspendidos", () => {
    iniciar();
    vi.setSystemTime(BASE + 31 * MINUTO);
    actividad();
    expect(alCerrar).toHaveBeenCalledOnce();
    expect(token.leer()).toBeNull();
  });

  it("una segunda actividad no duplica una renovación en curso", async () => {
    iniciar();
    fetchMock.mockImplementation(() => new Promise(() => undefined));
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    actividad(); actividad(); actividad();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("RF-008: cambiar clave cancela la renovación y no adopta tokens de otras pestañas durante el POST", async () => {
    iniciar();
    let resolver: ((respuesta: Response) => void) | undefined;
    fetchMock.mockImplementationOnce(() => new Promise((completar) => { resolver = completar; }));
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    actividad();
    const reanudar = suspenderRenovacion(jwt());
    try {
      expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
      expect(renovacionSuspendida()).toBe(true);
      CanalFalso.canales[0]?.recibir({ tipo: "renovacion", usuario: 7, actividad: Date.now(), datos: datosToken(jwt(7, Date.now())) });
      actividad();
      expect(token.leer()).toBe(jwt());
      expect(fetchMock).toHaveBeenCalledTimes(1);
      resolver?.(respuesta(datosToken(jwt(7, Date.now()))));
      await vi.advanceTimersByTimeAsync(0);
      expect(token.leer()).toBe(jwt());
      expect(guardarTokenRenovado(datosToken(jwt(7, Date.now())), jwt())).toBe(true);
      expect(renovacionSuspendida()).toBe(false);
    } finally { reanudar(); }
    expect(token.leer()).toBe(jwt(7, Date.now()));
  });

  it("RF-008: tras fallar el cambio de clave vuelve a admitir renovaciones, sin pedirlas por reloj", async () => {
    iniciar();
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    const reanudar = suspenderRenovacion(jwt());
    actividad();
    expect(fetchMock).not.toHaveBeenCalled();
    reanudar();
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).not.toHaveBeenCalled();
    fetchMock.mockResolvedValueOnce(respuesta(datosToken(jwt(7, Date.now()))));
    actividad();
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(token.leer()).toBe(jwt(7, Date.now()));
  });

  it("ignora respuestas tardías tras logout y después de cambiar de cuenta", async () => {
    iniciar();
    let resolver: ((respuesta: Response) => void) | undefined;
    fetchMock.mockImplementation(() => new Promise((res) => { resolver = res; }));
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    actividad();
    token.borrar();
    window.dispatchEvent(new Event(SESION_EXPIRADA));
    token.guardar(jwt(8, BASE + 26 * MINUTO));
    resolver?.(respuesta(datosToken(jwt(7, BASE + 26 * MINUTO))));
    await vi.advanceTimersByTimeAsync(0);
    expect(token.leer()).toBe(jwt(8, BASE + 26 * MINUTO));
  });

  it("no reemplaza un token más nuevo con una respuesta anterior", async () => {
    iniciar();
    let resolver: ((respuesta: Response) => void) | undefined;
    fetchMock.mockImplementation(() => new Promise((res) => { resolver = res; }));
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    actividad();
    token.guardar(jwt(7, BASE + 27 * MINUTO));
    resolver?.(respuesta(datosToken(jwt(7, BASE + 26 * MINUTO))));
    await vi.advanceTimersByTimeAsync(0);
    expect(token.leer()).toBe(jwt(7, BASE + 27 * MINUTO));
  });

  it("respeta 204 o fallos de renovación sin guardar credenciales vacías", async () => {
    iniciar();
    fetchMock.mockResolvedValueOnce(respuesta(null, 204)).mockRejectedValueOnce(new TypeError("Sin red"));
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    actividad();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(30_000);
    actividad();
    await vi.advanceTimersByTimeAsync(0);
    expect(token.leer()).toBe(jwt());
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each(["red", "servidor"])("limita reintentos tras fallo de %s sin renovar por reloj", async (fallo) => {
    iniciar();
    if (fallo === "red") fetchMock.mockRejectedValue(new TypeError("Sin red"));
    else fetchMock.mockResolvedValue(respuesta({ error: { codigo: "ERROR_INTERNO", mensaje: "Error temporal" } }, 500));
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    actividad();
    await vi.advanceTimersByTimeAsync(0);
    for (let indice = 0; indice < 100; indice += 1) window.dispatchEvent(new MouseEvent("mousemove"));
    await vi.advanceTimersByTimeAsync(29_999);
    actividad();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    actividad();
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(4 * MINUTO);
    expect(token.leer()).toBeNull();
    expect(alCerrar).toHaveBeenCalledOnce();
  });

  it("401 de renovación elimina la sesión inmediatamente", async () => {
    iniciar();
    fetchMock.mockResolvedValue(respuesta({ error: { codigo: "SESION_INVALIDA", mensaje: "La sesión ya no es válida" } }, 401));
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    actividad();
    await vi.advanceTimersByTimeAsync(0);
    expect(token.leer()).toBeNull();
    expect(alCerrar).toHaveBeenCalledOnce();
  });

  it("el desmontaje cancela recursos y una respuesta pendiente", async () => {
    iniciar();
    let resolver: ((respuesta: Response) => void) | undefined;
    fetchMock.mockImplementation(() => new Promise((res) => { resolver = res; }));
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    actividad();
    limpiar?.(); limpiar = undefined;
    expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
    expect(CanalFalso.canales[0]?.cerrado).toBe(true);
    resolver?.(respuesta(datosToken(jwt(7, BASE + 26 * MINUTO))));
    await vi.advanceTimersByTimeAsync(40 * MINUTO);
    actividad();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(token.leer()).toBe(jwt());
    expect(alCerrar).not.toHaveBeenCalled();
  });

  it("remontar el gestor conserva el plazo y no renueva por la carga", async () => {
    iniciar();
    await vi.advanceTimersByTimeAsync(20 * MINUTO);
    limpiar?.();
    limpiar = iniciarGestorSesion(7, alCerrar);
    expect(fetchMock).not.toHaveBeenCalled();
    fetchMock.mockResolvedValue(respuesta(null, 204));
    await vi.advanceTimersByTimeAsync(10 * MINUTO);
    expect(alCerrar).toHaveBeenCalledOnce();
  });

  it("funciona localmente cuando BroadcastChannel no está disponible", async () => {
    vi.stubGlobal("BroadcastChannel", undefined);
    iniciar();
    fetchMock.mockResolvedValue(respuesta(null, 204));
    await vi.advanceTimersByTimeAsync(30 * MINUTO);
    expect(token.leer()).toBeNull();
  });

  it("funciona localmente si el navegador rechaza la apertura del canal", async () => {
    vi.stubGlobal("BroadcastChannel", class { constructor() { throw new Error("Canal restringido"); } });
    iniciar();
    fetchMock.mockResolvedValue(respuesta(null, 204));
    await vi.advanceTimersByTimeAsync(30 * MINUTO);
    expect(alCerrar).toHaveBeenCalledOnce();
  });

  it("sincroniza actividad y token por handshake sin solicitudes de renovación", async () => {
    iniciar();
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    CanalFalso.canales[0]?.recibir({ tipo: "estado", usuario: 7, actividad: Date.now(), datos: datosToken(jwt(7, Date.now())) });
    expect(token.leer()).toBe(jwt(7, Date.now()));
    expect(fetchMock).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(29 * MINUTO);
    expect(alCerrar).not.toHaveBeenCalled();
  });

  it("contesta a una pestaña nueva con la actividad previa, sin contar su apertura como actividad", async () => {
    iniciar();
    await vi.advanceTimersByTimeAsync(10 * MINUTO);
    CanalFalso.canales[0]?.recibir({ tipo: "consulta", usuario: 7, actividad: Date.now() });
    expect(CanalFalso.canales[0]?.mensajes).toContainEqual(expect.objectContaining({ tipo: "estado", actividad: BASE }));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("no mezcla usuarios ni acepta mensajes malformados o renovaciones antiguas", async () => {
    iniciar();
    await vi.advanceTimersByTimeAsync(10 * MINUTO);
    const canal = CanalFalso.canales[0];
    canal?.recibir(null);
    canal?.recibir({ tipo: "cierre", usuario: 8, actividad: Date.now() });
    canal?.recibir({ tipo: "renovacion", usuario: 7, actividad: Date.now(), datos: datosToken(jwt(8, Date.now())) });
    canal?.recibir({ tipo: "renovacion", usuario: 7, actividad: Date.now(), datos: datosToken(jwt()) });
    canal?.recibir({ tipo: "renovacion", usuario: 7, actividad: Date.now(), datos: {} });
    expect(token.leer()).toBe(jwt());
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("comparte la renovación sin retransmitirla en bucle", async () => {
    iniciar();
    await vi.advanceTimersByTimeAsync(26 * MINUTO);
    const canal = CanalFalso.canales[0];
    const cantidad = canal?.mensajes.length;
    canal?.recibir({ tipo: "renovacion", usuario: 7, actividad: Date.now(), datos: datosToken(jwt(7, Date.now())) });
    expect(canal?.mensajes).toHaveLength(cantidad ?? 0);
    expect(token.leer()).toBe(jwt(7, Date.now()));
  });

  it("propaga el cierre de otra pestaña sin repetir el POST logout", () => {
    iniciar();
    CanalFalso.canales[0]?.recibir({ tipo: "cierre", usuario: 7, actividad: BASE, inactividad: true });
    expect(token.leer()).toBeNull();
    expect(leerMotivoSesion()).toBe(MENSAJE_INACTIVIDAD);
    expect(alCerrar).toHaveBeenCalledOnce();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("un cierre retrasado no elimina un login posterior del mismo usuario", async () => {
    iniciar();
    const avisoAnterior = { tipo: "cierre", usuario: 7, actividad: BASE, emitidoEn: BASE, inactividad: true };
    await vi.advanceTimersByTimeAsync(MINUTO);
    const nuevoLogin = jwt(7, Date.now());
    token.guardar(nuevoLogin);
    await vi.advanceTimersByTimeAsync(MINUTO);
    CanalFalso.canales[0]?.recibir(avisoAnterior);
    expect(token.leer()).toBe(nuevoLogin);
    expect(alCerrar).not.toHaveBeenCalled();
    expect(leerMotivoSesion()).toBe("");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("el cierre explícito comparte el evento al desmontarse y no almacena el token en metadatos", () => {
    iniciar();
    expect(sessionStorage.getItem("predicitas_actividad_sesion")).not.toContain(jwt());
    token.borrar();
    limpiar?.(); limpiar = undefined;
    expect(CanalFalso.canales[0]?.mensajes).toContainEqual(expect.objectContaining({ tipo: "cierre", usuario: 7 }));
  });
});

describe("guardado condicional y lectura del JWT (RNF-004)", () => {
  it("rechaza respuestas sin credencial previa o posteriores a otra sesión", () => {
    token.guardar("otra-credencial");
    expect(guardarTokenRenovado(datosToken("renovado"), "anterior")).toBe(false);
    expect(guardarTokenRenovado(datosToken("renovado"), null)).toBe(false);
    expect(token.leer()).toBe("otra-credencial");
  });
  it("guarda el token válido y emite el evento que reajusta el gestor", () => {
    token.guardar("anterior");
    expect(guardarTokenRenovado(datosToken("renovado"), "anterior")).toBe(true);
    expect(token.leer()).toBe("renovado");
  });
  it("tolera payload inválido, JSON escalar y fechas no numéricas", () => {
    expect(leerJwt("invalido")).toEqual({});
    expect(leerJwt("x.!.y")).toEqual({});
    expect(leerJwt(`x.${btoa("null")}.y`)).toEqual({});
    expect(leerJwt(`x.${btoa('{"iat":"fecha","exp":null}')}.y`)).toEqual({ sub: undefined, iat: undefined, exp: undefined });
  });
});
