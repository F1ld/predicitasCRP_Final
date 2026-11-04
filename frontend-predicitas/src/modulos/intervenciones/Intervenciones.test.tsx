import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ContextoAuth } from "../../nucleo/auth/contexto";
import { ContextoSesion } from "../../nucleo/auth/contexto";
import Intervenciones from "./Intervenciones";
import menu from "./menu";
import rutas from "./rutas";
import type { ElegibleOut, IntervencionOut, PlantillaOut } from "./tipos";

const mockUsuario = {
  id_usuario: 1,
  nombre_completo: "Operador de pruebas",
  correo_institucional: "operador@predicitas.crp",
  rol: "RECEPCION" as const,
  activo: true,
  creado_en: "2026-10-18T08:00:00-05:00",
  actualizado_en: null,
};

let sesionMock: ContextoAuth = {
  usuario: mockUsuario,
  cargando: false,
  mensajeSesion: "",
  iniciarSesion: vi.fn(),
  cerrarSesion: vi.fn(),
  tieneRol: (...roles) => roles.includes(mockUsuario.rol),
};

const plantillas: PlantillaOut[] = [
  { id: "RECORDATORIO_WHATSAPP", canal_contacto: "WHATSAPP", descripcion: "Recordatorio WhatsApp", contenido: "Mensaje sintético." },
];

const elegible: ElegibleOut = {
  id_cita: 101,
  id_cita_externa: "CIT-000101",
  paciente_anon_id: "PAC-00099",
  especialidad: "CARDIOLOGIA",
  medico: "Dra. María Sánchez",
  fecha_hora_cita: "2026-10-25T10:30:00-05:00",
  estado_actual: "RECIBIDA",
  riesgo: {
    id_prediccion: 1,
    nivel_riesgo: "ALTO",
    probabilidad_no_show: 0.654,
    version_modelo: "v1.0.0",
    fecha_hora_inferencia: "2026-10-18T09:00:00-05:00",
    resultado_simulado: true,
  },
  intervenciones_previas: 0,
};

const intervencion: IntervencionOut = {
  id_intervencion: 42,
  id_cita: 101,
  id_cita_externa: "CIT-000101",
  id_operador: 1,
  canal_contacto: "WHATSAPP",
  plantilla_mensaje: "RECORDATORIO_WHATSAPP",
  consentimiento_optout: false,
  estado_intervencion: "PENDIENTE",
  respuesta_paciente: null,
  fecha_hora_envio: "2026-10-18T10:00:00-05:00",
  fecha_hora_respuesta: null,
  acciones_disponibles: ["REGISTRAR_ENVIO", "REGISTRAR_FALLO"],
};

const fetchSimulado = vi.fn<typeof fetch>();

function respuesta(datos: unknown, status = 200) {
  return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } });
}

function pagina<T>(items: T[], total = items.length, limite = 50, desplazamiento = 0) {
  return { total, limite, desplazamiento, items };
}

function Ubicacion() {
  const ubicacion = useLocation();
  return <output aria-label="URL actual">{ubicacion.pathname}{ubicacion.search}</output>;
}

function montar(ruta = "/intervenciones") {
  return render(
    <ContextoSesion.Provider value={sesionMock}>
      <MemoryRouter initialEntries={[ruta]}>
        <Ubicacion />
        <Routes>
          <Route path="/intervenciones" element={<Intervenciones />} />
          <Route path="/intervenciones/:id" element={<p>Seguimiento detallado</p>} />
          <Route path="/citas/:id" element={<p>Detalle de cita</p>} />
          <Route path="/reportes/intervenciones" element={<p>Reporte REP-02</p>} />
        </Routes>
      </MemoryRouter>
    </ContextoSesion.Provider>,
  );
}

