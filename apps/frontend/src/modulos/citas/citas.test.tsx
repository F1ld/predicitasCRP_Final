import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Bandeja from "./Bandeja";
import Detalle from "./Detalle";
import Importar from "./Importar";
import menu from "./menu";
import rutas from "./rutas";
import type { CitaDetalleOut, CitaResumenOut, ResultadoImportacionOut } from "./tipos";
import { ESTADOS, ROLES_ESCRITURA, TRANSICIONES } from "./transiciones";

const permisos = vi.hoisted(() => ({ escritura: true }));
vi.mock("../../nucleo/auth/useAuth", () => ({ useAuth: () => ({ tieneRol: () => permisos.escritura }) }));

// RF-009, RF-011, RF-018, RF-019 y RNF-007: todos los datos son sintéticos.
const cita: CitaResumenOut = {
  id_cita: 324, id_cita_externa: "CIT-SIM-000324", paciente_anon_id: "PAC-SIM-0007",
  sede: "SAN_ISIDRO", especialidad: "CARDIOLOGIA", medico: "Profesional sintético 1",
  fecha_hora_cita: "2026-10-20T09:00:00-05:00", fecha_registro_cita: "2026-10-01T10:00:00-05:00",
  antelacion_dias: 19, tipo_paciente: "CONTINUADOR", canal_origen: "WEB", franja_horaria: "MANANA",
  dia_semana: "MARTES", inasistencias_previas: 0, reprogramaciones_prev: 0, asistencias_previas: 1,
  estado_actual: "RECIBIDA", target_no_show: null, riesgo: null, estado_intervencion: null,
  respuesta_paciente: null, tiene_check_in: false,
};
const detalle: CitaDetalleOut = {
  ...cita,
  check_in: null, predicciones: [], intervenciones: [], cupo_liberado: null, reasignacion: null,
  historial: [{ id_historial: 1, estado_anterior: null, estado_nuevo: "RECIBIDA", id_usuario_actor: null, motivo_cambio: null, fecha_hora_evento: "2026-10-01T10:00:00-05:00" }],
};
const resultadoImportacion: ResultadoImportacionOut = {
  recibidas: 2, aceptadas: 1, rechazadas: 1,
  detalle_rechazos: [{ fila: 2, id_cita_externa: "CIT-SIM-000325", motivos: ["Identificador duplicado", "Fuera del piloto"] }],
};
const fetchSimulado = vi.fn<typeof fetch>();

function respuesta(datos: unknown, status = 200) {
  return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } });
}

function pagina(items: CitaResumenOut[] = [cita], total = items.length) {
  return { total, limite: 20, desplazamiento: 0, items };
}

function montarBandeja(ruta = "/citas?desde=") {
  return render(<MemoryRouter initialEntries={[ruta]}><Routes>
    <Route path="/citas" element={<Bandeja />} />
    <Route path="/citas/:id" element={<p>Detalle abierto</p>} />
  </Routes></MemoryRouter>);
}

function montarDetalle(volver = "/citas?desde=2026-10-01") {
  return render(<MemoryRouter initialEntries={[{ pathname: "/citas/324", state: { volver } }]}><Routes>
    <Route path="/citas/:id" element={<Detalle />} />
  </Routes></MemoryRouter>);
}

function montarImportar() {
  return render(<MemoryRouter><Importar /></MemoryRouter>);
}

