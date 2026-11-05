import { api, SESION_EXPIRADA, token } from "../api/cliente";
import type { TokenOut } from "../api/tipos";
import { guardarMotivoInactividad, guardarTokenRenovado, renovacionSuspendida, RENOVACION_SUSPENDIDA, TOKEN_RENOVADO } from "./credenciales";

const PLAZO_PREDETERMINADO = 30 * 60_000;
const VENTANA_RENOVACION = 5 * 60_000;
const ESPERA_REINTENTO = 30_000;
const CLAVE_ACTIVIDAD = "predicitas_actividad_sesion";
const EVENTOS_ACTIVIDAD = ["keydown", "mousedown", "mousemove", "pointerdown", "touchstart"] as const;

interface DatosJwt { sub?: string; iat?: number; exp?: number }
type Mensaje = {
  tipo: "consulta" | "estado" | "actividad" | "cierre" | "renovacion";
  usuario: number;
  actividad: number;
  emitidoEn: number;
  inactividad?: boolean;
  datos?: TokenOut;
};

/** RNF-004, D-010: se lee la caducidad; la firma la verifica siempre la API. */
export function leerJwt(credencial: string | null): DatosJwt {
  try {
    const segmento = credencial?.split(".")[1];
    if (!segmento) return {};
    const texto = atob(segmento.replace(/-/g, "+").replace(/_/g, "/"));
    const datos: unknown = JSON.parse(texto);
    if (typeof datos !== "object" || datos === null) return {};
    const campos = datos as Record<string, unknown>;
    return {
      sub: typeof campos.sub === "string" ? campos.sub : undefined,
      iat: typeof campos.iat === "number" && Number.isFinite(campos.iat) ? campos.iat * 1000 : undefined,
      exp: typeof campos.exp === "number" && Number.isFinite(campos.exp) ? campos.exp * 1000 : undefined,
    };
  } catch { return {}; }
}

function leerActividad(usuario: number, inicio: number): number {
  try {
    const datos: unknown = JSON.parse(sessionStorage.getItem(CLAVE_ACTIVIDAD) ?? "null");
    if (typeof datos === "object" && datos !== null && "usuario" in datos && datos.usuario === usuario &&
      "actividad" in datos && typeof datos.actividad === "number" && Number.isFinite(datos.actividad)) {
      return Math.min(Date.now(), Math.max(inicio, datos.actividad));
    }
  } catch { /* Un registro incompleto se reemplaza por la fecha de emisión del token. */ }
  return Math.min(Date.now(), inicio);
}

function esMensaje(datos: unknown): datos is Mensaje {
  if (typeof datos !== "object" || datos === null) return false;
  const valor = datos as Record<string, unknown>;
  return ["consulta", "estado", "actividad", "cierre", "renovacion"].includes(String(valor.tipo)) &&
    typeof valor.usuario === "number" && typeof valor.actividad === "number" && Number.isFinite(valor.actividad) &&
    typeof valor.emitidoEn === "number" && Number.isFinite(valor.emitidoEn);
}

function esToken(datos: unknown): datos is TokenOut {
  return typeof datos === "object" && datos !== null && "access_token" in datos && typeof datos.access_token === "string" &&
    "token_type" in datos && datos.token_type === "bearer" && "expires_in" in datos && typeof datos.expires_in === "number";
}

