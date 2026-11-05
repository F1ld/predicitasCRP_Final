import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Rol } from "../../nucleo/api/tipos";
import Bandeja from "./Bandeja";
import type { CatalogosOut, CitaResumenOut } from "./tipos";

const permisos = vi.hoisted(() => ({ rol: "RECEPCION" as Rol, tieneRol: vi.fn<(...roles: Rol[]) => boolean>() }));
vi.mock("../../nucleo/auth/useAuth", () => ({ useAuth: () => ({ tieneRol: permisos.tieneRol }) }));

// RF-015 a RF-017, RF-084, RF-104, RNF-007 y RNF-016: contrato M02-V01,
// sin servidor ni datos personales. Los catálogos se simulan por su endpoint.
const catalogos: CatalogosOut = {
  especialidades: ["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"],
  estados: ["RECIBIDA", "CONFIRMADA", "REPROGRAMADA", "CANCELADA", "LIBERADA", "ATENDIDA", "NO_SHOW"],
  niveles_riesgo: ["BAJO", "MEDIO", "ALTO"],
  medicos: ["Profesional sintético 1", "Profesional sintético 2"],
  canales_origen: ["WEB", "CALL_CENTER", "PRESENCIAL"], tipos_paciente: ["NUEVO", "CONTINUADOR"],
};
const cita: CitaResumenOut = {
  id_cita: 324, id_cita_externa: "CIT-SIM-000324", paciente_anon_id: "PAC-SIM-0007",
  sede: "SAN_ISIDRO", especialidad: "CARDIOLOGIA", medico: "Profesional sintético 1",
  fecha_hora_cita: "2026-10-20T09:00:00-05:00", fecha_registro_cita: "2026-10-01T10:00:00-05:00",
  antelacion_dias: 19, tipo_paciente: "CONTINUADOR", canal_origen: "WEB", franja_horaria: "MANANA",
  dia_semana: "MARTES", inasistencias_previas: 0, reprogramaciones_prev: 0, asistencias_previas: 1,
  estado_actual: "RECIBIDA", target_no_show: null, riesgo: null,
  estado_intervencion: null, respuesta_paciente: null, tiene_check_in: false,
};
const fetchSimulado = vi.fn<typeof fetch>();

