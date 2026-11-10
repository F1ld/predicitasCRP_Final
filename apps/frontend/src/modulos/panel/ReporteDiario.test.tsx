import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { respuestaPrueba } from "../../pruebas/panel";
import ReporteDiario from "./ReporteDiario";

const RUTA = "/panel/reporte-diario";
const FECHA = "2026-11-09";
const fila = {
  hora: "13:00:00", id_cita_externa: "REP-01", especialidad: "CARDIOLOGIA", medico: "Profesional sintético",
  antelacion_dias: 5, probabilidad_no_show: 0, nivel_riesgo: "BAJO", estado_intervencion: "ENVIADA",
  respuesta_paciente: null,
};

function vacio(url: URL) {
  return {
    fecha: url.searchParams.get("fecha"),
    filtros: { especialidad: url.searchParams.get("especialidad"), nivel_riesgo: url.searchParams.get("nivel_riesgo") },
    total: 0, grupos: [],
  };
}

function Ubicacion() {
  const { search } = useLocation();
  return <output data-testid="consulta">{search}</output>;
}

function mostrar(servidor = (url: URL): Response | Promise<Response> => respuestaPrueba(vacio(url)), ruta = `${RUTA}?fecha=${FECHA}`) {
  const fetch = vi.fn<typeof window.fetch>(async entrada => servidor(new URL(String(entrada))));
  vi.stubGlobal("fetch", fetch);
  render(<MemoryRouter initialEntries={[ruta]}><ReporteDiario /><Ubicacion /></MemoryRouter>);
  return fetch;
}

afterEach(() => vi.useRealTimers());

it("fija hoy en Lima y solo aplica filtros al enviar el formulario", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-11-10T02:00:00Z"));
  const fetch = mostrar(undefined, RUTA);
  await screen.findByText(/No hay citas/);
  expect(screen.getByLabelText("Fecha de la jornada")).toHaveValue(FECHA);
  expect(screen.getByRole("link", { name: "Volver al panel operativo" })).toHaveAttribute("href", "/panel");
  await userEvent.selectOptions(screen.getByLabelText("Especialidad"), "PEDIATRIA");
  await userEvent.selectOptions(screen.getByLabelText("Nivel de riesgo"), "ALTO");
  expect(fetch).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
  expect(screen.getByTestId("consulta")).toHaveTextContent("?fecha=2026-11-09&especialidad=PEDIATRIA&nivel_riesgo=ALTO");
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  const api = new URL(String(fetch.mock.calls[1][0]));
  expect(api.pathname + api.search).toBe("/reportes/rep-01?fecha=2026-11-09&especialidad=PEDIATRIA&nivel_riesgo=ALTO");
});

it("bloquea una fecha inválida y permite corregirla", async () => {
  const fetch = mostrar(undefined, `${RUTA}?fecha=2026-02-30`);
  expect(screen.getByText(/Selecciona una fecha válida/)).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Fecha de la jornada"), { target: { value: FECHA } });
  await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
  expect(await screen.findByText(/No hay citas/)).toBeInTheDocument();
});

it("respeta los grupos, la hora de Lima y los valores cero y ausentes", async () => {
  mostrar(url => respuestaPrueba({
    ...vacio(url), total: 2, grupos: [{
      especialidad: "CARDIOLOGIA", franja_horaria: "TARDE", subtotal: 2, filas: [
        fila, { ...fila, id_cita_externa: "REP-02", probabilidad_no_show: null, nivel_riesgo: null, estado_intervencion: null },
      ],
    }],
  }));
  expect(await screen.findByRole("table", { name: /Cardiología.*Tarde.*Subtotal: 2/ })).toBeInTheDocument();
  expect(screen.getByText("Total de citas: 2")).toBeInTheDocument();
  expect(screen.getAllByText("13:00")).toHaveLength(2);
  for (const texto of ["0 %", "Sin evaluación", "Sin intervención", "Sin respuesta"]) {
    expect(screen.getByText(texto)).toBeInTheDocument();
  }
});

it("distingue el error HTTP, el contrato incompatible y el resultado vacío al reintentar", async () => {
  let llamadas = 0;
  const fetch = mostrar(url => {
    llamadas++;
    if (llamadas === 1) return new Response(JSON.stringify({ error: { codigo: "NO_DISPONIBLE", mensaje: "Servicio no disponible" } }), { status: 503 });
    return respuestaPrueba({ ...vacio(url), total: llamadas === 2 ? 1 : 0 });
  });
  expect(await screen.findByText("Servicio no disponible")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Reintentar reporte" }));
  expect(await screen.findByText(/no devolvió un reporte válido/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Reintentar reporte" }));
  expect(await screen.findByText(/No hay citas/)).toBeInTheDocument();
  expect(new Set(fetch.mock.calls.map(([url]) => String(url))).size).toBe(1);
});

it("descarta una respuesta anterior que llega tras un cambio de filtros", async () => {
  let responder!: (respuesta: Response) => void;
  let primera!: URL;
  const fetch = mostrar(url => {
    if (url.searchParams.get("fecha") !== FECHA) return respuestaPrueba(vacio(url));
    primera = url;
    return new Promise(resolve => { responder = resolve; });
  });
  expect(await screen.findByText("Cargando reporte diario…")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Fecha de la jornada"), { target: { value: "2026-11-10" } });
  await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
  expect(await screen.findByText(/No hay citas/)).toBeInTheDocument();
  await act(async () => responder(respuestaPrueba({ ...vacio(primera), total: 1 })));
  expect(screen.getByText(/No hay citas/)).toBeInTheDocument();
  expect(fetch.mock.calls[0][1]?.signal?.aborted).toBe(true);
});
