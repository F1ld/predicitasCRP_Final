import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Rol, Usuario } from "../../nucleo/api/tipos";
import { ContextoSesion, type ContextoAuth } from "../../nucleo/auth/contexto";
import DetalleCupo from "./DetalleCupo";
import type { CandidatoOut, CupoDetalleOut, CupoOut, ReasignacionOut } from "./tipos";

// RF-074 a RF-082, RN03, RN05, RN11, RNF-028 y RNF-029:
// Pruebas unitarias completas de Detalle y Reasignación Asistida de Cupo (M06-V03)

const cupoInicial: CupoDetalleOut = {
  id_cupo_liberado: 42,
  id_cita_origen: 301,
  id_cita_externa_origen: "CIT-EXT-0042",
  especialidad: "CARDIOLOGIA",
  medico: "Dra. Cardióloga Sintética",
  fecha_hora_cupo: "2026-10-25T14:00:00-05:00",
  franja_horaria: "TARDE",
  estado_cupo: "DISPONIBLE",
  origen_liberacion: "INTERVENCION_VOLUNTARIA",
  liberado_en: "2026-10-24T10:00:00-05:00",
  oferta_vigente: null,
  reasignacion: null,
  historial_ofertas: [],
};

const candidatoUno: CandidatoOut = {
  id_candidato: 801,
  paciente_anon_id: "PAC-SIM-0801",
  especialidad_req: "CARDIOLOGIA",
  franja_preferida: "TARDE",
  estado_candidato: "ACTIVO",
  prioridad_registro: 1,
  fecha_registro: "2026-10-22T09:00:00-05:00",
};

const candidatoDos: CandidatoOut = {
  id_candidato: 802,
  paciente_anon_id: "PAC-SIM-0802",
  especialidad_req: "CARDIOLOGIA",
  franja_preferida: "INDIFERENTE",
  estado_candidato: "ACTIVO",
  prioridad_registro: 2,
  fecha_registro: "2026-10-22T10:30:00-05:00",
};

const fetchSimulado = vi.fn<typeof fetch>();

function respuesta(datos: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(datos), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function errorApi(codigo: string, mensaje: string, status = 409, campos?: Record<string, string>) {
  return respuesta({ error: { codigo, mensaje, ...(campos ? { campos } : {}) } }, status);
}

function montar(rol: Rol = "RECEPCION", idCupo = "42") {
  const usuario: Usuario = {
    id_usuario: 5,
    nombre_completo: "Operador de Reasignación",
    correo_institucional: "operador@predicitas.crp",
    rol,
    activo: true,
    creado_en: "2026-10-18T10:00:00-05:00",
    actualizado_en: null,
  };
  const contexto: ContextoAuth = {
    usuario,
    cargando: false,
    mensajeSesion: "",
    iniciarSesion: vi.fn(),
    cerrarSesion: vi.fn(),
    tieneRol: vi.fn((...roles: Rol[]) => roles.includes(rol)),
  };
  return {
    ...render(
      <ContextoSesion.Provider value={contexto}>
        <MemoryRouter initialEntries={[`/cupos/${idCupo}`]}>
          <Routes>
            <Route path="/cupos/:id" element={<DetalleCupo />} />
          </Routes>
        </MemoryRouter>
      </ContextoSesion.Provider>
    ),
    contexto,
  };
}

beforeEach(() => {
  fetchSimulado.mockReset();
  vi.stubGlobal("fetch", fetchSimulado);
  sessionStorage.clear();

  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value(this: HTMLDialogElement) {
      this.setAttribute("open", "");
    },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value(this: HTMLDialogElement) {
      this.removeAttribute("open");
    },
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("M06-V03 Consulta de cupo, propuestas y permisos (RF-074, RF-075, RN05, RNF-028)", () => {
  it("muestra carga mientras se consultan el cupo y los candidatos", () => {
    fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined));
    montar();
    expect(screen.getByText("Cargando cupo y propuestas…")).toBeInTheDocument();
  });

  it("bloquea el acceso y no realiza peticiones para TECNICO_IA", () => {
    montar("TECNICO_IA");
    expect(screen.getByRole("alert")).toHaveTextContent("No tienes permiso para acceder a los cupos liberados.");
    expect(screen.queryByRole("heading", { name: /Cupo #/ })).not.toBeInTheDocument();
    expect(fetchSimulado).not.toHaveBeenCalled();
  });

  it("muestra error contractual si falla la lectura del cupo y permite reintentar", async () => {
    fetchSimulado
      .mockResolvedValueOnce(errorApi("ERROR_INTERNO", "Error al consultar el cupo.", 500))
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent("Error al consultar el cupo.");

    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(screen.getByText("Propuesta 1 · PAC-SIM-0801")).toBeInTheDocument();
  });

  it("informa cuando el cupo no existe (404)", async () => {
    fetchSimulado.mockResolvedValueOnce(errorApi("NO_ENCONTRADO", "Cupo no encontrado.", 404));
    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se encontró el registro solicitado. Actualiza la vista para consultar los datos vigentes."
    );
  });

  it("renderiza datos del cupo, candidatos propuestos en orden sin scores y aviso sin ofertas", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno, candidatoDos]));

    montar("ADMINISTRADOR");
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(screen.getByText("CIT-EXT-0042")).toBeInTheDocument();
    expect(screen.getByText("Dra. Cardióloga Sintética")).toBeInTheDocument();
    expect(screen.getByText("Propuesta 1 · PAC-SIM-0801")).toBeInTheDocument();
    expect(screen.getByText("Propuesta 2 · PAC-SIM-0802")).toBeInTheDocument();

    // RN05: Sin score, urgencia ni prioridad clínica
    expect(screen.queryByText(/score|probabilidad|urgencia clínica/i)).not.toBeInTheDocument();
    expect(screen.getByText("No hay oferta vigente.")).toBeInTheDocument();
    expect(screen.getByText("No hay reasignación registrada.")).toBeInTheDocument();
    expect(screen.getByText("No hay ofertas registradas.")).toBeInTheDocument();
  });
});

