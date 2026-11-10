import { describe, expect, it } from "vitest";
import { fechaHoraPanel, fechaPanel, horaPanel, hoyLima, numeroPanel, porcentajePanel } from "./formato";

describe("formato del panel en Lima", () => {
  it("mantiene el día previo a medianoche de Lima aunque UTC cambió", () => {
    expect(hoyLima(new Date("2026-11-10T04:59:59Z"))).toBe("2026-11-09");
    expect(hoyLima(new Date("2026-11-10T05:00:00Z"))).toBe("2026-11-10");
    expect(horaPanel("2026-11-10T05:00:00Z")).toBe("00:00");
  });
  it("presenta calendario sin desplazarlo y timestamps con offset", () => {
    expect(fechaPanel("2026-11-09")).toBe("09/11/2026");
    expect(horaPanel("2026-11-09T19:00:00Z")).toBe("14:00");
    expect(fechaHoraPanel(null)).toBe("—");
    expect(fechaHoraPanel("2026-11-08T19:00:00Z")).toContain("14:00");
    expect(fechaHoraPanel("2026-11-08T19:00:00Z")).toContain("8/11/26");
  });
  it("no escala otra vez el porcentaje de recuperación y preserva cero", () => {
    expect(porcentajePanel(25)).toBe("25 %");
    expect(porcentajePanel(0)).toBe("0 %");
    expect(numeroPanel(0)).toBe("0");
  });
});
