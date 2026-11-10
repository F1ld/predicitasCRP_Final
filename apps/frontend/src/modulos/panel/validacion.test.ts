import { describe, expect, it } from "vitest";
import { paginaPrueba, resumenPrueba } from "../../pruebas/panel";
import { TIPOS } from "./tipos";
import { esPaginaPanel, esResumenPanel } from "./validacion";

describe("contrato de respuestas del panel", () => {
  it("acepta el resumen y las proyecciones mínimas sin campos del detalle", () => {
    expect(esResumenPanel(resumenPrueba())).toBe(true);
    for (const tipo of TIPOS) expect(esPaginaPanel(paginaPrueba(tipo))).toBe(true);
  });
  it("rechaza bloques ausentes, tipos de conteo incorrectos y fechas sin zona", () => {
    const r = resumenPrueba();
    expect(esResumenPanel({ ...r, generado_en: "2026-11-09T09:00:00" })).toBe(false);
    expect(esResumenPanel({ ...r, citas: { total: 1 } })).toBe(false);
    expect(esResumenPanel({ ...r, cupos: { ...r.cupos, tasa_recuperacion_pct: "25" } })).toBe(false);
    expect(esResumenPanel({ ...r, pendientes: { citas_sin_intervencion: -1 } })).toBe(false);
  });
  it("rechaza items mezclados, fechas inválidas y proyecciones incompletas", () => {
    const p = paginaPrueba();
    expect(esPaginaPanel({ ...p, items: paginaPrueba("OFERTAS_EN_CURSO").items })).toBe(false);
    expect(esPaginaPanel({ ...p, items: [{ tipo: p.tipo }] })).toBe(false);
    expect(esPaginaPanel({ ...p, items: [{ ...p.items[0], fecha_hora_cita: "no-fecha" }] })).toBe(false);
    expect(esPaginaPanel(null)).toBe(false);
  });
});
