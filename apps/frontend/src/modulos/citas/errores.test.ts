import { describe, expect, it } from "vitest";
import { ApiError } from "../../nucleo/api/cliente";
import { mensajeErrorCitas } from "./errores";

// RF-010, RF-020 a RF-024, RF-104 y RF-103: los códigos contractuales
// necesitan instrucciones legibles aunque el backend omita una explicación útil.
describe("Errores M02/M09", () => {
  it.each([
    ["DESENLACE_ANTICIPADO", /cita futura/], ["CHECK_IN_REGISTRADO", /No asistió/],
    ["TRANSICION_INVALIDA", /estado actualizado/], ["CITA_PASADA", /cita pasada/],
    ["CHECK_IN_DUPLICADO", /ya fue registrada/], ["FUERA_DE_FECHA", /día de la cita/],
    ["ESTADO_FINAL", /estado final/], ["MOTOR_IA_NO_DISPONIBLE", /Motor de IA no disponible/],
    ["CITA_NO_ELEGIBLE", /Cita no elegible/], ["MODELO_NO_HABILITADO", /Modelo no habilitado/],
    ["CITA_DUPLICADA", /identificador externo/], ["FECHAS_INCONSISTENTES", /fecha de registro/],
    ["FUERA_DE_PERIMETRO", /perímetro del piloto/], ["SIN_PERMISO", /no tiene permiso/],
    ["NO_ENCONTRADO", /No se encontró la cita/],
  ])("explica %s", (codigo, patron) => {
    expect(mensajeErrorCitas(new ApiError(409, codigo))).toMatch(patron);
  });
  it("conserva validaciones, errores de conexión y fallos inesperados", () => {
    expect(mensajeErrorCitas(new ApiError(422, "VALIDACION", "Revisa el campo."))).toBe("Revisa el campo.");
    expect(mensajeErrorCitas(new Error("Conexión interrumpida."))).toBe("Conexión interrumpida.");
    expect(mensajeErrorCitas(null)).toBe("No se pudo completar la solicitud.");
  });
});
