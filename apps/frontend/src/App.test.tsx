import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { ContextoSesion, type ContextoAuth } from "./nucleo/auth/contexto";
import type { Pagina, Rol, Usuario } from "./nucleo/api/tipos";
import { inicioPorRol, menuPorRol, type ModuloMenu } from "./nucleo/layout/ranuras";
import type { CatalogosOut, CitaDetalleOut, CitaResumenOut } from "./modulos/citas/tipos";

// RF-015, RF-018, RF-104 y RNF-007: fixtures sintéticos completos M02 para
// verificar las ranuras sin sustituir respuestas distintas por una misma forma.
const catalogosCitas: CatalogosOut = {
  especialidades: ["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"],
  estados: ["RECIBIDA", "CONFIRMADA", "REPROGRAMADA", "CANCELADA", "LIBERADA", "ATENDIDA", "NO_SHOW"],
  niveles_riesgo: ["BAJO", "MEDIO", "ALTO"], medicos: ["Profesional sintético 1"],
  canales_origen: ["WEB", "CALL_CENTER", "PRESENCIAL"], tipos_paciente: ["NUEVO", "CONTINUADOR"],
};
const paginaCitas: Pagina<CitaResumenOut> = { total: 0, limite: 50, desplazamiento: 0, items: [] };
const detalleCita: CitaDetalleOut = {
  id_cita: 324, id_cita_externa: "CIT-SIM-000324", paciente_anon_id: "PAC-SIM-0007",
  sede: "SAN_ISIDRO", especialidad: "CARDIOLOGIA", medico: "Profesional sintético 1",
  fecha_hora_cita: "2026-10-20T09:00:00-05:00", fecha_registro_cita: "2026-10-01T10:00:00-05:00",
  antelacion_dias: 19, tipo_paciente: "CONTINUADOR", canal_origen: "WEB", franja_horaria: "MANANA",
  dia_semana: "MARTES", inasistencias_previas: 0, reprogramaciones_prev: 0, asistencias_previas: 1,
  estado_actual: "RECIBIDA", target_no_show: null, historial: [], check_in: null,
  predicciones: [], intervenciones: [], cupo_liberado: null, reasignacion: null,
};

function mostrar(ruta: string, rol: Rol = "ADMINISTRADOR", autenticado = true, datos: CitaDetalleOut = detalleCita) {
  const usuario: Usuario = { id_usuario: 1, nombre_completo: "Usuario sintético", correo_institucional: "demo@predicitas.crp", rol, activo: true, creado_en: "2026-10-18T10:00:00-05:00", actualizado_en: null };
  const contexto: ContextoAuth = { usuario: autenticado ? usuario : null, cargando: false, mensajeSesion: "", iniciarSesion: vi.fn(), cerrarSesion: vi.fn(), tieneRol: (...roles) => autenticado && roles.includes(rol) };
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async (entrada: RequestInfo | URL) => {
    const url = new URL(entrada instanceof Request ? entrada.url : String(entrada));
    const respuesta = url.pathname === "/citas/catalogos" ? catalogosCitas
      : url.pathname === "/citas" ? { ...paginaCitas, limite: Number(url.searchParams.get("limite") ?? 50), desplazamiento: Number(url.searchParams.get("desplazamiento") ?? 0) }
        : /^\/citas\/\d+$/.test(url.pathname) ? datos : undefined;
    if (respuesta === undefined) throw new Error(`No hay respuesta simulada para ${url.pathname}.`);
    return new Response(JSON.stringify(respuesta), { status: 200 });
  }));
  return { ...render(<ContextoSesion.Provider value={contexto}><MemoryRouter initialEntries={[ruta]}><App /></MemoryRouter></ContextoSesion.Provider>), contexto };
}

// RF-003: ambos import.meta.glob descubren el módulo fixture sin editar App/Layout.
describe("router y menú por ranuras", () => {
  it("descubre la ruta y su menú y conserva los landmarks", () => {
    mostrar("/prueba-ranura");
    expect(screen.getByRole("heading", { name: "Módulo de prueba descubierto" })).toBeInTheDocument();
    expect(within(screen.getByRole("navigation", { name: "Principal" })).getByRole("link", { name: "Prueba de ranura" })).toHaveAttribute("href", "/prueba-ranura");
    expect(screen.getByRole("main")).toHaveAttribute("id", "contenido");
    expect(screen.getByRole("link", { name: "Ir al contenido" })).toHaveAttribute("href", "#contenido");
  });
  it("protege la ruta descubierta y filtra el menú por rol", () => {
    mostrar("/prueba-ranura", "TECNICO_IA");
    expect(screen.getByRole("heading", { name: "No tienes permiso para esta sección" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Prueba de ranura" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Importar CSV" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Citas" })).toBeInTheDocument();
  });
  it.each<Rol>(["ADMINISTRADOR", "RECEPCION", "TECNICO_IA"])("inicia %s en citas mientras no existe /panel", async (rol) => {
    mostrar("/", rol);
    expect(await screen.findByRole("heading", { name: "Bandeja de citas" })).toBeInTheDocument();
  });
  it("redirige /importar y permite la vista al escritor", () => {
    mostrar("/importar", "RECEPCION");
    expect(screen.getByRole("heading", { name: "Importar citas" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Importar CSV" })).toHaveAttribute("href", "/citas/importar");
    expect(screen.getByRole("link", { name: "Importar CSV" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Citas" })).not.toHaveAttribute("aria-current");
  });
  it("conserva Citas activo al consultar un detalle", async () => {
    mostrar("/citas/324", "ADMINISTRADOR", true, detalleCita);
    expect(await screen.findByRole("heading", { name: "Cita CIT-SIM-000324" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Citas" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Importar CSV" })).not.toHaveAttribute("aria-current");
  });
  it("el alias anterior también termina en una ruta protegida", () => {
    mostrar("/importar", "TECNICO_IA");
    expect(screen.getByRole("heading", { name: "No tienes permiso para esta sección" })).toBeInTheDocument();
  });
  it("sin sesión lleva al login", () => {
    mostrar("/citas", "RECEPCION", false);
    expect(screen.getByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  });
  it("permite cerrar sesión desde la cabecera", async () => {
    const { contexto } = mostrar("/prueba-ranura");
    await userEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));
    expect(contexto.cerrarSesion).toHaveBeenCalledOnce();
  });
  it("presenta una ruta desconocida con enlace al inicio", () => {
    mostrar("/desconocida");
    expect(screen.getByRole("heading", { name: "Página no encontrada" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver al inicio" })).toHaveAttribute("href", "/");
  });
  it("ordena las entradas permitidas por orden y ruta", () => {
    const modulos: Record<string, ModuloMenu> = {
      primero: { default: [{ etiqueta: "Z", ruta: "/z", icono: "check", roles: ["RECEPCION"], orden: 1 }] },
      segundo: { default: [{ etiqueta: "A", ruta: "/a", icono: "check", roles: ["RECEPCION"], orden: 1 }, { etiqueta: "Oculta", ruta: "/admin", icono: "check", roles: ["ADMINISTRADOR"], orden: 0 }] },
    };
    expect(menuPorRol(modulos, "RECEPCION").map((entrada) => entrada.ruta)).toEqual(["/a", "/z"]);
    expect(inicioPorRol("ADMINISTRADOR", [{ ruta: "/panel", elemento: <div />, roles: ["ADMINISTRADOR"] }])).toBe("/panel");
    expect(inicioPorRol("TECNICO_IA", [{ ruta: "/panel", elemento: <div />, roles: ["TECNICO_IA"] }])).toBe("/citas");
  });
});