/** RF-002, RF-090, RNF-004, D-010: gestiona una pestaña sin intervalos de renovación automática. */
export function iniciarGestorSesion(usuario: number, volverAlLogin: () => void): () => void {
  if (!token.leer()) return () => undefined;
  let vigente = true;
  let cerrada = false;
  let recibiendoToken = false;
  let canal: BroadcastChannel | undefined;
  let temporizador: ReturnType<typeof setTimeout> | undefined;
  let renovacion: AbortController | undefined;
  let proximoIntento = 0;
  const inicio = leerJwt(token.leer()).iat ?? Date.now();
  let ultimaActividad = leerActividad(usuario, inicio);

  function persistirActividad() {
    sessionStorage.setItem(CLAVE_ACTIVIDAD, JSON.stringify({ usuario, actividad: ultimaActividad }));
  }
  function enviar(tipo: Mensaje["tipo"], extras: Partial<Mensaje> = {}) {
    try { canal?.postMessage({ tipo, usuario, actividad: ultimaActividad, emitidoEn: Date.now(), ...extras } satisfies Mensaje); }
    catch { /* Sin BroadcastChannel la protección local continúa funcionando. */ }
  }
  function cerrar(inactividad: boolean, avisar = true) {
    if (!vigente || cerrada) return;
    cerrada = true;
    clearTimeout(temporizador);
    renovacion?.abort();
    if (avisar) enviar("cierre", { inactividad });
    // RF-090: el POST captura el Bearer antes de eliminarlo. El cierre local no espera la red.
    if (inactividad && avisar && token.leer()) void api<void>("/auth/logout", { metodo: "POST" }).catch(() => undefined);
    token.borrar();
    sessionStorage.removeItem(CLAVE_ACTIVIDAD);
    if (inactividad) guardarMotivoInactividad();
    window.dispatchEvent(new Event(SESION_EXPIRADA));
    volverAlLogin();
  }
  function programar() {
    clearTimeout(temporizador);
    if (!vigente || cerrada || !token.leer()) return;
    const jwt = leerJwt(token.leer());
    const plazo = jwt.exp !== undefined && jwt.iat !== undefined && jwt.exp > jwt.iat ? jwt.exp - jwt.iat : PLAZO_PREDETERMINADO;
    const limiteActividad = ultimaActividad + plazo;
    const limiteToken = jwt.exp ?? Infinity;
    const inactividad = limiteActividad <= limiteToken;
    temporizador = setTimeout(() => cerrar(inactividad), Math.max(0, Math.min(limiteActividad, limiteToken) - Date.now()));
  }
  function adoptarToken(datos: unknown) {
    if (renovacionSuspendida() || !esToken(datos)) return;
    const actual = token.leer();
    const nuevoJwt = leerJwt(datos.access_token);
    const previoJwt = leerJwt(actual);
    // D-010: no mezcla cuentas ni sobrescribe un login posterior con mensajes antiguos.
    if (nuevoJwt.sub !== String(usuario) || !nuevoJwt.iat || !nuevoJwt.exp || nuevoJwt.exp <= Date.now() ||
      nuevoJwt.iat <= (previoJwt.iat ?? 0)) return;
    recibiendoToken = true;
    guardarTokenRenovado(datos, actual);
    recibiendoToken = false;
  }
  function recibir(evento: MessageEvent<unknown>) {
    if (!vigente || cerrada || !token.leer() || !esMensaje(evento.data) || evento.data.usuario !== usuario) return;
    const mensaje = evento.data;
    if (mensaje.tipo === "cierre") {
      // RF-002, D-010: un cierre en tránsito no invalida un login posterior del mismo usuario.
      if ((leerJwt(token.leer()).iat ?? 0) > mensaje.emitidoEn) return;
      cerrar(mensaje.inactividad === true, false);
      return;
    }
    if (mensaje.tipo === "consulta") {
      const credencial = token.leer();
      const jwt = leerJwt(credencial);
      enviar("estado", { datos: credencial ? { access_token: credencial, token_type: "bearer", expires_in: Math.max(0, ((jwt.exp ?? Date.now()) - Date.now()) / 1000) } : undefined });
      return;
    }
    ultimaActividad = Math.max(ultimaActividad, Math.min(Date.now(), mensaje.actividad));
    persistirActividad();
    if (mensaje.tipo === "renovacion" || mensaje.tipo === "estado") adoptarToken(mensaje.datos);
    programar(); // Recibir mensajes o abrir otra pestaña nunca dispara POST /auth/renovar.
  }
  function tokenRenovado(evento: Event) {
    if (!vigente || cerrada) return;
    const detalle: unknown = (evento as CustomEvent<unknown>).detail;
    if (!recibiendoToken && typeof detalle === "object" && detalle !== null && "datos" in detalle && esToken(detalle.datos)) {
      enviar("renovacion", { datos: detalle.datos });
    }
    programar();
  }
  function actividad() {
    if (!vigente || cerrada || !token.leer()) return;
    const jwt = leerJwt(token.leer());
    const plazo = jwt.exp !== undefined && jwt.iat !== undefined && jwt.exp > jwt.iat ? jwt.exp - jwt.iat : PLAZO_PREDETERMINADO;
    if (Date.now() - ultimaActividad >= plazo) { cerrar(true); return; }
    if (jwt.exp !== undefined && jwt.exp <= Date.now()) { cerrar(false); return; }
    ultimaActividad = Date.now();
    persistirActividad();
    enviar("actividad");
    programar();
    if (renovacionSuspendida() || renovacion || Date.now() < proximoIntento || jwt.exp === undefined || jwt.exp - Date.now() >= VENTANA_RENOVACION) return;
    const anterior = token.leer();
    const controlador = new AbortController();
    renovacion = controlador;
    void api<TokenOut>("/auth/renovar", { metodo: "POST", signal: controlador.signal }).then((datos) => {
      if (vigente && !cerrada && !controlador.signal.aborted && !renovacionSuspendida() && datos) guardarTokenRenovado(datos, anterior);
      if (!datos) proximoIntento = Date.now() + ESPERA_REINTENTO;
    }).catch(() => {
      // RNF-004: tras un fallo, el ratón no debe producir decenas de POST por segundo.
      // El reloj solo habilita un intento futuro; siempre requiere actividad real.
      proximoIntento = Date.now() + ESPERA_REINTENTO;
    }).finally(() => { if (renovacion === controlador) renovacion = undefined; });
  }
  function expirada() { cerrar(false); }
  function suspender() {
    if (!renovacionSuspendida()) return;
    renovacion?.abort();
    renovacion = undefined;
  }

  try {
    if (typeof BroadcastChannel !== "undefined") {
      canal = new BroadcastChannel(`predicitas:sesion:${usuario}`);
      canal.addEventListener("message", recibir);
      enviar("consulta");
    }
  } catch { /* RNF-004: navegadores sin canal mantienen el límite por pestaña. */ }
  persistirActividad();
  EVENTOS_ACTIVIDAD.forEach((evento) => window.addEventListener(evento, actividad, { passive: true }));
  window.addEventListener(TOKEN_RENOVADO, tokenRenovado);
  window.addEventListener(SESION_EXPIRADA, expirada);
  window.addEventListener(RENOVACION_SUSPENDIDA, suspender);
  programar();
  return () => {
    vigente = false;
    clearTimeout(temporizador);
    renovacion?.abort();
    // RF-002: incluye el cierre explícito de AuthProvider; StrictMode conserva el token.
    if (!cerrada && !token.leer()) { enviar("cierre"); sessionStorage.removeItem(CLAVE_ACTIVIDAD); }
    EVENTOS_ACTIVIDAD.forEach((evento) => window.removeEventListener(evento, actividad));
    window.removeEventListener(TOKEN_RENOVADO, tokenRenovado);
    window.removeEventListener(SESION_EXPIRADA, expirada);
    window.removeEventListener(RENOVACION_SUSPENDIDA, suspender);
    canal?.removeEventListener("message", recibir);
    canal?.close();
  };
}