describe("M06-E07 Registro de oferta de cupo (RF-077)", () => {
  it("permite registrar oferta a un candidato compatible y actualiza estado", async () => {
    const cupoEnOferta: CupoOut = {
      ...cupoInicial,
      estado_cupo: "EN_OFERTA",
      oferta_vigente: {
        id_candidato: candidatoUno.id_candidato,
        paciente_anon_id: candidatoUno.paciente_anon_id,
        id_operador: 5,
        fecha_hora_oferta: "2026-10-24T11:00:00-05:00",
      },
    };

    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      // POST oferta
      .mockResolvedValueOnce(respuesta(cupoEnOferta, 201))
      // Refresco tras mutación
      .mockResolvedValueOnce(respuesta({ ...cupoEnOferta, historial_ofertas: [], reasignacion: null }))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    const botonOfrecer = screen.getByRole("button", { name: `Ofrecer cupo a ${candidatoUno.paciente_anon_id}` });
    await userEvent.click(botonOfrecer);

    await waitFor(() => {
      const llamadaOferta = fetchSimulado.mock.calls.find(([, opt]) => opt?.method === "POST");
      expect(llamadaOferta).toBeDefined();
      expect(String(llamadaOferta?.[0])).toContain("/cupos/42/oferta");
      expect(JSON.parse(String(llamadaOferta?.[1]?.body))).toEqual({ id_candidato: candidatoUno.id_candidato });
    });

    expect(
      await screen.findByText("Oferta registrada. Espera la respuesta del paciente antes de confirmar la reasignación.")
    ).toBeInTheDocument();
  });

  it.each([
    ["CUPO_NO_DISPONIBLE", "El cupo ya no está disponible para ofrecerlo. Revisa su estado actualizado."],
    ["CUPO_EXPIRADO", "El cupo está vencido: no admite ofertas ni reasignación."],
    ["CANDIDATO_NO_COMPATIBLE", "El candidato ya no es compatible con el cupo. Revisa las propuestas actualizadas."],
    ["CANDIDATO_CON_OFERTA", "El candidato tiene una oferta vigente. Cierra la oferta antes de continuar."],
  ])("informa error de negocio %s al intentar ofrecer", async (codigo, mensajeEsperado) => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockResolvedValueOnce(errorApi(codigo, "Conflicto", 409))
      // Refresco tras 409
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: `Ofrecer cupo a ${candidatoUno.paciente_anon_id}` }));
    expect(await screen.findByText(mensajeEsperado)).toBeInTheDocument();
  });
});

