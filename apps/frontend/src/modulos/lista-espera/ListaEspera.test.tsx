import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Pagina, Rol, Usuario } from "../../nucleo/api/tipos";
import { ContextoSesion, type ContextoAuth } from "../../nucleo/auth/contexto";
import ListaEspera from "./ListaEspera";
import type { CandidatoOut } from "./tipos";

// RF-069 a RF-072, RN05, RNF-007, RNF-016 y RNF-028: datos sintéticos,
// respuestas HTTP contractuales y permisos reales del contexto compartido.
const candidato: CandidatoOut = {
  id_candidato: 11, paciente_anon_id: "PAC-SIM-0011", especialidad_req: "CARDIOLOGIA",
  franja_preferida: "MANANA", estado_candidato: "ACTIVO", prioridad_registro: 77,
  fecha_registro: "2026-10-21T10:00:00-05:00",
};
const fetchSimulado = vi.fn<typeof fetch>();

function respuesta(datos: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(datos), { status, headers: { "Content-Type": "application/json" } });
}
function pagina(items: CandidatoOut[] = [candidato], total = items.length, limite = 50, desplazamiento = 0): Pagina<CandidatoOut> {
  return { items, total, limite, desplazamiento };
}
function simular(items = [candidato], total = items.length) {
  fetchSimulado.mockImplementation((entrada, opciones) => {
    const url = new URL(String(entrada));
    if (!opciones?.method || opciones.method === "GET") return Promise.resolve(respuesta(pagina(items, total, Number(url.searchParams.get("limite") || 50), Number(url.searchParams.get("desplazamiento") || 0))));
    const cuerpo = JSON.parse(String(opciones.body)) as Record<string, unknown>;
    return Promise.resolve(respuesta({ ...candidato, ...cuerpo }, opciones.method === "POST" ? 201 : 200));
  });
}
function peticiones(metodo: string) {
  return fetchSimulado.mock.calls.filter(([, opciones]) => opciones?.method === metodo);
}
function Ubicacion() {
  const { pathname, search } = useLocation();
  return <output aria-label="URL actual">{pathname}{search}</output>;
}
function montar(rol: Rol = "RECEPCION", ruta = "/lista-espera") {
  const usuario: Usuario = { id_usuario: 1, nombre_completo: "Operador sintético", correo_institucional: "operador@predicitas.crp", rol, activo: true, creado_en: "2026-10-18T10:00:00-05:00", actualizado_en: null };
  const contexto: ContextoAuth = { usuario, cargando: false, mensajeSesion: "", iniciarSesion: vi.fn(), cerrarSesion: vi.fn(), tieneRol: vi.fn((...roles: Rol[]) => roles.includes(rol)) };
  return { ...render(<ContextoSesion.Provider value={contexto}><MemoryRouter initialEntries={[ruta]}><Ubicacion /><ListaEspera /></MemoryRouter></ContextoSesion.Provider>), contexto };
}
async function esperarLista() {
  await screen.findByRole("rowheader", { name: candidato.paciente_anon_id });
}
async function completarRegistro() {
  const formulario = within(screen.getByRole("form", { name: "Registrar candidato" }));
  await userEvent.type(formulario.getByLabelText("Identificador del paciente"), " PAC-SIM-0099 ");
  await userEvent.selectOptions(formulario.getByLabelText("Especialidad requerida"), "PEDIATRIA");
  await userEvent.selectOptions(formulario.getByLabelText("Franja preferida"), "INDIFERENTE");
}
async function abrirEdicion() {
  await esperarLista();
  await userEvent.click(screen.getByRole("button", { name: `Cambiar franja de ${candidato.paciente_anon_id}` }));
}
function fallarMutacion(codigo: string, status: number, campos: Record<string, string> = {}) {
  fetchSimulado.mockImplementation((entrada, opciones) => {
    const url = new URL(String(entrada));
    return Promise.resolve(opciones?.method === "GET"
      ? respuesta(pagina([candidato], 1, Number(url.searchParams.get("limite") || 50)))
      : respuesta({ error: { codigo, mensaje: "Revisa los campos indicados.", campos } }, status));
  });
}
beforeEach(() => { fetchSimulado.mockReset(); vi.stubGlobal("fetch", fetchSimulado); sessionStorage.clear(); simular(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Lista de espera M06-V01: consulta y permisos (RF-072, RNF-028)", () => {
  it("muestra carga y bloquea los filtros mientras espera", () => {
    fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined));
    montar();
    expect(screen.getByText("Cargando lista de espera…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeDisabled();
  });

  it.each<Rol>(["ADMINISTRADOR", "RECEPCION"])("permite gestionar al rol %s y conserva el orden del servidor", async (rol) => {
    const segundo: CandidatoOut = { ...candidato, id_candidato: 12, paciente_anon_id: "PAC-SIM-0012", especialidad_req: "PEDIATRIA", prioridad_registro: 3, franja_preferida: "INDIFERENTE" };
    simular([candidato, segundo]);
    const { contexto } = montar(rol);
    await esperarLista();
    expect(contexto.tieneRol).toHaveBeenCalledWith("ADMINISTRADOR", "RECEPCION");
    const filas = within(screen.getByRole("table")).getAllByRole("rowheader");
    expect(filas.map((fila) => fila.textContent)).toEqual([candidato.paciente_anon_id, segundo.paciente_anon_id]);
    expect(screen.getByRole("columnheader", { name: "Orden de inscripción" })).toBeInTheDocument();
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/score|urgencia|prioridad clínica/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("21/10/26, 10:00 a. m.")).toHaveLength(2);
    expect(screen.getByRole("region", { name: "Candidatos de la lista de espera" })).toHaveAttribute("tabindex", "0");
  });

  it("impide montar el módulo y consultar datos a TECNICO_IA", () => {
    montar("TECNICO_IA");
    expect(screen.getByRole("alert")).toHaveTextContent("No tienes permiso para esta sección.");
    expect(screen.queryByRole("heading", { name: "Lista de espera" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Registrar candidato" })).not.toBeInTheDocument();
    expect(fetchSimulado).not.toHaveBeenCalled();
  });

  it("presenta el estado vacío y la paginación deshabilitada", async () => {
    simular([]);
    montar();
    expect(await screen.findByText("No hay candidatos con estos filtros.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
    expect(screen.getByText("Página 1 de 1")).toBeInTheDocument();
  });

  it("muestra el error de consulta y permite recuperarse", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta({ error: { codigo: "ERROR_INTERNO", mensaje: "La lista no está disponible." } }, 500));
    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent("La lista no está disponible.");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar lista" }));
    await esperarLista();
  });

  it("recupera los cuatro filtros de la URL y aplica cambios reiniciando el desplazamiento", async () => {
    montar("RECEPCION", "/lista-espera?q=PAC-SIM&especialidad_req=CARDIOLOGIA&franja_preferida=MANANA&estado_candidato=ACTIVO&desplazamiento=10&limite=10");
    await esperarLista();
    const filtros = within(screen.getByRole("form", { name: "Filtrar candidatos" }));
    expect(filtros.getByLabelText("Buscar paciente")).toHaveValue("PAC-SIM");
    expect(filtros.getByLabelText("Especialidad")).toHaveValue("CARDIOLOGIA");
    expect(filtros.getByLabelText("Franja")).toHaveValue("MANANA");
    expect(filtros.getByLabelText("Estado del candidato")).toHaveValue("ACTIVO");
    await userEvent.clear(filtros.getByLabelText("Buscar paciente"));
    await userEvent.type(filtros.getByLabelText("Buscar paciente"), " PAC-SIM-00 ");
    await userEvent.selectOptions(filtros.getByLabelText("Especialidad"), "PEDIATRIA");
    await userEvent.selectOptions(filtros.getByLabelText("Franja"), "INDIFERENTE");
    await userEvent.selectOptions(filtros.getByLabelText("Estado del candidato"), "CONTACTADO");
    await userEvent.click(filtros.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(peticiones("GET")).toHaveLength(2));
    const parametros = new URL(String(peticiones("GET").at(-1)?.[0])).searchParams;
    expect(Object.fromEntries(parametros)).toEqual({ q: "PAC-SIM-00", especialidad_req: "PEDIATRIA", franja_preferida: "INDIFERENTE", estado_candidato: "CONTACTADO", limite: "10", desplazamiento: "0" });
    expect(screen.getByLabelText("URL actual").textContent).toContain("estado_candidato=CONTACTADO");
  });

  it("pagina con los filtros y limpia el borrador aunque la URL ya esté vacía", async () => {
    simular([candidato], 101);
    montar();
    await esperarLista();
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("Página 2 de 3")).toBeInTheDocument();
    expect(new URL(String(peticiones("GET").at(-1)?.[0])).searchParams.get("desplazamiento")).toBe("50");
    await userEvent.click(screen.getByRole("button", { name: "Anterior" }));
    expect(await screen.findByText("Página 1 de 3")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Limpiar filtros" }));
    await esperarLista();
    await userEvent.type(screen.getByLabelText("Buscar paciente"), "PAC-SIM");
    await userEvent.click(screen.getByRole("button", { name: "Limpiar filtros" }));
    expect(screen.getByLabelText("Buscar paciente")).toHaveValue("");
    expect(screen.getByLabelText("URL actual")).toHaveTextContent(/^\/lista-espera$/);
  });

  it("normaliza valores de paginación inválidos y permite actualizar la consulta", async () => {
    montar("RECEPCION", "/lista-espera?limite=201&desplazamiento=-1");
    await esperarLista();
    expect(new URL(String(peticiones("GET")[0][0])).searchParams.get("limite")).toBe("50");
    expect(new URL(String(peticiones("GET")[0][0])).searchParams.get("desplazamiento")).toBe("0");
    await userEvent.click(screen.getByRole("button", { name: "Actualizar lista" }));
    await waitFor(() => expect(peticiones("GET")).toHaveLength(2));
  });
});

describe("Registro de candidato (RF-069, RF-070, RN05)", () => {
  it("valida los tres campos y no transmite un registro incompleto", async () => {
    montar();
    await userEvent.click(screen.getByRole("button", { name: "Registrar candidato" }));
    expect(screen.getByLabelText("Identificador del paciente")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Especialidad requerida")).toHaveAccessibleDescription("Selecciona una especialidad del piloto.");
    expect(screen.getByLabelText("Franja preferida")).toHaveAccessibleDescription("Selecciona una franja preferida.");
    expect(peticiones("POST")).toHaveLength(0);
  });

  it("valida la longitud del identificador sin depender del límite HTML", async () => {
    montar();
    await completarRegistro();
    fireEvent.change(screen.getByLabelText("Identificador del paciente"), { target: { value: "A".repeat(51) } });
    await userEvent.click(screen.getByRole("button", { name: "Registrar candidato" }));
    expect(screen.getByLabelText("Identificador del paciente")).toHaveAttribute("aria-invalid", "true");
    expect(peticiones("POST")).toHaveLength(0);
  });

  it("envía solo los campos contractuales y muestra el orden asignado por el servidor", async () => {
    montar();
    await completarRegistro();
    await userEvent.click(screen.getByRole("button", { name: "Registrar candidato" }));
    expect(await screen.findByText(/Candidato registrado. Orden de inscripción asignado por el sistema: 77/)).toBeInTheDocument();
    expect(JSON.parse(String(peticiones("POST")[0][1]?.body))).toEqual({ paciente_anon_id: "PAC-SIM-0099", especialidad_req: "PEDIATRIA", franja_preferida: "INDIFERENTE" });
    expect(screen.getByLabelText("Identificador del paciente")).toHaveValue("");
    expect(screen.getByLabelText("Especialidad requerida")).toHaveValue("");
    expect(peticiones("GET").length).toBeGreaterThan(1);
  });

  it("bloquea los controles y evita envíos duplicados mientras registra", async () => {
    fetchSimulado.mockImplementation((_entrada, opciones) => opciones?.method === "POST" ? new Promise<Response>(() => undefined) : Promise.resolve(respuesta(pagina())));
    montar();
    await completarRegistro();
    const formulario = screen.getByRole("form", { name: "Registrar candidato" });
    fireEvent.submit(formulario);
    fireEvent.submit(formulario);
    expect(screen.getByRole("button", { name: "Registrando…" })).toBeDisabled();
    expect(peticiones("POST")).toHaveLength(1);
  });

  it("explica CANDIDATO_DUPLICADO y vincula el conflicto al identificador", async () => {
    fallarMutacion("CANDIDATO_DUPLICADO", 409);
    montar();
    await completarRegistro();
    await userEvent.click(screen.getByRole("button", { name: "Registrar candidato" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El paciente ya está activo o contactado en la lista de espera de esa especialidad.");
    expect(screen.getByLabelText("Identificador del paciente")).toHaveAttribute("aria-invalid", "true");
    await userEvent.type(screen.getByLabelText("Identificador del paciente"), "A");
    expect(screen.getByLabelText("Identificador del paciente")).toHaveAttribute("aria-invalid", "false");
  });

  it("asocia VALIDACION con cada campo enviado por la API", async () => {
    fallarMutacion("VALIDACION", 422, { paciente_anon_id: "Identificador no válido.", especialidad_req: "Especialidad no admitida.", franja_preferida: "Franja no admitida." });
    montar();
    await completarRegistro();
    await userEvent.click(screen.getByRole("button", { name: "Registrar candidato" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Revisa los campos indicados.");
    expect(screen.getByLabelText("Especialidad requerida")).toHaveAccessibleDescription("Especialidad no admitida.");
    expect(screen.getByLabelText("Franja preferida")).toHaveAccessibleDescription("Franja no admitida.");
  });

  it("presenta SIN_PERMISO devuelto por el servidor", async () => {
    fallarMutacion("SIN_PERMISO", 403);
    montar();
    await completarRegistro();
    await userEvent.click(screen.getByRole("button", { name: "Registrar candidato" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Tu rol no tiene permiso para gestionar la lista de espera y la reasignación.");
  });

  it("explica una respuesta de registro sin cuerpo contractual", async () => {
    fetchSimulado.mockImplementation((_entrada, opciones) => Promise.resolve(opciones?.method === "POST" ? respuesta(null, 204) : respuesta(pagina())));
    montar();
    await completarRegistro();
    await userEvent.click(screen.getByRole("button", { name: "Registrar candidato" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El servidor no devolvió el candidato registrado.");
  });
});

describe("Disponibilidad y desistimiento (RF-071)", () => {
  it("edita únicamente franja_preferida y actualiza el listado", async () => {
    montar();
    await abrirEdicion();
    expect(screen.getByLabelText("Nueva franja preferida")).toHaveFocus();
    await userEvent.selectOptions(screen.getByLabelText("Nueva franja preferida"), "TARDE");
    await userEvent.click(screen.getByRole("button", { name: "Guardar franja" }));
    expect(await screen.findByText("Franja preferida actualizada.")).toBeInTheDocument();
    expect(String(peticiones("PATCH")[0][0])).toMatch(/\/lista-espera\/11$/);
    expect(JSON.parse(String(peticiones("PATCH")[0][1]?.body))).toEqual({ franja_preferida: "TARDE" });
    expect(screen.queryByRole("button", { name: "Guardar franja" })).not.toBeInTheDocument();
  });

  it("cancela la edición, devuelve el foco y no escribe en la API", async () => {
    montar();
    await abrirEdicion();
    await userEvent.click(screen.getByRole("button", { name: "Cancelar edición" }));
    expect(peticiones("PATCH")).toHaveLength(0);
    expect(screen.getByRole("button", { name: `Cambiar franja de ${candidato.paciente_anon_id}` })).toHaveFocus();
  });

  it("rechaza una franja ajena al catálogo antes de enviar", async () => {
    montar();
    await abrirEdicion();
    fireEvent.change(screen.getByLabelText("Nueva franja preferida"), { target: { value: "" } });
    await userEvent.click(screen.getByRole("button", { name: "Guardar franja" }));
    expect(screen.getByLabelText("Nueva franja preferida")).toHaveAccessibleDescription("Selecciona una franja preferida.");
    expect(peticiones("PATCH")).toHaveLength(0);
  });

  it("marca desistido mediante el único estado admitido por PATCH", async () => {
    montar();
    await esperarLista();
    await userEvent.click(screen.getByRole("button", { name: `Marcar desistido a ${candidato.paciente_anon_id}` }));
    expect(await screen.findByText("Candidato marcado como desistido.")).toBeInTheDocument();
    expect(JSON.parse(String(peticiones("PATCH")[0][1]?.body))).toEqual({ estado_candidato: "DESISTIDO" });
  });

  it.each([
    ["CANDIDATO_CON_OFERTA", 409, "El candidato tiene una oferta vigente. Cierra la oferta antes de continuar."],
    ["CANDIDATO_ASIGNADO", 409, "El candidato ya está asignado y no admite ese cambio."],
    ["NO_ENCONTRADO", 404, "No se encontró el registro solicitado. Actualiza la vista para consultar los datos vigentes."],
  ] as const)("explica %s al intentar desistir y conserva el listado", async (codigo, status, mensaje) => {
    fallarMutacion(codigo, status);
    montar();
    await esperarLista();
    await userEvent.click(screen.getByRole("button", { name: `Marcar desistido a ${candidato.paciente_anon_id}` }));
    expect(await screen.findByRole("alert")).toHaveTextContent(mensaje);
    expect(screen.getByRole("rowheader", { name: candidato.paciente_anon_id })).toBeInTheDocument();
  });

  it("explica VALIDACION en el campo de edición sin perder la selección", async () => {
    fallarMutacion("VALIDACION", 422, { franja_preferida: "La franja ya no está disponible." });
    montar();
    await abrirEdicion();
    await userEvent.click(screen.getByRole("button", { name: "Guardar franja" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Revisa los campos indicados.");
    expect(screen.getByLabelText("Nueva franja preferida")).toHaveAccessibleDescription("La franja ya no está disponible.");
    await userEvent.selectOptions(screen.getByLabelText("Nueva franja preferida"), "INDIFERENTE");
    expect(screen.getByLabelText("Nueva franja preferida")).toHaveAttribute("aria-invalid", "false");
  });

  it("bloquea edición y otras acciones durante el PATCH y no duplica el envío", async () => {
    fetchSimulado.mockImplementation((_entrada, opciones) => opciones?.method === "PATCH" ? new Promise<Response>(() => undefined) : Promise.resolve(respuesta(pagina())));
    montar();
    await abrirEdicion();
    const formulario = screen.getByRole("form", { name: `Cambiar franja de ${candidato.paciente_anon_id}` });
    fireEvent.submit(formulario);
    fireEvent.submit(formulario);
    expect(screen.getByRole("button", { name: "Guardando…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Registrar candidato" })).toBeDisabled();
    expect(screen.getByRole("button", { name: `Marcar desistido a ${candidato.paciente_anon_id}` })).toBeDisabled();
    expect(peticiones("PATCH")).toHaveLength(1);
  });

  it("explica una respuesta de actualización sin candidato", async () => {
    fetchSimulado.mockImplementation((_entrada, opciones) => Promise.resolve(opciones?.method === "PATCH" ? respuesta(null, 204) : respuesta(pagina())));
    montar();
    await abrirEdicion();
    await userEvent.click(screen.getByRole("button", { name: "Guardar franja" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El servidor no devolvió el candidato actualizado.");
  });

  it("presenta estados finales sin acciones y mantiene la gestión de contactados", async () => {
    simular([
      { ...candidato, estado_candidato: "ASIGNADO" },
      { ...candidato, id_candidato: 12, paciente_anon_id: "PAC-SIM-0012", estado_candidato: "DESISTIDO" },
      { ...candidato, id_candidato: 13, paciente_anon_id: "PAC-SIM-0013", estado_candidato: "CONTACTADO" },
    ]);
    montar();
    await esperarLista();
    expect(screen.getAllByText("Sin acciones disponibles")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: `Cambiar franja de ${candidato.paciente_anon_id}` })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cambiar franja de PAC-SIM-0013" })).toBeInTheDocument();
  });
});