beforeEach(() => {
  fetchSimulado.mockReset();
  // RF-015: los catálogos son una consulta independiente de la bandeja.
  vi.stubGlobal("fetch", (entrada: RequestInfo | URL, opciones?: RequestInit) =>
    new URL(String(entrada)).pathname === "/citas/catalogos"
      ? Promise.resolve(respuesta({ especialidades: ["CARDIOLOGIA", "TRAUMATOLOGIA", "PEDIATRIA"], estados: ESTADOS, niveles_riesgo: ["BAJO", "MEDIO", "ALTO"], medicos: [], canales_origen: ["WEB", "CALL_CENTER", "PRESENCIAL"], tipos_paciente: ["NUEVO", "CONTINUADOR"] }))
      : fetchSimulado(entrada, opciones));
  permisos.escritura = true;
  sessionStorage.clear();
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value(this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value(this: HTMLDialogElement) { this.removeAttribute("open"); } });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Bandeja migrada (RF-009, RF-016, RF-056, RN16, RNF-016)", () => {
  it("muestra el estado cargando y bloquea los filtros mientras espera", () => {
    fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined));
    montarBandeja();
    expect(screen.getByText("Cargando citas…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeDisabled();
  });

  it("muestra los datos, fecha en Lima y ausencia de predicción", async () => {
    fetchSimulado.mockResolvedValue(respuesta(pagina()));
    montarBandeja();
    expect(await screen.findByText(cita.id_cita_externa)).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Sin predicción" })).toBeInTheDocument();
    expect(screen.getByText(cita.medico)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver detalle" })).toHaveAttribute("href", "/citas/324");
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  });

  it("identifica el riesgo y rotula un resultado simulado junto al dato", async () => {
    fetchSimulado.mockResolvedValue(respuesta(pagina([{ ...cita, riesgo: {
      id_prediccion: 7, probabilidad_no_show: 0.75, nivel_riesgo: "ALTO", version_modelo: "simulador_v1",
      fecha_hora_inferencia: "2026-10-18T10:00:00-05:00", resultado_simulado: true,
    } }])));
    montarBandeja();
    expect(await screen.findByText("Resultado simulado: no es desempeño real")).toBeInTheDocument();
    expect(screen.getByLabelText("Riesgo de inasistencia: ALTO")).toBeInTheDocument();
    expect(screen.queryByRole("cell", { name: "Sin predicción" })).not.toBeInTheDocument();
  });

  it("conserva el estado vacío con ayuda para ampliar la búsqueda", async () => {
    fetchSimulado.mockResolvedValue(respuesta(pagina([])));
    montarBandeja();
    expect(await screen.findByText("No hay citas con esos filtros.")).toBeInTheDocument();
    expect(screen.getByText("Página 1 de 1")).toBeInTheDocument();
  });

  it("muestra el error de contrato y permite reintentar", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo: "ERROR_INTERNO", mensaje: "Consulta temporalmente no disponible." } }, 500))
      .mockResolvedValueOnce(respuesta(pagina()));
    montarBandeja();
    expect(await screen.findByText("Consulta temporalmente no disponible.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText(cita.id_cita_externa)).toBeInTheDocument();
  });

  it("valida las fechas y lleva los filtros a la consulta", async () => {
    fetchSimulado.mockImplementation(() => Promise.resolve(respuesta(pagina())));
    montarBandeja("/citas?desde=2026-10-20");
    await screen.findByText(cita.id_cita_externa);
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-10-19" } });
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    expect(screen.getByText("La fecha inicial no puede ser posterior a la fecha final.")).toBeInTheDocument();
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-10-21" } });
    await userEvent.type(screen.getByLabelText("Identificador de cita"), " CIT-SIM ");
    await userEvent.selectOptions(screen.getByLabelText("Especialidad"), "CARDIOLOGIA");
    await userEvent.selectOptions(screen.getByLabelText("Estado"), "RECIBIDA");
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(2));
    const consulta = new URL(String(fetchSimulado.mock.calls[1][0]), "http://localhost").searchParams;
    expect(consulta.get("q")).toBe("CIT-SIM");
    expect(consulta.get("especialidad")).toBe("CARDIOLOGIA");
    expect(consulta.get("estado")).toBe("RECIBIDA");
    expect(consulta.get("hasta")).toBe("2026-10-21");
  });

  it("pagina y limpia filtros desde la URL", async () => {
    fetchSimulado.mockImplementation(() => Promise.resolve(respuesta(pagina([cita], 41))));
    montarBandeja("/citas?desde=2026-10-20&q=CIT-SIM");
    await screen.findByText(cita.id_cita_externa);
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("Página 2 de 3")).toBeInTheDocument();
    expect(String(fetchSimulado.mock.calls[1][0])).toContain("desplazamiento=20");
    await userEvent.click(screen.getByRole("button", { name: "Anterior" }));
    expect(await screen.findByText("Página 1 de 3")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(4));
    expect(String(fetchSimulado.mock.calls[3][0])).not.toContain("desde=");
    expect(screen.getByLabelText("Identificador de cita")).toHaveValue("");
  });

  it("normaliza un desplazamiento inválido", async () => {
    fetchSimulado.mockResolvedValue(respuesta(pagina()));
    montarBandeja("/citas?desplazamiento=-4");
    await screen.findByText(cita.id_cita_externa);
    expect(String(fetchSimulado.mock.calls[0][0])).toContain("desplazamiento=0");
  });

  it.each(["fila", "enlace"])("abre el detalle con la %s", async (accion) => {
    fetchSimulado.mockResolvedValue(respuesta(pagina()));
    montarBandeja();
    await screen.findByText(cita.id_cita_externa);
    await userEvent.click(accion === "fila" ? screen.getByText(cita.medico) : screen.getByRole("link", { name: "Ver detalle" }));
    expect(screen.getByText("Detalle abierto")).toBeInTheDocument();
  });
});

