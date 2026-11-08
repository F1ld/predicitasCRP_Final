import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import ModeloIA from "./ModeloIA";

const metricas = {
  version_modelo: "LightGBM_v1.0.0",
  metricas_test: { f1_score: 0.85, umbral: 0.45, precision: 0.87, recall: 0.83, roc_auc: 0.92,
    matriz_confusion: { tn: 100, fp: 10, fn: 12, tp: 28 } },
  metricas_baseline_test: { f1_score: 0.71 },
  importancia_global_variables: [{ variable: "antelacion_dias", importancia: 9 }],
};
const dataset = {
  total_historicas: 1000, atendidas_historicas: 700, no_show_historicas: 300,
  tasa_no_show_global: 0.3, train_size: 700, val_size: 150, test_size: 150,
  proximas_operativas_bd: 5, control_leakage: { aprobado: true },
};

function simular() {
  vi.stubGlobal("fetch", vi.fn(async (url: URL) =>
    Response.json(url.pathname === "/ia/metricas" ? metricas : dataset)));
}

it("conserva métricas, calidad de datos y rótulo sintético", async () => {
  simular();
  render(<ModeloIA />);
  expect(await screen.findByText("1000 atenciones cerradas")).toBeInTheDocument();
  expect(screen.getByText("Entrenamiento: 700 · Validación: 150 · Prueba: 150")).toBeInTheDocument();
  expect(screen.getByText("Días de anticipación con que se reservó la cita")).toBeInTheDocument();
  expect(screen.getByText("Resultado simulado: no es desempeño real")).toBeInTheDocument();
});

it("muestra IA no disponible y permite reintentar", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({
    error: { codigo: "MOTOR_IA_NO_DISPONIBLE", mensaje: "Motor de IA no disponible." },
  }, { status: 503 })));
  render(<ModeloIA />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Motor de IA no disponible.");
  simular();
  await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(await screen.findByText("1000 atenciones cerradas")).toBeInTheDocument();
});
