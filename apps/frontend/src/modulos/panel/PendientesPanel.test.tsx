import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { paginaPrueba, resumenPrueba } from "../../pruebas/panel";
import PendientesPanel from "./PendientesPanel";
import { TIPOS } from "./tipos";

function props() { return { tipo: TIPOS[0], resumen: resumenPrueba(), datos: paginaPrueba(), cargando: false, error: "", volver: "/panel?fecha=2026-11-09", seleccionar: vi.fn(), paginar: vi.fn(), reintentar: vi.fn() }; }
describe("bandeja tipada de pendientes", () => {
  it.each(TIPOS)("muestra las columnas y el enlace correspondientes a %s", tipo => {
    const p = { ...props(), tipo, datos: paginaPrueba(tipo) };
    render(<MemoryRouter><PendientesPanel {...p} /></MemoryRouter>);
    const ruta = tipo === "CITAS_SIN_INTERVENCION" ? "/citas/101" : tipo === "INTERVENCIONES_SIN_RESPUESTA" ? "/intervenciones/17" : "/cupos/42";
    expect(screen.getByRole("link")).toHaveAttribute("href", ruta);
    if (tipo === "INTERVENCIONES_SIN_RESPUESTA") expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  });
  it("pagina usando total del servidor y conserva el orden de filas", async () => {
    const p = props(); p.datos.total = 42;
    render(<MemoryRouter><PendientesPanel {...p} /></MemoryRouter>);
    expect(screen.getByText("Mostrando 1–1 de 42")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(p.paginar).toHaveBeenCalledWith(20);
  });
  it("distingue página fuera de rango de categoría vacía", async () => {
    const p = props(); p.datos = { ...p.datos, total: 3, desplazamiento: 20, items: [] };
    const { rerender } = render(<MemoryRouter><PendientesPanel {...p} /></MemoryRouter>);
    expect(screen.getByText("Esta página ya no tiene resultados.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ir a la primera página" }));
    expect(p.paginar).toHaveBeenCalledWith(0);
    rerender(<MemoryRouter><PendientesPanel {...p} datos={{ ...p.datos, total: 0 }} /></MemoryRouter>);
    expect(screen.getByText("No hay citas sin intervención con estos filtros.")).toBeInTheDocument();
  });
  it("conserva carga/error independientes y avisa si difiere el total", async () => {
    const p = props();
    const { rerender } = render(<MemoryRouter><PendientesPanel {...p} cargando /></MemoryRouter>);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    rerender(<MemoryRouter><PendientesPanel {...p} datos={null} error="Sin conexión" /></MemoryRouter>);
    expect(screen.getByRole("alert")).toHaveTextContent("Sin conexión");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar pendientes" }));
    expect(p.reintentar).toHaveBeenCalledOnce();
    rerender(<MemoryRouter><PendientesPanel {...p} /></MemoryRouter>);
    expect(screen.getByText(/Los datos pueden haber cambiado/)).toBeInTheDocument();
  });
});