beforeEach(() => {
  sesionMock = {
    usuario: mockUsuario,
    cargando: false,
    mensajeSesion: "",
    iniciarSesion: vi.fn(),
    cerrarSesion: vi.fn(),
    tieneRol: (...roles) => (sesionMock.usuario ? roles.includes(sesionMock.usuario.rol) : false),
  };
  fetchSimulado.mockReset();
  fetchSimulado.mockImplementation(async (entrada, init) => {
    const url = new URL(String(entrada));
    if (url.pathname === "/intervenciones/plantillas") return respuesta(plantillas);
    if (url.pathname === "/intervenciones/elegibles") return respuesta(pagina([elegible]));
    if (url.pathname === "/intervenciones" && init?.method === "POST") return respuesta(intervencion, 201);
    if (url.pathname === "/intervenciones") return respuesta(pagina([intervencion]));
    return respuesta({ error: { codigo: "NO_ENCONTRADO", mensaje: "Ruta no encontrada" } }, 404);
  });
  vi.stubGlobal("fetch", fetchSimulado);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// M05-V01, RF-003, RF-057, RF-058, RF-060, RF-093: Intervenciones y elegibilidad
describe("M05-V01: vista principal de intervenciones", () => {
  it("muestra estado de carga mientras se verifica la sesión", () => {
    sesionMock = { ...sesionMock, cargando: true, usuario: null };
    montar();
    expect(screen.getByText("Verificando sesión…")).toBeInTheDocument();
  });

  it("informa si no hay sesión disponible", () => {
    sesionMock = { ...sesionMock, cargando: false, usuario: null };
    montar();
    expect(screen.getByText("No tienes una sesión disponible.")).toBeInTheDocument();
  });

  it("muestra la pestaña Elegibles con datos, badge de riesgo y rótulo de simulación", async () => {
    montar();
    expect(screen.getByText("Cargando citas elegibles…")).toBeInTheDocument();
    await screen.findByText("CIT-000101");
    const tabla = within(screen.getByRole("table"));
    expect(tabla.getByText("PAC-00099")).toBeInTheDocument();
    expect(tabla.getByText("Dra. María Sánchez")).toBeInTheDocument();
    expect(tabla.getByText("Cardiología")).toBeInTheDocument();
    expect(tabla.getByText("ALTO")).toBeInTheDocument();
    expect(tabla.getByText("Resultado simulado: no es desempeño real")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Intervenir en CIT-000101" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir a la cita" })).toHaveAttribute("href", "/citas/101");
    expect(screen.getByRole("link", { name: "Ver reporte REP-02" })).toHaveAttribute("href", "/reportes/intervenciones");
  });

  it("presenta el estado vacío en elegibles", async () => {
    fetchSimulado.mockImplementation(async (entrada) => {
      const url = new URL(String(entrada));
      if (url.pathname === "/intervenciones/elegibles") return respuesta(pagina([]));
      return respuesta({});
    });
    montar();
    expect(await screen.findByText("No hay citas elegibles con esos filtros.")).toBeInTheDocument();
    expect(screen.getByText("Prueba otras fechas o utiliza «Limpiar».")).toBeInTheDocument();
  });

  it("presenta el estado de error en elegibles y permite reintentar", async () => {
    let fallo = true;
    fetchSimulado.mockImplementation(async (entrada) => {
      const url = new URL(String(entrada));
      if (url.pathname === "/intervenciones/elegibles") {
        if (fallo) return respuesta({ error: { codigo: "ERROR_CONEXION", mensaje: "Error del servidor al listar elegibles." } }, 500);
        return respuesta(pagina([elegible]));
      }
      return respuesta({});
    });
    montar();
    expect(await screen.findByText("Error del servidor al listar elegibles.")).toBeInTheDocument();
    fallo = false;
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("CIT-000101")).toBeInTheDocument();
  });

  it("cambia a la pestaña Registradas y muestra las intervenciones con sus filtros", async () => {
    const persona = userEvent.setup();
    montar();
    await screen.findByText("CIT-000101");
    await persona.click(screen.getByRole("tab", { name: "Registradas" }));
    expect(await screen.findByText("#42")).toBeInTheDocument();
    const tabla = within(screen.getByRole("table"));
    expect(tabla.getByText("WhatsApp")).toBeInTheDocument();
    expect(tabla.getByText("Pendiente")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver seguimiento" })).toHaveAttribute("href", "/intervenciones/42");
    expect(screen.getByLabelText("URL actual")).toHaveTextContent("pestana=registradas");
  });

  it("presenta el estado vacío en registradas", async () => {
    fetchSimulado.mockImplementation(async (entrada) => {
      const url = new URL(String(entrada));
      if (url.pathname === "/intervenciones") return respuesta(pagina([]));
      return respuesta({});
    });
    montar("/intervenciones?pestana=registradas");
    expect(await screen.findByText("No hay intervenciones registradas con esos filtros.")).toBeInTheDocument();
  });

  it("permite a TECNICO_IA consultar solo registradas sin opciones de creación", async () => {
    sesionMock = {
      ...sesionMock,
      usuario: { ...mockUsuario, rol: "TECNICO_IA" },
    };
    montar();
    expect(await screen.findByRole("heading", { name: "Intervenciones registradas" })).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Ver reporte REP-02" })).not.toBeInTheDocument();
    expect(screen.queryByText("Intervenir")).not.toBeInTheDocument();
  });

  it("informa a TECNICO_IA si accede con id_cita en la URL", async () => {
    sesionMock = {
      ...sesionMock,
      usuario: { ...mockUsuario, rol: "TECNICO_IA" },
    };
    montar("/intervenciones?id_cita=101");
    expect(await screen.findByText(/Tu rol permite consultar intervenciones. La creación corresponde a Recepción o al Administrador./)).toBeInTheDocument();
  });

  it("abre el diálogo de nueva intervención al pulsar Intervenir en una cita elegible", async () => {
    const persona = userEvent.setup();
    montar();
    await screen.findByText("CIT-000101");
    await persona.click(screen.getByRole("button", { name: "Intervenir en CIT-000101" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/Cita CIT-000101/)).toBeInTheDocument();
  });

  it("abre el diálogo directamente cuando llega ?id_cita= en la URL para roles escritores", async () => {
    montar("/intervenciones?id_cita=101");
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/Cita #101/)).toBeInTheDocument();
  });

  it("valida que id_cita sea un entero positivo", async () => {
    montar("/intervenciones?id_cita=-5");
    expect(await screen.findByText("El identificador de cita debe ser un entero positivo.")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("cierra el diálogo al crear y muestra el mensaje de éxito con enlace al seguimiento", async () => {
    const persona = userEvent.setup();
    montar("/intervenciones?id_cita=101");
    await screen.findByText("CIT-000101");
    const plantilla = await screen.findByLabelText("Plantilla");
    await waitFor(() => expect(plantilla).not.toBeDisabled());
    const casillaConsentimiento = screen.getByLabelText(/El paciente cuenta con consentimiento/i);
    await persona.click(casillaConsentimiento);
    expect(casillaConsentimiento).toBeChecked();
    await persona.click(screen.getByRole("button", { name: "Crear intervención" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(await screen.findByText(/Intervención creada correctamente/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir seguimiento #42" })).toHaveAttribute("href", "/intervenciones/42");
  });

  it("valida que la fecha inicial no sea posterior a la final en el filtro", async () => {
    const persona = userEvent.setup();
    montar();
    await screen.findByText("CIT-000101");
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-10-30" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-10-20" } });
    await persona.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    expect(await screen.findByText("La fecha inicial no puede ser posterior a la final.")).toBeInTheDocument();
  });

  it("navega entre pestañas con el teclado (ArrowRight, ArrowLeft, Home, End)", async () => {
    montar();
    await screen.findByText("CIT-000101");
    const pestanaElegibles = screen.getByRole("tab", { name: "Elegibles" });
    const pestanaRegistradas = screen.getByRole("tab", { name: "Registradas" });
    pestanaElegibles.focus();
    fireEvent.keyDown(pestanaElegibles, { key: "ArrowRight" });
    await waitFor(() => expect(pestanaRegistradas).toHaveFocus());
    expect(pestanaRegistradas).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(pestanaRegistradas, { key: "ArrowLeft" });
    await waitFor(() => expect(pestanaElegibles).toHaveFocus());
    expect(pestanaElegibles).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(pestanaElegibles, { key: "End" });
    await waitFor(() => expect(pestanaRegistradas).toHaveFocus());
    fireEvent.keyDown(pestanaRegistradas, { key: "Home" });
    await waitFor(() => expect(pestanaElegibles).toHaveFocus());
  });

  it("maneja paginación correctamente (desplazamiento y límites)", async () => {
    const persona = userEvent.setup();
    fetchSimulado.mockImplementation(async (entrada) => {
      const url = new URL(String(entrada));
      if (url.pathname === "/intervenciones/elegibles") {
        return respuesta(pagina([elegible], 120, 50, Number(url.searchParams.get("desplazamiento") || 0)));
      }
      return respuesta({});
    });
    montar();
    await screen.findByText("Página 1 de 3 · 120 registros");
    const botonSiguiente = screen.getByRole("button", { name: "Siguiente" });
    expect(botonSiguiente).not.toBeDisabled();
    await persona.click(botonSiguiente);
    expect(screen.getByLabelText("URL actual")).toHaveTextContent("desplazamiento=50");
  });

  it("limpia filtros aplicados al hacer clic en Limpiar", async () => {
    const persona = userEvent.setup();
    montar("/intervenciones?desde=2026-10-01&hasta=2026-10-15");
    await screen.findByText("CIT-000101");
    await persona.click(screen.getByRole("button", { name: "Limpiar" }));
    expect(screen.getByLabelText("URL actual").textContent).toBe("/intervenciones");
  });

  it("aplica filtros de fecha válidos al enviar el formulario", async () => {
    const persona = userEvent.setup();
    montar();
    await screen.findByText("CIT-000101");
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-10-10" } });
    await persona.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    expect(screen.getByLabelText("URL actual")).toHaveTextContent("desde=2026-10-01");
    expect(screen.getByLabelText("URL actual")).toHaveTextContent("hasta=2026-10-10");
  });

  it("publica las rutas del módulo y los accesos del menú según el contrato", () => {
    expect(rutas.map((r) => r.ruta)).toEqual(["/intervenciones", "/intervenciones/:id", "/reportes/intervenciones"]);
    expect(rutas[0].roles).toContain("TECNICO_IA");
    expect(rutas[2].roles).not.toContain("TECNICO_IA");
    expect(menu.map((m) => m.ruta)).toEqual(["/intervenciones", "/reportes/intervenciones"]);
    expect(menu[0].roles).toContain("TECNICO_IA");
    expect(menu[1].roles).not.toContain("TECNICO_IA");
  });
});

