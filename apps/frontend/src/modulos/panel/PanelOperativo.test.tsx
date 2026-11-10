import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Rol, Usuario } from "../../nucleo/api/tipos";
import { ContextoSesion, type ContextoAuth } from "../../nucleo/auth/contexto";
import { paginaPrueba, respuestaPrueba, resumenPrueba } from "../../pruebas/panel";
import { hoyLima } from "./formato";
import PanelOperativo from "./PanelOperativo";
import type { TipoPendiente } from "./tipos";

function Ubicacion() {
  const l = useLocation(); const navegar = useNavigate();
  return <><output data-testid="ubicacion">{l.pathname}{l.search}</output><output data-testid="estado">{JSON.stringify(l.state)}</output><button onClick={() => navegar(-1)}>Atrás de prueba</button></>;
}
type Servidor = (url: URL, opciones?: RequestInit) => Response | Promise<Response>;
function mostrar({ ruta = "/panel?fecha=2026-11-09", rol = "RECEPCION", servidor }: { ruta?: string; rol?: Rol; servidor?: Servidor } = {}) {
  const usuario: Usuario = { id_usuario: 1, nombre_completo: "Operador sintético", correo_institucional: "panel@predicitas.crp", rol, activo: true, creado_en: "2026-11-09T09:00:00-05:00", actualizado_en: null };
  const sesion: ContextoAuth = { usuario, cargando: false, mensajeSesion: "", iniciarSesion: vi.fn(), cerrarSesion: vi.fn(), tieneRol: (...roles) => roles.includes(rol) };
  const fetch = vi.fn<typeof window.fetch>(async (entrada, opciones) => {
    const url = new URL(String(entrada));
    if (servidor) return servidor(url, opciones);
    const fecha = url.searchParams.get("fecha")!;
    const especialidad = url.searchParams.get("especialidad");
    if (url.pathname === "/panel/resumen") return respuestaPrueba({ ...resumenPrueba(), fecha, especialidad });
    return respuestaPrueba({ ...paginaPrueba(url.searchParams.get("tipo") as TipoPendiente), fecha, especialidad, desplazamiento: Number(url.searchParams.get("desplazamiento")) });
  });
  vi.stubGlobal("fetch", fetch);
  render(<ContextoSesion.Provider value={sesion}><MemoryRouter initialEntries={[ruta]}><Routes>
    <Route path="/panel" element={<PanelOperativo />} /><Route path="/citas/:id" element={<h1>Detalle de destino</h1>} />
    <Route path="/intervenciones/:id" element={<h1>Detalle de destino</h1>} /><Route path="/cupos/:id" element={<h1>Detalle de destino</h1>} />
  </Routes><Ubicacion /></MemoryRouter></ContextoSesion.Provider>);
  return fetch;
}
const esperarLista = () => screen.findByRole("link", { name: "Ver cita" });
afterEach(() => vi.useRealTimers());

