import { describe, expect, it } from "vitest";
import { leerConsulta, parametrosPanel, rutaPanel, rutasApi, validarFiltros } from "./consulta";

describe("contexto URL del panel", () => {
  it("fija hoy de Lima y normaliza valores omitidos sin fecha UTC", () => {
    const r = leerConsulta(new URLSearchParams(), new Date("2026-11-10T02:00:00Z"));
    expect(r.consulta).toEqual({ fecha: "2026-11-09", especialidad: "", tipo: "CITAS_SIN_INTERVENCION", desplazamiento: 0 });
    expect(r.error).toBe("");
    expect(parametrosPanel(r.consulta).toString()).toBe(r.normalizada);
  });
  it.each(["-1", "20abc", "1.5", "3", "Infinity", "9007199254741000", ""]) ("normaliza offset inválido %s", valor => {
    expect(leerConsulta(new URLSearchParams({ desplazamiento: valor })).consulta.desplazamiento).toBe(0);
  });
  it("conserva URL válida y separa los parámetros de los dos endpoints", () => {
    const r = leerConsulta(new URLSearchParams("fecha=2026-11-09&especialidad=CARDIOLOGIA&tipo=OFERTAS_EN_CURSO&desplazamiento=20"));
    expect(r.consulta.desplazamiento).toBe(20);
    expect(rutaPanel(r.consulta)).toBe(`/panel?${r.normalizada}`);
    const rutas = rutasApi(r.consulta);
    expect(rutas.resumen).toBe("/panel/resumen?fecha=2026-11-09&especialidad=CARDIOLOGIA");
    expect(rutas.pendientes).toContain("tipo=OFERTAS_EN_CURSO&limite=20&desplazamiento=20");
  });
  it.each(["2026-02-30", "2026-13-01", "0000-01-01", "9999-12-31", "2026-1-1", "", "abc"]) ("rechaza fecha %s", fecha => {
    expect(validarFiltros(fecha, "")).not.toBe("");
  });
  it("rechaza especialidad desconocida y normaliza tipo sin ocultar el error del universo", () => {
    const r = leerConsulta(new URLSearchParams("fecha=2026-11-09&especialidad=OTRA&tipo=OTRO"));
    expect(r.error).toMatch(/especialidad/);
    expect(r.consulta.especialidad).toBe("OTRA");
    expect(r.consulta.tipo).toBe("CITAS_SIN_INTERVENCION");
  });
});
