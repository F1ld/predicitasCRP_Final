import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import ts from "typescript";
import { defineConfig, globalIgnores } from "eslint/config";

// D-002: usamos solo dependencias aprobadas. TypeScript comprueba tipos/usos;
// ESLint revisa el JSX sin anotaciones y mantiene las reglas de hooks.
// Sin autofix: las posiciones de los mensajes corresponden al JS transpilado.
const tipos = {
  processors: {
    quitarTipos: {
      preprocess(codigo, archivo) {
        return [{
          text: ts.transpileModule(codigo, {
            fileName: archivo,
            compilerOptions: { jsx: ts.JsxEmit.Preserve, target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.ESNext, verbatimModuleSyntax: false },
          }).outputText,
          filename: "sin-tipos.jsx",
        }];
      },
      postprocess(mensajes) { return mensajes.flat(); },
      supportsAutofix: false,
    },
  },
};
export default defineConfig([
  globalIgnores(["dist/**", "coverage/**", "tests/**"]),
  {
    files: ["**/*.{js,jsx,mjs}"],
    extends: [js.configs.recommended, reactHooks.configs.flat.recommended, reactRefresh.configs.vite],
    languageOptions: { globals: { ...globals.browser, ...globals.node }, parserOptions: { ecmaFeatures: { jsx: true } } },
  },
  { files: ["**/*.{ts,tsx}"], ignores: ["**/*.d.ts"], plugins: { tipos }, processor: "tipos/quitarTipos" },
]);