describe("M06-E08 Cierre de oferta (RF-078)", () => {
  const cupoConOferta: CupoDetalleOut = {
    ...cupoInicial,
    estado_cupo: "EN_OFERTA",
    oferta_vigente: {
      id_candidato: candidatoUno.id_candidato,
      paciente_anon_id: candidatoUno.paciente_anon_id,
      id_operador: 5,
      fecha_hora_oferta: "2026-10-24T11:00:00-05:00",
    },
  };

  it("cierra oferta por rechazo con respuesta RECHAZA", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockResolvedValueOnce(respuesta(cupoInicial, 200))
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Cerrar oferta: rechazó" }));

    await waitFor(() => {
      const llamada = fetchSimulado.mock.calls.find(([, opt]) => String(opt?.body).includes("RECHAZA"));
      expect(llamada).toBeDefined();
      expect(String(llamada?.[0])).toContain("/cupos/42/oferta/cerrar");
      expect(JSON.parse(String(llamada?.[1]?.body))).toEqual({ respuesta: "RECHAZA" });
    });

    expect(await screen.findByText("Oferta cerrada: el paciente rechazó el cupo.")).toBeInTheDocument();
  });

  it("cierra oferta por falta de respuesta con respuesta SIN_RESPUESTA", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockResolvedValueOnce(respuesta(cupoInicial, 200))
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Cerrar oferta: sin respuesta" }));

    await waitFor(() => {
      const llamada = fetchSimulado.mock.calls.find(([, opt]) => String(opt?.body).includes("SIN_RESPUESTA"));
      expect(llamada).toBeDefined();
      expect(JSON.parse(String(llamada?.[1]?.body))).toEqual({ respuesta: "SIN_RESPUESTA" });
    });

    expect(await screen.findByText("Oferta cerrada: no hubo respuesta del paciente.")).toBeInTheDocument();
  });

  it("gestiona error 409 SIN_OFERTA_VIGENTE al cerrar oferta", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockResolvedValueOnce(errorApi("SIN_OFERTA_VIGENTE", "No hay oferta", 409))
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Cerrar oferta: rechazó" }));
    expect(
      await screen.findByText("No hay una oferta vigente para este candidato. Actualiza el cupo antes de continuar.")
    ).toBeInTheDocument();
  });
});

