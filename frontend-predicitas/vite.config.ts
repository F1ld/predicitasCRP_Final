import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// D-002: Vitest + RTL, cobertura de todo el código de aplicación (>= 75 %).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/pruebas/configurar.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    clearMocks: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json-summary"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/pruebas/**", "src/**/*.d.ts", "src/main.tsx", "src/nucleo/sesion/index.ts"],
      thresholds: { lines: 75 },
    },
  },
});
