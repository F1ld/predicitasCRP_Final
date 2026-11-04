import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Cargando from "./Cargando";
import Mensaje from "./Mensaje";
import EstadoBadge from "./EstadoBadge";
import NivelRiesgoBadge from "./NivelRiesgoBadge";
import RotuloSimulado from "./RotuloSimulado";
import Icono from "./Icono";
import Marca from "./Marca";
import { etiqueta, formatearFechaHora } from "../formato/formato";

// RF-056, RN16, RNF-016, RNF-017: etiquetas, anuncios y fecha local comprensibles.
describe("componentes compartidos", () => {
  it.each(["BAJO", "MEDIO", "ALTO"] as const)("riesgo %s tiene texto además del color", (nivel) => {
    render(<NivelRiesgoBadge nivel={nivel} />);
    expect(screen.getByLabelText(`Riesgo de inasistencia: ${nivel}`)).toHaveTextContent(nivel);
  });
  it("conserva el rótulo exacto del contrato", () => {
    render(<RotuloSimulado />);
    expect(screen.getByText("Resultado simulado: no es desempeño real")).toBeInTheDocument();
  });
  it("anuncia carga y mensajes y no crea un aviso vacío", () => {
    const { rerender } = render(<Mensaje />);
    expect(screen.queryByRole("alert")).toBeNull();
    rerender(<Mensaje>Fallo</Mensaje>);
    expect(screen.getByRole("alert")).toHaveTextContent("Fallo");
    rerender(<Mensaje tipo="exito">Guardado</Mensaje>);
    expect(screen.getByRole("status")).toHaveTextContent("Guardado");
    rerender(<Mensaje tipo="info">Aviso</Mensaje>);
    expect(screen.getByRole("status")).toHaveTextContent("Aviso");
    rerender(<Cargando />);
    expect(screen.getByRole("status")).toHaveTextContent("Cargando…");
  });
  it("muestra identidad, iconos decorativos y estado textual", () => {
    const { container } = render(<><Marca /><Icono nombre="desconocido" /><EstadoBadge estado="CONFIRMADA" /><EstadoBadge estado="FUTURO" /></>);
    expect(screen.getByRole("img", { name: "PrediCitas CRP" })).toHaveAttribute("width", "850");
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("Confirmada")).toBeInTheDocument();
    expect(screen.getByText("FUTURO")).toBeInTheDocument();
  });
  it("muestra fecha en Lima y etiquetas conocidas", () => {
    expect(formatearFechaHora("2026-10-18T02:30:00Z")).toContain("17/10/26");
    expect(formatearFechaHora(null)).toBe("—");
    expect(etiqueta("CARDIOLOGIA")).toBe("Cardiología");
    expect(etiqueta("OTRA")).toBe("OTRA");
    expect(etiqueta(null)).toBe("—");
  });
});