describe("M06-E09 Reasignación Asistida con Confirmación Humana Explícita (RF-079, RF-081, RF-082, RN03, RN11, RNF-029)", () => {
  const cupoConOferta: CupoDetalleOut = {
    ...cupoInicial,
    estado_cupo: "EN_OFERTA",
    oferta_vigente: {
      id_candidato: candidatoUno.id_candidato,
      paciente_anon_id: candidatoUno.paciente_anon_id,
      id_operador: 5,
      fecha_hora_oferta: "2026-10-24T11:00:00-05:00",
    },
  };

  it("abre el diálogo modal y permite cancelarlo", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirmar reasignación" }));
    expect(screen.getByRole("heading", { name: "Confirmar reasignación" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    const dialogo = document.querySelector("dialog");
    expect(dialogo?.hasAttribute("open")).toBe(false);
  });

  it("el botón de envío permanece deshabilitado hasta marcar la casilla Y seleccionar el medio", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirmar reasignación" }));

    const botonRegistrar = screen.getByRole("button", { name: "Registrar reasignación" });
    const casillaConfirmacion = screen.getByLabelText("Confirmé la reasignación con el paciente");
    const selectMedio = screen.getByLabelText("Medio de confirmación");

    // Ambos desmarcados -> botón deshabilitado
    expect(botonRegistrar).toBeDisabled();

    // Solo casilla marcada -> sigue deshabilitado
    await userEvent.click(casillaConfirmacion);
    expect(casillaConfirmacion).toBeChecked();
    expect(botonRegistrar).toBeDisabled();

    // Casilla desmarcada y solo medio seleccionado -> sigue deshabilitado
    await userEvent.click(casillaConfirmacion);
    expect(casillaConfirmacion).not.toBeChecked();
    await userEvent.selectOptions(selectMedio, "LLAMADA_CONFIRMADA");
    expect(botonRegistrar).toBeDisabled();

    // Ambos listos -> habilitado
    await userEvent.click(casillaConfirmacion);
    expect(casillaConfirmacion).toBeChecked();
    expect(botonRegistrar).toBeEnabled();
  });

  it("rechaza el envío programático si la casilla de confirmación no está marcada (false/null/omitida)", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirmar reasignación" }));

    const formulario = screen.getByRole("dialog").querySelector("form")!;
    // Intentar submit directo sin marcar casilla
    fireEvent.submit(formulario);

    expect(screen.getByText("Marca la confirmación después de hablar con el paciente.")).toBeInTheDocument();
    // No debe haber ninguna llamada a POST /reasignacion
    const llamadaReasigna = fetchSimulado.mock.calls.find(([, opt]) => String(opt?.body).includes("confirmacion_humana"));
    expect(llamadaReasigna).toBeUndefined();
  });

  it("envía confirmacion_humana: true literal, medio y observaciones, y muestra el aviso de agendamiento externo (RN03)", async () => {
    const reasignacionExitosa: ReasignacionOut = {
      id_reasignacion: 901,
      id_cupo_liberado: 42,
      id_candidato: candidatoUno.id_candidato,
      paciente_anon_id: candidatoUno.paciente_anon_id,
      id_operador_confirma: 5,
      confirmacion_humana: true,
      medio_confirmacion: "LLAMADA_CONFIRMADA",
      observaciones: "Aceptó cita para la tarde",
      fecha_hora_reasigna: "2026-10-24T11:15:00-05:00",
    };

    const cupoReasignado: CupoDetalleOut = {
      ...cupoConOferta,
      estado_cupo: "REASIGNADO",
      oferta_vigente: null,
      reasignacion: reasignacionExitosa,
    };

    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      // POST reasignación
      .mockResolvedValueOnce(respuesta(reasignacionExitosa, 201))
      // Refresco tras mutación
      .mockResolvedValueOnce(respuesta(cupoReasignado));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirmar reasignación" }));

    const casilla = screen.getByLabelText("Confirmé la reasignación con el paciente");
    const selectMedio = screen.getByLabelText("Medio de confirmación");
    const inputObservaciones = screen.getByLabelText("Observaciones (opcional)");

    await userEvent.click(casilla);
    await userEvent.selectOptions(selectMedio, "LLAMADA_CONFIRMADA");
    await userEvent.type(inputObservaciones, "Aceptó cita para la tarde");

    const botonRegistrar = screen.getByRole("button", { name: "Registrar reasignación" });
    expect(botonRegistrar).toBeEnabled();
    await userEvent.click(botonRegistrar);

    await waitFor(() => {
      const llamada = fetchSimulado.mock.calls.find(([, opt]) => String(opt?.body).includes("confirmacion_humana"));
      expect(llamada).toBeDefined();
      expect(String(llamada?.[0])).toContain("/cupos/42/reasignacion");

      const cuerpo = JSON.parse(String(llamada?.[1]?.body));
      expect(cuerpo).toEqual({
        id_candidato: candidatoUno.id_candidato,
        confirmacion_humana: true, // Literal boolean true
        medio_confirmacion: "LLAMADA_CONFIRMADA",
        observaciones: "Aceptó cita para la tarde",
      });
      // Verificación estricta de tipo boolean true
      expect(cuerpo.confirmacion_humana).toBe(true);
      expect(typeof cuerpo.confirmacion_humana).toBe("boolean");
    });

    // RN03: Aviso de que PrediCitas no agenda
    const avisos = await screen.findAllByText("Agenda la cita en el sistema de la clínica: PrediCitas no agenda");
    expect(avisos.length).toBeGreaterThanOrEqual(1);
  });

  it("gestiona error 422 CONFIRMACION_REQUERIDA devuelto por la API", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockResolvedValueOnce(
        errorApi("CONFIRMACION_REQUERIDA", "Confirmación obligatoria", 422)
      );

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirmar reasignación" }));
    await userEvent.click(screen.getByLabelText("Confirmé la reasignación con el paciente"));
    await userEvent.selectOptions(screen.getByLabelText("Medio de confirmación"), "PRESENCIAL");
    await userEvent.click(screen.getByRole("button", { name: "Registrar reasignación" }));

    expect(
      await screen.findByText("Debes confirmar explícitamente la reasignación con el paciente antes de registrarla.")
    ).toBeInTheDocument();
  });

  it("gestiona error 409 CUPO_REASIGNADO devuelto por la API", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockResolvedValueOnce(errorApi("CUPO_REASIGNADO", "Ya fue reasignado", 409))
      // Refresco tras 409
      .mockResolvedValueOnce(respuesta({ ...cupoConOferta, estado_cupo: "REASIGNADO" }));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirmar reasignación" }));
    await userEvent.click(screen.getByLabelText("Confirmé la reasignación con el paciente"));
    await userEvent.selectOptions(screen.getByLabelText("Medio de confirmación"), "PRESENCIAL");
    await userEvent.click(screen.getByRole("button", { name: "Registrar reasignación" }));

    expect(
      await screen.findByText("El cupo ya fue reasignado. No se puede confirmar otra reasignación.")
    ).toBeInTheDocument();
  });
});