describe("Detalle migrado (RF-018, RF-019, RF-020, RNF-007)", () => {
  it("muestra carga e historial con datos seudonimizados", async () => {
    fetchSimulado.mockResolvedValue(respuesta(detalle));
    montarDetalle();
    expect(screen.getByText("Cargando detalle…")).toBeInTheDocument();
    expect(await screen.findByText(cita.paciente_anon_id)).toBeInTheDocument();
    expect(screen.getByText(/Actor no registrado/)).toBeInTheDocument();
    expect(screen.getByText("Sin motivo registrado")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Volver a la bandeja/ })).toHaveAttribute("href", "/citas?desde=2026-10-01");
  });

  it("muestra el error de cita no encontrada y reintenta", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo: "NO_ENCONTRADO", mensaje: "No se encontró la cita." } }, 404))
      .mockResolvedValueOnce(respuesta(detalle));
    montarDetalle();
    expect(await screen.findByText("No se encontró la cita.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText(cita.paciente_anon_id)).toBeInTheDocument();
  });

  it("oculta las acciones de escritura al rol de lectura", async () => {
    permisos.escritura = false;
    fetchSimulado.mockResolvedValue(respuesta(detalle));
    montarDetalle("https://example.invalid");
    expect(await screen.findByText(/Tu rol permite consultar/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Marcar como/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Volver a la bandeja/ })).toHaveAttribute("href", "/citas");
  });

  it.each([0, 1] as const)("presenta el desenlace %s y el estado final", async (target) => {
    fetchSimulado.mockResolvedValue(respuesta({ ...detalle, estado_actual: target === 0 ? "ATENDIDA" : "NO_SHOW", target_no_show: target, historial: [] }));
    montarDetalle();
    expect(await screen.findByText("Estado final: no admite más cambios.")).toBeInTheDocument();
    expect(screen.getByText(target === 0 ? "0 · Asistió" : "1 · No asistió")).toBeInTheDocument();
    expect(screen.getByText("No hay transiciones registradas.")).toBeInTheDocument();
  });

  it("abre el diálogo, permite cancelar y confirma una sola actualización con motivo", async () => {
    const actualizada = { ...detalle, estado_actual: "CONFIRMADA", historial: [{ ...detalle.historial[0], id_usuario_actor: 8, estado_anterior: "RECIBIDA", estado_nuevo: "CONFIRMADA", motivo_cambio: "Confirmación sintética" }] };
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockResolvedValueOnce(respuesta(actualizada)).mockResolvedValueOnce(respuesta(actualizada));
    montarDetalle();
    await userEvent.click(await screen.findByRole("button", { name: "Marcar como Confirmada" }));
    const dialogo = screen.getByRole("dialog");
    await userEvent.click(within(dialogo).getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Marcar como Confirmada" }));
    await userEvent.type(screen.getByLabelText("Motivo (opcional)"), " Confirmación sintética ");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar cambio" }));
    expect(await screen.findByText("Estado actualizado a Confirmada.")).toBeInTheDocument();
    expect(JSON.parse(String(fetchSimulado.mock.calls[1][1]?.body))).toEqual({ estado_nuevo: "CONFIRMADA", motivo: "Confirmación sintética" });
    expect(fetchSimulado.mock.calls[1][1]?.method).toBe("POST");
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(3));
    expect(screen.getByText(/Usuario #8/)).toBeInTheDocument();
  });

  it("recarga tras un conflicto de transición", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle))
      .mockResolvedValueOnce(respuesta({ error: { codigo: "TRANSICION_INVALIDA", mensaje: "El estado cambió." } }, 409))
      .mockResolvedValueOnce(respuesta({ ...detalle, estado_actual: "ATENDIDA", target_no_show: 0 }));
    montarDetalle();
    await userEvent.click(await screen.findByRole("button", { name: "Marcar como Confirmada" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar cambio" }));
    expect(await screen.findByText(/La cita ya no admite ese cambio/)).toBeInTheDocument();
    expect(screen.getByText("Estado final: no admite más cambios.")).toBeInTheDocument();
  });

  it("informa cuando se guardó pero falló refrescar el detalle", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockResolvedValueOnce(respuesta({ ...detalle, estado_actual: "CONFIRMADA" }))
      .mockRejectedValueOnce(new Error("Conexión interrumpida."));
    montarDetalle();
    await userEvent.click(await screen.findByRole("button", { name: "Marcar como Confirmada" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar cambio" }));
    expect(await screen.findByText(/El cambio se guardó, pero no se pudo refrescar el detalle: No se pudo conectar con el servidor/)).toBeInTheDocument();
    expect(screen.getByText("Estado actualizado a Confirmada.")).toBeInTheDocument();
  });

  it("muestra un fallo de guardado sin anunciar éxito", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(detalle)).mockRejectedValueOnce(new Error("Conexión interrumpida."));
    montarDetalle();
    await userEvent.click(await screen.findByRole("button", { name: "Marcar como Confirmada" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar cambio" }));
    expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
    expect(screen.queryByText(/Estado actualizado a/)).not.toBeInTheDocument();
  });
});

describe("Importación migrada (RF-011, RF-012, RNF-007)", () => {
  it("deshabilita enviar hasta elegir un CSV válido y permite consultar columnas", async () => {
    montarImportar();
    expect(screen.getByRole("button", { name: "Importar archivo" })).toBeDisabled();
    await userEvent.click(screen.getByText("Ver columnas obligatorias"));
    expect(screen.getByText(/id_cita_externa, paciente_anon_id/)).toBeVisible();
  });

  it.each([
    ["citas.txt", "datos", "Selecciona un archivo con extensión .csv."],
    ["citas.csv", "", "El archivo está vacío."],
    ["citas.csv", "x".repeat(2 * 1024 * 1024 + 1), "El archivo supera los 2 MB permitidos."],
  ])("rechaza el archivo inválido %s", async (nombre, contenido, mensaje) => {
    montarImportar();
    const usuario = userEvent.setup({ applyAccept: false });
    await usuario.upload(screen.getByLabelText("Archivo CSV"), new File([contenido], nombre, { type: "text/csv" }));
    expect(screen.getByText(mensaje)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importar archivo" })).toBeDisabled();
    expect(fetchSimulado).not.toHaveBeenCalled();
  });

  it("envía multipart, muestra el resumen y los rechazos, y limpia la selección", async () => {
    fetchSimulado.mockResolvedValue(respuesta(resultadoImportacion));
    montarImportar();
    const archivo = new File(["id_cita_externa,paciente_anon_id\nCIT-SIM-1,PAC-SIM-1"], "citas.CSV", { type: "text/csv" });
    await userEvent.upload(screen.getByLabelText("Archivo CSV"), archivo);
    expect(screen.getByText("citas.CSV")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Importar archivo" }));
    expect(await screen.findByText("Resultado de la importación")).toBeInTheDocument();
    const opciones = fetchSimulado.mock.calls[0][1];
    expect(opciones?.body).toBeInstanceOf(FormData);
    expect((opciones?.body as FormData | undefined)?.get("archivo")).toEqual(archivo);
    expect(screen.getByText("Identificador duplicado; Fuera del piloto")).toBeInTheDocument();
    expect(screen.getByText("CIT-SIM-000325")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importar archivo" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "Ver citas importadas" })).toHaveAttribute("href", "/citas?desde=");
  });

  it("bloquea un segundo envío mientras espera la importación", async () => {
    fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined));
    montarImportar();
    await userEvent.upload(screen.getByLabelText("Archivo CSV"), new File(["datos"], "citas.csv", { type: "text/csv" }));
    await userEvent.click(screen.getByRole("button", { name: "Importar archivo" }));
    expect(screen.getByRole("button", { name: "Importando…" })).toBeDisabled();
    expect(screen.getByLabelText("Archivo CSV")).toBeDisabled();
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
  });

  it("permite volver a enviar tras un error y no muestra tabla sin rechazos", async () => {
    fetchSimulado.mockRejectedValueOnce(new Error("La carga se interrumpió."))
      .mockResolvedValueOnce(respuesta({ recibidas: 1, aceptadas: 1, rechazadas: 0, detalle_rechazos: [] }));
    montarImportar();
    await userEvent.upload(screen.getByLabelText("Archivo CSV"), new File(["datos"], "citas.csv", { type: "text/csv" }));
    await userEvent.click(screen.getByRole("button", { name: "Importar archivo" }));
    expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Importar archivo" }));
    expect(await screen.findByText("Resultado de la importación")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("borra el resultado previo al cambiar o cancelar la selección", async () => {
    fetchSimulado.mockResolvedValue(respuesta(resultadoImportacion));
    montarImportar();
    await userEvent.upload(screen.getByLabelText("Archivo CSV"), new File(["datos"], "citas.csv", { type: "text/csv" }));
    await userEvent.click(screen.getByRole("button", { name: "Importar archivo" }));
    await screen.findByText("Resultado de la importación");
    fireEvent.change(screen.getByLabelText("Archivo CSV"), { target: { files: [] } });
    expect(screen.queryByText("Resultado de la importación")).not.toBeInTheDocument();
  });
});

describe("Ranuras y transiciones existentes (RF-009, RF-011, RF-019)", () => {
  it("publica las rutas de lectura y restringe la importación a escritores", () => {
    expect(rutas.map((ruta) => ruta.ruta)).toEqual(["/citas", "/citas/nueva", "/citas/importar", "/citas/:id"]);
    expect(rutas[0].roles).toContain("TECNICO_IA");
    expect(rutas[1].roles).toEqual(ROLES_ESCRITURA);
    expect(menu.find((entrada) => entrada.ruta === "/citas")?.roles).toContain("TECNICO_IA");
    expect(menu.find((entrada) => entrada.ruta === "/citas/importar")?.roles).not.toContain("TECNICO_IA");
  });

  it("mantiene los estados existentes y deja los finales sin transiciones", () => {
    expect(ESTADOS).toEqual(["RECIBIDA", "CONFIRMADA", "REPROGRAMADA", "CANCELADA", "LIBERADA", "ATENDIDA", "NO_SHOW"]);
    expect(TRANSICIONES.RECIBIDA).toContain("CONFIRMADA");
    expect(TRANSICIONES.CONFIRMADA).not.toContain("CONFIRMADA");
    for (const final of ["CANCELADA", "LIBERADA", "ATENDIDA", "NO_SHOW"] as const) expect(TRANSICIONES[final]).toEqual([]);
  });
});