function respuesta(datos: unknown, status = 200) {
  return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } });
}
function pagina(items: CitaResumenOut[] = [cita], total = items.length) {
  return { total, limite: 20, desplazamiento: 0, items };
}
function consultaCitas() {
  return fetchSimulado.mock.calls.filter(([entrada]) => new URL(String(entrada)).pathname === "/citas");
}
function ultimaConsulta() {
  return new URL(String(consultaCitas().at(-1)?.[0])).searchParams;
}
function Ubicacion() {
  const ubicacion = useLocation();
  return <output aria-label="URL actual">{ubicacion.pathname}{ubicacion.search}</output>;
}
function montar(ruta = "/citas") {
  return render(<MemoryRouter initialEntries={[ruta]}><Ubicacion /><Routes>
    <Route path="/citas" element={<Bandeja />} />
    <Route path="/citas/:id" element={<p>Detalle abierto</p>} />
    <Route path="/citas/nueva" element={<p>Registro abierto</p>} />
    <Route path="/citas/importar" element={<p>Importación abierta</p>} />
  </Routes></MemoryRouter>);
}
function datosSimulados(items = [cita], total = items.length) {
  fetchSimulado.mockImplementation((entrada) => Promise.resolve(respuesta(
    new URL(String(entrada)).pathname === "/citas/catalogos" ? catalogos : pagina(items, total),
  )));
}
beforeEach(() => {
  fetchSimulado.mockReset();
  vi.stubGlobal("fetch", fetchSimulado);
  permisos.rol = "RECEPCION";
  // RF-003: reproduce la firma rest del núcleo; pasar un arreglo como único
  // argumento dejaría de reconocer el rol y haría fallar las acciones escritoras.
  permisos.tieneRol.mockImplementation((...roles) => roles.includes(permisos.rol));
  sessionStorage.clear();
  datosSimulados();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Bandeja completa M02-V01 (RF-015, RF-016, RF-017, RF-084)", () => {
  it("anuncia carga de citas y de catálogos y bloquea los filtros mientras espera", () => {
    fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined));
    montar();
    expect(screen.getByText("Cargando citas…")).toBeInTheDocument();
    expect(screen.getByText("Cargando filtros…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeDisabled();
  });

  it("carga catálogos del servidor y muestra datos, ausencia de riesgo, intervención y llegada", async () => {
    montar();
    await screen.findByText(cita.id_cita_externa);
    await waitFor(() => expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeEnabled());
    const resultados = within(screen.getByRole("region", { name: "Resultados de citas" }));
    expect(resultados.getByText(cita.paciente_anon_id)).toBeInTheDocument();
    expect(resultados.getByText("Sin predicción")).toBeInTheDocument();
    expect(resultados.getByText("Sin intervención")).toBeInTheDocument();
    expect(resultados.getByText("Sin check-in")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Médico")).getByRole("option", { name: catalogos.medicos[1] })).toBeInTheDocument();
    expect(screen.getByLabelText("Identificador de cita")).toHaveAccessibleDescription("ID de cita, paciente o médico");
    expect(fetchSimulado.mock.calls.some(([entrada]) => new URL(String(entrada)).pathname === "/citas/catalogos")).toBe(true);
  });

  it("muestra el riesgo, el rótulo simulado junto al dato, la intervención y el check-in (RF-056, RN16)", async () => {
    datosSimulados([{ ...cita, riesgo: { id_prediccion: 4, probabilidad_no_show: 0.72, nivel_riesgo: "ALTO", version_modelo: "simulador_v1", fecha_hora_inferencia: "2026-10-18T10:00:00-05:00", resultado_simulado: true }, estado_intervencion: "RESPONDIDA", respuesta_paciente: "CONFIRMA", tiene_check_in: true }]);
    montar();
    const rotulo = await screen.findByText("Resultado simulado: no es desempeño real");
    expect(rotulo.closest("td")).toContainElement(screen.getByLabelText("Riesgo de inasistencia: ALTO"));
    expect(screen.getByText("Respondida")).toBeInTheDocument();
    expect(screen.getByText("Confirma")).toBeInTheDocument();
    expect(screen.getByText("Check-in registrado")).toBeInTheDocument();
    expect(screen.getByText(/no es una decisión clínica/)).toBeInTheDocument();
  });

  it("omite el rótulo cuando el resultado no es simulado y presenta una intervención sin respuesta", async () => {
    datosSimulados([{ ...cita, riesgo: { id_prediccion: 4, probabilidad_no_show: 0.2, nivel_riesgo: "BAJO", version_modelo: "modelo_prueba", fecha_hora_inferencia: "2026-10-18T10:00:00-05:00", resultado_simulado: false }, estado_intervencion: "PENDIENTE" }]);
    montar();
    expect(await screen.findByLabelText("Riesgo de inasistencia: BAJO")).toBeInTheDocument();
    expect(screen.queryByText("Resultado simulado: no es desempeño real")).not.toBeInTheDocument();
    expect(screen.getByText("Pendiente")).toBeInTheDocument();
  });

  it("presenta el estado vacío y conserva una paginación válida", async () => {
    datosSimulados([]);
    montar();
    expect(await screen.findByText("No hay citas con esos filtros.")).toBeInTheDocument();
    expect(screen.getByText("Página 1 de 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  });

  it.each([[403, "SIN_PERMISO", "No tienes permiso para consultar citas."], [422, "VALIDACION", "Los filtros no son válidos."]] as const)("muestra el error %s %s del contrato y permite recuperar la consulta", async (status, codigo, mensaje) => {
    let fallar = true;
    fetchSimulado.mockImplementation((entrada) => Promise.resolve(respuesta(
      new URL(String(entrada)).pathname === "/citas/catalogos" ? catalogos : fallar ? { error: { codigo, mensaje } } : pagina(),
      new URL(String(entrada)).pathname === "/citas" && fallar ? status : 200,
    )));
    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent(mensaje);
    fallar = false;
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText(cita.id_cita_externa)).toBeInTheDocument();
  });

  it("explica el error de catálogos y reintenta solo esos filtros", async () => {
    let fallarCatalogos = true;
    fetchSimulado.mockImplementation((entrada) => {
      const esCatalogo = new URL(String(entrada)).pathname === "/citas/catalogos";
      return Promise.resolve(esCatalogo && fallarCatalogos
        ? respuesta({ error: { codigo: "ERROR_INTERNO", mensaje: "Catálogos temporalmente no disponibles." } }, 500)
        : respuesta(esCatalogo ? catalogos : pagina()));
    });
    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudieron cargar los filtros: Catálogos temporalmente no disponibles.");
    expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeDisabled();
    fallarCatalogos = false;
    await userEvent.click(screen.getByRole("button", { name: "Reintentar catálogos" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeEnabled());
    expect(consultaCitas()).toHaveLength(1);
  });

  it("recupera todos los filtros desde la URL y los manda con nombres exactos al endpoint", async () => {
    const filtros = new URLSearchParams({ desde: "2026-10-01", hasta: "2026-10-30", especialidad: "CARDIOLOGIA", medico: catalogos.medicos[1], estado: "CONFIRMADA", nivel_riesgo: "SIN_PREDICCION", con_intervencion: "false", q: "PAC-SIM", desplazamiento: "20" });
    montar(`/citas?${filtros}`);
    await screen.findByText(cita.id_cita_externa);
    await waitFor(() => expect(screen.getByLabelText("Médico")).toHaveValue(catalogos.medicos[1]));
    for (const [clave, valor] of filtros) expect(ultimaConsulta().get(clave)).toBe(valor);
    expect(screen.getByLabelText("Nivel de riesgo")).toHaveValue("SIN_PREDICCION");
    expect(screen.getByLabelText("Intervención")).toHaveValue("false");
  });

  it("guarda todos los filtros combinados, recorta q y reinicia la página al aplicar", async () => {
    datosSimulados([cita], 41);
    montar("/citas?desplazamiento=20&limite=10");
    await screen.findByText(cita.id_cita_externa);
    await waitFor(() => expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-10-30" } });
    await userEvent.type(screen.getByLabelText("Identificador de cita"), " PAC-SIM ");
    await userEvent.selectOptions(screen.getByLabelText("Especialidad"), "PEDIATRIA");
    await userEvent.selectOptions(screen.getByLabelText("Médico"), catalogos.medicos[1]);
    await userEvent.selectOptions(screen.getByLabelText("Estado"), "RECIBIDA");
    await userEvent.selectOptions(screen.getByLabelText("Nivel de riesgo"), "MEDIO");
    await userEvent.selectOptions(screen.getByLabelText("Intervención"), "true");
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(consultaCitas()).toHaveLength(2));
    expect(Object.fromEntries(ultimaConsulta())).toEqual({ limite: "10", desplazamiento: "0", desde: "2026-10-01", hasta: "2026-10-30", especialidad: "PEDIATRIA", medico: catalogos.medicos[1], estado: "RECIBIDA", nivel_riesgo: "MEDIO", con_intervencion: "true", q: "PAC-SIM" });
    expect(screen.getByLabelText("URL actual").textContent).toContain("con_intervencion=true");
    expect(screen.getByLabelText("URL actual").textContent).not.toContain("desplazamiento=20");
  });

  it("rechaza rangos de fechas invertidos sin solicitar otra página", async () => {
    montar("/citas?desde=2026-10-20");
    await screen.findByText(cita.id_cita_externa);
    await waitFor(() => expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-10-19" } });
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    expect(screen.getByRole("alert")).toHaveTextContent("La fecha inicial no puede ser posterior a la fecha final.");
    expect(consultaCitas()).toHaveLength(1);
  });

  it("pagina conservando filtros y los limpia junto con el desplazamiento", async () => {
    datosSimulados([cita], 41);
    montar("/citas?medico=Profesional+sint%C3%A9tico+1&nivel_riesgo=ALTO&con_intervencion=false");
    await screen.findByText(cita.id_cita_externa);
    await waitFor(() => expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("Página 2 de 3")).toBeInTheDocument();
    expect(ultimaConsulta().get("desplazamiento")).toBe("20");
    expect(ultimaConsulta().get("medico")).toBe(catalogos.medicos[0]);
    expect(ultimaConsulta().get("con_intervencion")).toBe("false");
    await userEvent.click(screen.getByRole("button", { name: "Anterior" }));
    expect(await screen.findByText("Página 1 de 3")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    await waitFor(() => expect(consultaCitas()).toHaveLength(4));
    expect(Object.fromEntries(ultimaConsulta())).toEqual({ limite: "20", desplazamiento: "0" });
    expect(screen.getByLabelText("URL actual")).toHaveTextContent(/^\/citas$/);
  });

  it.each(["-1", "1.5", "Infinity", "no-numero"])("normaliza el desplazamiento inválido %s y un límite fuera de rango", async (desplazamiento) => {
    montar(`/citas?desplazamiento=${desplazamiento}&limite=201`);
    await screen.findByText(cita.id_cita_externa);
    expect(ultimaConsulta().get("desplazamiento")).toBe("0");
    expect(ultimaConsulta().get("limite")).toBe("20");
  });

  it("limpia un borrador sin aplicar cuando la URL ya está sin filtros (RF-015, RF-016)", async () => {
    montar("/citas");
    await screen.findByText(cita.id_cita_externa);
    await waitFor(() => expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeEnabled());
    await userEvent.type(screen.getByLabelText("Identificador de cita"), "PAC-SIM");
    await userEvent.selectOptions(screen.getByLabelText("Médico"), catalogos.medicos[1]);
    await userEvent.selectOptions(screen.getByLabelText("Nivel de riesgo"), "ALTO");
    await userEvent.selectOptions(screen.getByLabelText("Intervención"), "false");
    await userEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    expect(screen.getByLabelText("Identificador de cita")).toHaveValue("");
    expect(screen.getByLabelText("Médico")).toHaveValue("");
    expect(screen.getByLabelText("Nivel de riesgo")).toHaveValue("");
    expect(screen.getByLabelText("Intervención")).toHaveValue("");
    expect(screen.getByLabelText("URL actual")).toHaveTextContent(/^\/citas$/);
    expect(consultaCitas()).toHaveLength(1);
  });

  it("respeta el límite de la URL al paginar", async () => {
    datosSimulados([cita], 25);
    montar("/citas?limite=10");
    await screen.findByText(cita.id_cita_externa);
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("Página 2 de 3")).toBeInTheDocument();
    expect(ultimaConsulta().get("desplazamiento")).toBe("10");
    expect(ultimaConsulta().get("limite")).toBe("10");
  });

  it.each(["fila", "enlace"])("abre el detalle desde la %s", async (accion) => {
    montar();
    await screen.findByText(cita.id_cita_externa);
    await userEvent.click(accion === "fila" ? within(screen.getByRole("table")).getByText(cita.medico) : screen.getByRole("link", { name: "Ver detalle" }));
    expect(screen.getByText("Detalle abierto")).toBeInTheDocument();
  });

  it("ofrece registro e importación a roles escritores y permite abrirlos", async () => {
    montar();
    expect(permisos.tieneRol).toHaveBeenCalledWith("ADMINISTRADOR", "RECEPCION");
    expect(screen.getByRole("link", { name: "Registrar cita" })).toHaveAttribute("href", "/citas/nueva");
    expect(screen.getByRole("link", { name: "Importar" })).toHaveAttribute("href", "/citas/importar");
    await userEvent.click(screen.getByRole("link", { name: "Registrar cita" }));
    expect(screen.getByText("Registro abierto")).toBeInTheDocument();
  });

  it("oculta todas las acciones de escritura a TECNICO_IA y conserva la consulta", async () => {
    permisos.rol = "TECNICO_IA";
    montar();
    await screen.findByText(cita.id_cita_externa);
    expect(screen.queryByRole("link", { name: "Registrar cita" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Importar" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver detalle" })).toBeInTheDocument();
  });
});
