import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { resumenPrueba } from "../../pruebas/panel";
import { DesglosesPanel, TarjetasPanel } from "./ResumenPanel";

describe("resumen de jornada", () => {
  it("presenta fuentes correctas, unidades distintas y categorías con cero", () => {
    const datos = resumenPrueba();
    render(<><TarjetasPanel datos={datos} /><DesglosesPanel datos={datos} /></>);
    expect(screen.getByText("25 %")).toBeInTheDocument();
    expect(screen.getByText("1 de 4 cupos recuperados")).toBeInTheDocument();
    expect(screen.getByText("4 intervenciones · 3 citas distintas")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Citas por estado" })).getByText("No asistió")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Distribución de riesgo" })).getByText("Sin predicción")).toBeInTheDocument();
    expect(screen.getByText(/Resultado simulado/)).toBeInTheDocument();
  });
  it("distingue tasa nula de recuperación cero", () => {
    const datos = resumenPrueba(); datos.cupos.tasa_recuperacion_pct = null; datos.cupos.total_liberados = 0;
    const { rerender } = render(<TarjetasPanel datos={datos} />);
    expect(screen.getByText("Sin cupos liberados")).toBeInTheDocument();
    expect(screen.queryByText("0 %")).not.toBeInTheDocument();
    datos.cupos.tasa_recuperacion_pct = 0; datos.cupos.total_liberados = 4; datos.cupos.reasignados_confirmados = 0;
    rerender(<TarjetasPanel datos={datos} />);
    expect(screen.getByText("0 %")).toBeInTheDocument();
  });
});
