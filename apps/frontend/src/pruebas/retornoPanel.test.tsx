import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ContextoSesion, type ContextoAuth } from "../nucleo/auth/contexto";
import type { CitaDetalleOut } from "../modulos/citas/tipos";
import type { IntervencionOut } from "../modulos/intervenciones/tipos";
import type { CupoDetalleOut } from "../modulos/lista-espera/tipos";
import DetalleCita from "../modulos/citas/Detalle";
import Seguimiento from "../modulos/intervenciones/Seguimiento";
import DetalleCupo from "../modulos/lista-espera/DetalleCupo";
import PanelOperativo from "../modulos/panel/PanelOperativo";
import { paginaPrueba, respuestaPrueba, resumenPrueba } from "./panel";

const rutaPanel = "/panel?fecha=2026-11-09&especialidad=CARDIOLOGIA&tipo=OFERTAS_EN_CURSO&desplazamiento=20";
const cita: CitaDetalleOut = { id_cita: 101, id_cita_externa: "CITA-101", paciente_anon_id: "PAC-101", sede: "SAN_ISIDRO", especialidad: "CARDIOLOGIA", medico: "Profesional sintético", fecha_hora_cita: "2026-11-09T14:00:00-05:00", fecha_registro_cita: "2026-11-01T10:00:00-05:00", antelacion_dias: 8, tipo_paciente: "NUEVO", canal_origen: "WEB", franja_horaria: "TARDE", dia_semana: "LUNES", inasistencias_previas: 0, reprogramaciones_prev: 0, asistencias_previas: 0, estado_actual: "RECIBIDA", target_no_show: null, historial: [], check_in: null, predicciones: [], intervenciones: [], cupo_liberado: null, reasignacion: null };
const inter: IntervencionOut = { id_intervencion: 17, id_cita: 101, id_cita_externa: "CITA-101", id_operador: null, canal_contacto: "SMS", plantilla_mensaje: "RECORDATORIO_CONFIRMACION_V1", consentimiento_optout: false, estado_intervencion: "ENVIADA", respuesta_paciente: null, fecha_hora_envio: "2026-11-09T09:00:00-05:00", fecha_hora_respuesta: null, acciones_disponibles: [] };
const cupo: CupoDetalleOut = { id_cupo_liberado: 42, id_cita_origen: 101, id_cita_externa_origen: "CITA-101", especialidad: "CARDIOLOGIA", medico: "Profesional sintético", fecha_hora_cupo: cita.fecha_hora_cita, franja_horaria: "TARDE", estado_cupo: "EXPIRADO", origen_liberacion: "CANCELACION_EXTERNA", liberado_en: inter.fecha_hora_envio!, oferta_vigente: null, reasignacion: null, historial_ofertas: [] };
const casos = [{ ruta: "/citas/101", path: "/citas/:id", componente: <DetalleCita />, datos: cita, fallback: "/citas" }, { ruta: "/intervenciones/17", path: "/intervenciones/:id", componente: <Seguimiento />, datos: inter, fallback: "/intervenciones" }, { ruta: "/cupos/42", path: "/cupos/:id", componente: <DetalleCupo />, datos: cupo, fallback: "/cupos" }];

function montar(caso: typeof casos[number], estado: unknown, status: number) {
  const contexto: ContextoAuth = { usuario: null, cargando: false, mensajeSesion: "", iniciarSesion: vi.fn(), cerrarSesion: vi.fn(), tieneRol: (...roles) => roles.includes("RECEPCION") };
  const fetch = vi.fn<typeof window.fetch>(async entrada => {
    const u = new URL(String(entrada));
    if (u.pathname === "/panel/resumen") return respuestaPrueba({ ...resumenPrueba(), especialidad: "CARDIOLOGIA" });
    if (u.pathname === "/panel/pendientes") return respuestaPrueba({ ...paginaPrueba("OFERTAS_EN_CURSO"), especialidad: "CARDIOLOGIA", desplazamiento: 20 });
    if (status === 204) return new Response(null, { status });
    return respuestaPrueba(status === 200 ? caso.datos : { error: { codigo: "NO_ENCONTRADO", mensaje: "Registro no encontrado" } }, status);
  });
  vi.stubGlobal("fetch", fetch);
  render(<ContextoSesion.Provider value={contexto}><MemoryRouter initialEntries={[{ pathname: caso.ruta, state: estado }]}><Routes>
    <Route path={caso.path} element={caso.componente} /><Route path="/panel" element={<PanelOperativo />} />
  </Routes></MemoryRouter></ContextoSesion.Provider>);
  return fetch;
}

describe("regreso al panel desde detalles reales", () => {
  for (const caso of casos) {
    it.each([200, 404, 204])(`${caso.ruta} conserva retorno en respuesta %s`, async status => {
      montar(caso, { volver: rutaPanel }, status);
      expect(await screen.findByRole("link", { name: /Volver al panel operativo/ })).toHaveAttribute("href", rutaPanel);
    });
    it(`${caso.ruta} conserva el fallback ante acceso directo`, async () => {
      montar(caso, null, 404);
      expect(await screen.findByRole("link", { name: /Volver/ })).toHaveAttribute("href", caso.fallback);
    });
  }
  it("volver conserva contexto y consulta datos actuales", async () => {
    const fetch = montar(casos[2], { volver: rutaPanel }, 200);
    await userEvent.click(await screen.findByRole("link", { name: /Volver al panel operativo/ }));
    expect(await screen.findByRole("heading", { name: "Panel operativo" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Ver cupo" })).toBeInTheDocument();
    expect(fetch.mock.calls.filter(([u]) => new URL(String(u)).pathname.startsWith("/panel/")).length).toBe(2);
    expect(screen.getByLabelText("Fecha de la jornada")).toHaveValue("2026-11-09");
    expect(screen.getByLabelText("Especialidad")).toHaveValue("CARDIOLOGIA");
    expect(screen.getByRole("button", { name: /Ofertas en curso/ })).toHaveAttribute("aria-pressed", "true");
  });
});