describe("Panel Operativo conectado", () => {
  it("oculta el acceso al reporte para Administración", async () => {
    mostrar({ rol: "ADMINISTRADOR" });
    await esperarLista();
    expect(screen.queryByRole("link", { name: "Reporte diario" })).not.toBeInTheDocument();
  });
  it("normaliza la URL, carga solo dos recursos y conserva las unidades", async () => {
    const fetch = mostrar(); await esperarLista();
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("ubicacion")).toHaveTextContent("tipo=CITAS_SIN_INTERVENCION&desplazamiento=0");
    expect(screen.getByText("1 de 4 cupos recuperados")).toBeInTheDocument();
    expect(screen.getByText(/Resumen consultado a las 09:00/)).toBeInTheDocument();
    expect(fetch.mock.calls.every(([, opciones]) => !opciones?.method || opciones.method === "GET")).toBe(true);
  });
  it("solo cambia el universo al aplicar y actualiza usando filtros ya aplicados", async () => {
    const fetch = mostrar(); await esperarLista();
    fireEvent.change(screen.getByLabelText("Fecha de la jornada"), { target: { value: "2026-11-10" } });
    await userEvent.selectOptions(screen.getByLabelText("Especialidad"), "PEDIATRIA");
    expect(fetch).toHaveBeenCalledTimes(2);
    await userEvent.click(screen.getByRole("button", { name: "Actualizar" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(4));
    expect(new URL(String(fetch.mock.calls[2][0])).searchParams.get("fecha")).toBe("2026-11-09");
    await esperarLista();
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(6));
    expect(screen.getByTestId("ubicacion")).toHaveTextContent("fecha=2026-11-10&especialidad=PEDIATRIA");
    expect(new URL(String(fetch.mock.calls[4][0])).searchParams.has("tipo")).toBe(false);
  });
  it("aplicar los mismos filtros actualiza ambos recursos", async () => {
    const fetch = mostrar(); await esperarLista();
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(4));
  });
  it("cambiar categoría solo solicita su listado y conserva fecha/especialidad", async () => {
    const fetch = mostrar({ ruta: "/panel?fecha=2026-11-09&especialidad=CARDIOLOGIA" }); await esperarLista();
    await userEvent.click(screen.getByRole("button", { name: /Intervenciones sin respuesta/ }));
    expect(await screen.findByRole("link", { name: "Ver seguimiento" })).toHaveAttribute("href", "/intervenciones/17");
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(new URL(String(fetch.mock.calls[2][0])).pathname).toBe("/panel/pendientes");
    expect(screen.getByTestId("ubicacion")).toHaveTextContent("especialidad=CARDIOLOGIA&tipo=INTERVENCIONES_SIN_RESPUESTA&desplazamiento=0");
    await userEvent.click(screen.getByRole("button", { name: /Ofertas en curso/ }));
    expect(await screen.findByRole("link", { name: "Ver cupo" })).toHaveAttribute("href", "/cupos/42");
  });
  it("conserva categoría y especialidad al aplicar Hoy, restaurando contexto con Atrás", async () => {
    vi.useFakeTimers({ toFake: ["Date"] }); vi.setSystemTime(new Date("2026-11-10T02:00:00Z"));
    mostrar({ ruta: "/panel?fecha=2026-11-08&especialidad=PEDIATRIA&tipo=OFERTAS_EN_CURSO&desplazamiento=20" });
    await screen.findByRole("link", { name: "Ver cupo" });
    await userEvent.click(screen.getByRole("button", { name: "Hoy" }));
    await waitFor(() => expect(screen.getByTestId("ubicacion")).toHaveTextContent("fecha=2026-11-09&especialidad=PEDIATRIA&tipo=OFERTAS_EN_CURSO&desplazamiento=0"));
    await userEvent.click(screen.getByRole("button", { name: "Atrás de prueba" }));
    await waitFor(() => expect(screen.getByLabelText("Fecha de la jornada")).toHaveValue("2026-11-08"));
  });
  it("fija la fecha de Lima al entrar sin filtros", async () => {
    mostrar({ ruta: "/panel" }); await esperarLista();
    expect(screen.getByLabelText("Fecha de la jornada")).toHaveValue(hoyLima());
  });
  it.each(["fecha=2026-02-30", "fecha=2026-11-09&especialidad=OTRA"]) ("no consulta un universo inválido %s", async query => {
    const fetch = mostrar({ ruta: `/panel?${query}` });
    expect(await screen.findByRole("alert")).toHaveTextContent(/Selecciona/);
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Fecha de la jornada"), { target: { value: "2026-11-09" } });
    await userEvent.selectOptions(screen.getByLabelText("Especialidad"), "");
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await esperarLista(); expect(fetch).toHaveBeenCalledTimes(2);
  });
  it("deniega localmente al Técnico IA sin llamadas de datos", () => {
    const fetch = mostrar({ rol: "TECNICO_IA" });
    expect(screen.getByRole("alert")).toHaveTextContent("No tienes permiso");
    expect(fetch).not.toHaveBeenCalled();
  });
  it("falla un recurso sin bloquear el otro, con reintento independiente", async () => {
    let fallar = true;
    const fetch = mostrar({ servidor: url => url.pathname === "/panel/resumen"
      ? respuestaPrueba(fallar ? { error: { codigo: "ERROR_INTERNO", mensaje: "Resumen no disponible" } } : resumenPrueba(), fallar ? 500 : 200)
      : respuestaPrueba(paginaPrueba()) });
    await esperarLista();
    expect(screen.getByRole("alert")).toHaveTextContent("Resumen no disponible");
    expect(screen.queryByText("Cupos disponibles")).not.toBeInTheDocument();
    fallar = false;
    await userEvent.click(screen.getByRole("button", { name: "Reintentar resumen" }));
    expect(await screen.findByText("Cupos disponibles")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(3);
  });
  it("detecta respuestas incompletas sin sustituirlas por ceros", async () => {
    mostrar({ servidor: () => respuestaPrueba({}) });
    expect(await screen.findAllByText(/El servidor no devolvió los datos esperados/)).toHaveLength(2);
    expect(screen.queryByText("0 %")).not.toBeInTheDocument();
  });
  it("preserva el contexto al abrir el detalle", async () => {
    mostrar({ ruta: "/panel?fecha=2026-11-09&tipo=CITAS_SIN_INTERVENCION&desplazamiento=20" });
    await userEvent.click(await esperarLista());
    expect(screen.getByRole("heading", { name: "Detalle de destino" })).toBeInTheDocument();
    expect(screen.getByTestId("estado")).toHaveTextContent('"volver":"/panel?fecha=2026-11-09&tipo=CITAS_SIN_INTERVENCION&desplazamiento=20"');
  });
  it("ignora una respuesta antigua y aborta al cambiar de categoría", async () => {
    let responder: ((r: Response) => void) | undefined;
    let signal: AbortSignal | undefined;
    mostrar({ servidor: (url, opciones) => {
      if (url.pathname === "/panel/resumen") return respuestaPrueba(resumenPrueba());
      if (url.searchParams.get("tipo") === "CITAS_SIN_INTERVENCION") { signal = opciones?.signal ?? undefined; return new Promise<Response>(r => { responder = r; }); }
      return respuestaPrueba(paginaPrueba("OFERTAS_EN_CURSO"));
    } });
    await screen.findByText("Cupos disponibles");
    await userEvent.click(screen.getByRole("button", { name: /Ofertas en curso/ }));
    await screen.findByRole("link", { name: "Ver cupo" });
    expect(signal?.aborted).toBe(true);
    await act(async () => responder?.(respuestaPrueba(paginaPrueba())));
    expect(screen.queryByRole("link", { name: "Ver cita" })).not.toBeInTheDocument();
  });
});
