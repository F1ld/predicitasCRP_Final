import { describe, expect, it } from "vitest";
import { resolverRetorno } from "./retorno";

describe("retorno contextual interno", () => {
  it("conserva el contexto de Panel y el retorno de Citas", () => {
    expect(resolverRetorno({ volver: "/panel?fecha=2026-11-09&tipo=OFERTAS_EN_CURSO&desplazamiento=20" }, "/citas", ["/panel", "/citas"])).toBe("/panel?fecha=2026-11-09&tipo=OFERTAS_EN_CURSO&desplazamiento=20");
    expect(resolverRetorno({ volver: "/citas?medico=Sintetico" }, "/citas", ["/panel", "/citas"])).toBe("/citas?medico=Sintetico");
  });
  it.each([null, undefined, "x", {}, { volver: 3 }, { volver: "https://otro.test/panel" }, { volver: "//otro.test/panel" }, { volver: "/panel/otra" }, { volver: "/panel\\otra" }, { volver: "/panel\n" }])("preserva fallback ante origen no permitido %j", estado => {
    expect(resolverRetorno(estado, "/cupos", ["/panel", "/cupos"])).toBe("/cupos");
  });
});