describe("Estados especiales de cupo: EXPIRADO y REASIGNADO", () => {
  it("un cupo EXPIRADO no consulta candidatos y avisa que no admite ofertas", async () => {
    const cupoExpirado: CupoDetalleOut = {
      ...cupoInicial,
      estado_cupo: "EXPIRADO",
    };

    fetchSimulado.mockResolvedValueOnce(respuesta(cupoExpirado));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(screen.getByText("El cupo expiró y no admite ofertas ni reasignación.")).toBeInTheDocument();
    expect(screen.getByText("No se proponen candidatos para este estado del cupo.")).toBeInTheDocument();

    // Solo 1 llamada a GET /cupos/42, ninguna a /candidatos
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
    expect(String(fetchSimulado.mock.calls[0][0])).not.toContain("/candidatos");
  });

  it("un cupo REASIGNADO muestra los datos de la reasignación previa y el aviso de agendamiento", async () => {
    const cupoReasignado: CupoDetalleOut = {
      ...cupoInicial,
      estado_cupo: "REASIGNADO",
      reasignacion: {
        id_reasignacion: 777,
        id_cupo_liberado: 42,
        id_candidato: 801,
        paciente_anon_id: "PAC-SIM-0801",
        id_operador_confirma: 9,
        confirmacion_humana: true,
        medio_confirmacion: "PRESENCIAL",
        observaciones: "Reasignado en ventanilla",
        fecha_hora_reasigna: "2026-10-24T12:00:00-05:00",
      },
    };

    fetchSimulado.mockResolvedValueOnce(respuesta(cupoReasignado));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(screen.getByText("El cupo ya fue reasignado y no admite una nueva asignación.")).toBeInTheDocument();
    expect(screen.getByText("PAC-SIM-0801")).toBeInTheDocument();
    expect(screen.getByText("#777")).toBeInTheDocument();
    expect(screen.getAllByText("Presencial").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Reasignado en ventanilla")).toBeInTheDocument();
    // No llama a /candidatos
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
  });
});

describe("DetalleCupo · caminos de error y guardas (T-063)", () => {
  const cupoConOferta: CupoDetalleOut = {
    ...cupoInicial,
    estado_cupo: "EN_OFERTA",
    oferta_vigente: {
      id_candidato: candidatoUno.id_candidato,
      paciente_anon_id: candidatoUno.paciente_anon_id,
      id_operador: 5,
      fecha_hora_oferta: "2026-10-24T11:00:00-05:00",
    },
  };

  it("línea 31: muestra error cuando GET /cupos/{id}/candidatos responde 200 con cuerpo null", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta(null));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(screen.getByText("El servidor no devolvió las propuestas de candidatos.")).toBeInTheDocument();
  });

  it("línea 34: cancela la carga al desmontar el componente sin emitir errores tardíos", async () => {
    let abortado = false;
    fetchSimulado.mockImplementation((_url, opt) => {
      return new Promise((_, reject) => {
        opt?.signal?.addEventListener("abort", () => {
          abortado = true;
          reject(new DOMException("The operation was aborted", "AbortError"));
        });
      });
    });

    const { unmount } = montar();
    unmount();

    expect(abortado).toBe(true);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("líneas 36-37: relee el cupo cuando GET /candidatos responde 409 y muestra el error de candidatos", async () => {
    const cupoReasignado: CupoDetalleOut = {
      ...cupoInicial,
      estado_cupo: "REASIGNADO",
    };

    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(errorApi("CUPO_REASIGNADO", "El cupo ya fue reasignado.", 409))
      .mockResolvedValueOnce(respuesta(cupoReasignado));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(
      screen.getByText("El cupo ya fue reasignado. No se puede confirmar otra reasignación.")
    ).toBeInTheDocument();
    expect(screen.getByText("REASIGNADO")).toBeInTheDocument();
    expect(fetchSimulado).toHaveBeenCalledTimes(3);
    expect(String(fetchSimulado.mock.calls[0][0])).toContain("/cupos/42");
    expect(String(fetchSimulado.mock.calls[1][0])).toContain("/cupos/42/candidatos");
    expect(String(fetchSimulado.mock.calls[2][0])).toContain("/cupos/42");
  });

  it("líneas 61, 63: gestiona error 500 inicial con opción de reintentar y tolera desmontaje durante el fallo", async () => {
    fetchSimulado.mockResolvedValueOnce(errorApi("ERROR_INTERNO", "Error interno 500", 500));

    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent("Error interno 500");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();

    cleanup();

    let rejectPromise: ((reason: unknown) => void) | undefined;
    fetchSimulado.mockImplementationOnce(() => new Promise((_, reject) => {
      rejectPromise = reject;
    }));
    const { unmount } = montar();
    unmount();
    rejectPromise?.(new Error("Fallo tras desmontar"));
  });

  it("líneas 75, 77, 80: refrescar() con error de candidatos activa requiereRefresco y mantiene el botón visible", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(errorApi("ERROR_CANDIDATOS", "Fallo al consultar candidatos", 500))
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(errorApi("ERROR_CANDIDATOS", "Fallo repetido en candidatos", 500));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(screen.getByText("Fallo al consultar candidatos")).toBeInTheDocument();

    const botonRefrescar = screen.getByRole("button", { name: "Refrescar cupo y propuestas" });
    await userEvent.click(botonRefrescar);

    expect(await screen.findByText("No se pudo refrescar el cupo: Fallo repetido en candidatos")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refrescar cupo y propuestas" })).toBeInTheDocument();
  });

  it("líneas 85, 89-91: botón de refresco gestiona éxito, fallo con cupo, reintento sin cupo y evita doble clic", async () => {
    let resolverRefresco: ((res: Response) => void) | undefined;
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(errorApi("ERROR_CANDIDATOS", "Error temporal", 500))
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolverRefresco = resolve;
      }))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    const botonRefrescar = screen.getByRole("button", { name: "Refrescar cupo y propuestas" });

    fireEvent.click(botonRefrescar);
    fireEvent.click(botonRefrescar);

    expect(fetchSimulado).toHaveBeenCalledTimes(3);

    resolverRefresco!(respuesta(cupoInicial));
    await waitFor(() => {
      expect(screen.queryByText("Error temporal")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Refrescar cupo y propuestas" })).not.toBeInTheDocument();
    });

    cleanup();

    fetchSimulado
      .mockResolvedValueOnce(errorApi("ERROR_INTERNO", "Error inicial", 500))
      .mockResolvedValueOnce(errorApi("ERROR_INTERNO", "Fallo reintento sin cupo", 500));

    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent("Error inicial");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Fallo reintento sin cupo");
  });

  it("líneas 97, 99, 103-105, 109: acción con cuerpo vacío y acción guardada con refresco fallido", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockResolvedValueOnce(respuesta(null));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: `Ofrecer cupo a ${candidatoUno.paciente_anon_id}` }));
    expect(await screen.findByText("El servidor no devolvió el resultado de la acción.")).toBeInTheDocument();

    cleanup();

    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(errorApi("ERROR_INTERNO", "Fallo al refrescar tras oferta", 500));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: `Ofrecer cupo a ${candidatoUno.paciente_anon_id}` }));
    expect(
      await screen.findByText("La acción se guardó, pero no se pudo refrescar el detalle y sus propuestas: Fallo al refrescar tras oferta")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refrescar cupo y propuestas" })).toBeInTheDocument();
  });

  it("líneas 112, 117, 120: acción con 409 y refresco fallido combina ambos errores, y cubre desmontaje", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockResolvedValueOnce(errorApi("ESTADO_INVALIDO", "El cupo ya no está disponible.", 409))
      .mockResolvedValueOnce(errorApi("ERROR_RED", "Fallo de conexión.", 500));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: `Ofrecer cupo a ${candidatoUno.paciente_anon_id}` }));

    expect(
      await screen.findByText("El cupo ya no está disponible. No se pudo refrescar el cupo: Fallo de conexión.")
    ).toBeInTheDocument();

    cleanup();

    let resolverPost: ((res: Response) => void) | undefined;
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolverPost = resolve;
      }));

    const inst = montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: `Ofrecer cupo a ${candidatoUno.paciente_anon_id}` }));
    inst.unmount();
    resolverPost!(respuesta(cupoInicial));
  });

  it("líneas 129, 133, 137, 142: guardas bloquean acciones mientras está bloqueado y doble clic en Ofrecer emite un solo POST", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(errorApi("ERROR_CANDIDATOS", "Error candidatos", 500));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    const botonRechazo = screen.getByRole("button", { name: "Cerrar oferta: rechazó" });
    const botonSinResp = screen.getByRole("button", { name: "Cerrar oferta: sin respuesta" });
    const botonConfirmar = screen.getByRole("button", { name: "Confirmar reasignación" });

    expect(botonRechazo).toBeDisabled();
    expect(botonSinResp).toBeDisabled();
    expect(botonConfirmar).toBeDisabled();

    fireEvent.click(botonRechazo);
    fireEvent.click(botonSinResp);
    fireEvent.click(botonConfirmar);

    const llamadasPost = fetchSimulado.mock.calls.filter(([, opt]) => opt?.method === "POST");
    expect(llamadasPost).toHaveLength(0);

    cleanup();

    let resolverOferta: ((res: Response) => void) | undefined;
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolverOferta = resolve;
      }))
      .mockResolvedValueOnce(respuesta(cupoConOferta));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    const botonOfrecer = screen.getByRole("button", { name: `Ofrecer cupo a ${candidatoUno.paciente_anon_id}` });

    fireEvent.click(botonOfrecer);
    fireEvent.click(botonOfrecer);

    const postsOferta = fetchSimulado.mock.calls.filter(([url, opt]) => String(url).includes("/oferta") && opt?.method === "POST");
    expect(postsOferta).toHaveLength(1);

    resolverOferta!(respuesta(cupoConOferta));
  });

  it("línea 152: rechaza confirmación con medio inválido o discordante sin enviar POST", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirmar reasignación" }));
    await userEvent.click(screen.getByLabelText("Confirmé la reasignación con el paciente"));

    const selectMedio = screen.getByLabelText("Medio de confirmación");
    fireEvent.change(selectMedio, { target: { value: "INVALIDO" } });

    const formulario = screen.getByRole("dialog").querySelector("form")!;
    fireEvent.submit(formulario);

    expect(screen.getByText("Selecciona el medio de confirmación.")).toBeInTheDocument();
    const llamadaReasigna = fetchSimulado.mock.calls.find(([, opt]) => String(opt?.body).includes("confirmacion_humana"));
    expect(llamadaReasigna).toBeUndefined();
  });

  it("línea 154: rechaza observaciones mayores a 255 caracteres sin enviar POST", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirmar reasignación" }));
    await userEvent.click(screen.getByLabelText("Confirmé la reasignación con el paciente"));
    await userEvent.selectOptions(screen.getByLabelText("Medio de confirmación"), "LLAMADA_CONFIRMADA");

    const textarea = screen.getByLabelText("Observaciones (opcional)");
    fireEvent.change(textarea, { target: { value: "A".repeat(256) } });

    const formulario = screen.getByRole("dialog").querySelector("form")!;
    fireEvent.submit(formulario);

    expect(screen.getByText("Revisa las observaciones: el máximo es 255 caracteres.")).toBeInTheDocument();
    const llamadaReasigna = fetchSimulado.mock.calls.find(([, opt]) => String(opt?.body).includes("confirmacion_humana"));
    expect(llamadaReasigna).toBeUndefined();
  });

  it("línea 161: muestra 'No se encontró el cupo liberado.' con enlace cuando cupo es null", async () => {
    fetchSimulado.mockResolvedValueOnce(respuesta(null));

    montar();
    expect(await screen.findByText("No se encontró el cupo liberado.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Volver a cupos liberados" })).toBeInTheDocument();
  });

  it("líneas 166, 180: muestra error de candidatos y botón de refresco ante fallo en propuestas", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(errorApi("ERROR_CANDIDATOS", "Error al calcular compatibilidad", 500));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(screen.getByText("Error al calcular compatibilidad")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refrescar cupo y propuestas" })).toBeInTheDocument();
  });

  it("línea 187: muestra aviso sin reasignación y detalle con y sin observaciones cuando está reasignado", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(screen.getByText("No hay reasignación registrada.")).toBeInTheDocument();

    cleanup();

    const cupoReasignadoSinObs: CupoDetalleOut = {
      ...cupoInicial,
      estado_cupo: "REASIGNADO",
      reasignacion: {
        id_reasignacion: 999,
        id_cupo_liberado: 42,
        id_candidato: 801,
        paciente_anon_id: "PAC-SIM-0801",
        id_operador_confirma: 5,
        confirmacion_humana: true,
        medio_confirmacion: "PRESENCIAL",
        observaciones: "",
        fecha_hora_reasigna: "2026-10-24T12:00:00-05:00",
      },
    };

    fetchSimulado.mockResolvedValueOnce(respuesta(cupoReasignadoSinObs));
    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(screen.getByText("Sin observaciones")).toBeInTheDocument();
    expect(screen.getByText("PAC-SIM-0801")).toBeInTheDocument();
    expect(screen.getByText("#999")).toBeInTheDocument();
  });

  it("línea 190: muestra aviso con historial vacío y lista detallada con ofertas abiertas y cerradas", async () => {
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoInicial))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(screen.getByText("No hay ofertas registradas.")).toBeInTheDocument();

    cleanup();

    const cupoConHistorial: CupoDetalleOut = {
      ...cupoInicial,
      historial_ofertas: [
        {
          id_candidato: 801,
          fecha_hora_oferta: "2026-10-24T09:00:00-05:00",
          cierre: "RECHAZA",
        },
        {
          id_candidato: 802,
          fecha_hora_oferta: "2026-10-24T10:00:00-05:00",
          cierre: null,
        },
      ],
    };

    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConHistorial))
      .mockResolvedValueOnce(respuesta([candidatoUno]));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();
    expect(screen.getByText(/Candidato #801 · RECHAZA/)).toBeInTheDocument();
    expect(screen.getByText(/Candidato #802 · Oferta abierta/)).toBeInTheDocument();
  });

  it("línea 192: Escape en diálogo no cierra si ocupado y sí limpia si no hay petición", async () => {
    let resolverReasigna: ((res: Response) => void) | undefined;
    fetchSimulado
      .mockResolvedValueOnce(respuesta(cupoConOferta))
      .mockResolvedValueOnce(respuesta([candidatoUno]))
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolverReasigna = resolve;
      }))
      .mockResolvedValueOnce(respuesta({ ...cupoConOferta, estado_cupo: "REASIGNADO" }));

    montar();
    expect(await screen.findByRole("heading", { name: "Cupo #42" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirmar reasignación" }));
    const casilla = screen.getByLabelText("Confirmé la reasignación con el paciente") as HTMLInputElement;
    await userEvent.click(casilla);
    expect(casilla.checked).toBe(true);

    const dialogo = screen.getByRole("dialog");

    const eventoLibre = new Event("cancel", { bubbles: true, cancelable: true });
    fireEvent(dialogo, eventoLibre);
    expect(eventoLibre.defaultPrevented).toBe(false);
    await waitFor(() => {
      expect(casilla.checked).toBe(false);
    });

    await userEvent.click(casilla);
    await userEvent.selectOptions(screen.getByLabelText("Medio de confirmación"), "PRESENCIAL");
    const botonRegistrar = screen.getByRole("button", { name: "Registrar reasignación" });
    await userEvent.click(botonRegistrar);

    const eventoOcupado = new Event("cancel", { bubbles: true, cancelable: true });
    fireEvent(dialogo, eventoOcupado);
    expect(eventoOcupado.defaultPrevented).toBe(true);

    resolverReasigna!(respuesta({ id_reasignacion: 999 }, 201));
    await waitFor(() => {
      const llamada = fetchSimulado.mock.calls.find(([url]) => String(url).includes("/reasignacion"));
      expect(llamada).toBeDefined();
      const cuerpo = JSON.parse(String(llamada?.[1]?.body));
      expect(cuerpo).toEqual({
        id_candidato: candidatoUno.id_candidato,
        confirmacion_humana: true,
        medio_confirmacion: "PRESENCIAL",
      });
      expect("observaciones" in cuerpo).toBe(false);
    });
  });
});

