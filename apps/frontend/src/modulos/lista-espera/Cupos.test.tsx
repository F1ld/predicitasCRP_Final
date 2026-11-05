import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Pagina, Rol, Usuario } from "../../nucleo/api/tipos";
import { ContextoSesion, type ContextoAuth } from "../../nucleo/auth/contexto";
import Cupos from "./Cupos";
import type { CupoOut } from "./tipos";

// RF-073, RF-080, RNF-007, RNF-016 y RNF-028: pruebas de Cupos liberados (M06-V02)
const cupoEjemplo: CupoOut = {
  id_cupo_liberado: 101,
  id_cita_origen: 501,
  id_cita_externa_origen: "CIT-EXT-001",
  especialidad: "CARDIOLOGIA",
  medico: "Dra. Cardióloga Sintética",
  fecha_hora_cupo: "2026-10-25T10:00:00-05:00",
  franja_horaria: "MANANA",
  estado_cupo: "DISPONIBLE",
  origen_liberacion: "INTERVENCION_VOLUNTARIA",
  liberado_en: "2026-10-24T08:00:00-05:00",
  oferta_vigente: null,
};

const fetchSimulado = vi.fn<typeof fetch>();

function respuesta(datos: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(datos), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function pagina(items: CupoOut[] = [cupoEjemplo], total = items.length, limite = 20, desplazamiento = 0): Pagina<CupoOut> {
  return { items, total, limite, desplazamiento };
}

function simular(items = [cupoEjemplo], total = items.length) {
  fetchSimulado.mockImplementation((entrada, opciones) => {
    const url = new URL(String(entrada));
    if (!opciones?.method || opciones.method === "GET") {
      return Promise.resolve(
        respuesta(
          pagina(
            items,
            total,
            Number(url.searchParams.get("limite") || 20),
            Number(url.searchParams.get("desplazamiento") || 0)
          )
        )
      );
    }
    return Promise.resolve(respuesta(cupoEjemplo, 200));
  });
}

function Ubicacion() {
  const { pathname, search } = useLocation();
  return <output aria-label="URL actual">{pathname}{search}</output>;
}

function montar(rol: Rol = "RECEPCION", ruta = "/cupos") {
  const usuario: Usuario = {
    id_usuario: 1,
    nombre_completo: "Operador de Pruebas",
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
        <MemoryRouter initialEntries={[ruta]}>
          <Ubicacion />
          <Cupos />
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
  simular();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Cupos liberados M06-V02: consulta y permisos (RF-073, RNF-028)", () => {
  it("muestra estado de carga mientras espera respuesta", () => {
    fetchSimulado.mockImplementation(() => new Promise<Response>(() => undefined));
    montar();
    expect(screen.getByText("Cargando cupos…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aplicar filtros" })).toBeDisabled();
  });

  it.each<Rol>(["ADMINISTRADOR", "RECEPCION"])("permite consultar cupos al rol %s", async (rol) => {
    const { contexto } = montar(rol);
    expect(await screen.findByText("#101")).toBeInTheDocument();
    expect(contexto.tieneRol).toHaveBeenCalledWith("ADMINISTRADOR", "RECEPCION");
    expect(screen.getByText("Dra. Cardióloga Sintética")).toBeInTheDocument();
    expect(screen.getByText("CIT-EXT-001")).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Disponible")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ver cupo/ })).toHaveAttribute("href", "/cupos/101");
  });

  it("bloquea acceso a TECNICO_IA y no realiza peticiones", () => {
    montar("TECNICO_IA");
    expect(screen.getByRole("alert")).toHaveTextContent("No tienes permiso para consultar los cupos liberados.");
    expect(screen.queryByRole("heading", { name: "Cupos liberados" })).not.toBeInTheDocument();
    expect(fetchSimulado).not.toHaveBeenCalled();
  });

  it("presenta el estado vacío cuando no hay cupos con los filtros", async () => {
    simular([]);
    montar();
    expect(await screen.findByText("No hay cupos con esos filtros.")).toBeInTheDocument();
    expect(screen.getByText("Amplía las fechas o utiliza «Limpiar».")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("muestra mensaje de error cuando falla la consulta y permite reintentar", async () => {
    fetchSimulado.mockResolvedValueOnce(
      respuesta({ error: { codigo: "ERROR_INTERNO", mensaje: "Servicio no disponible." } }, 500)
    );
    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent("Servicio no disponible.");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("#101")).toBeInTheDocument();
  });
});

describe("Filtros y paginación de cupos (RF-073)", () => {
  it("aplica filtros de estado, especialidad y rango de fechas a la URL y a la consulta", async () => {
    montar();
    expect(await screen.findByText("#101")).toBeInTheDocument();

    const formulario = screen.getByRole("form", { name: "Filtrar cupos" });
    await userEvent.selectOptions(within(formulario).getByLabelText("Estado del cupo"), "DISPONIBLE");
    await userEvent.selectOptions(within(formulario).getByLabelText("Especialidad"), "CARDIOLOGIA");
    fireEvent.change(within(formulario).getByLabelText("Desde"), { target: { value: "2026-10-20" } });
    fireEvent.change(within(formulario).getByLabelText("Hasta"), { target: { value: "2026-10-28" } });
    await userEvent.click(within(formulario).getByRole("button", { name: "Aplicar filtros" }));

    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(2));
    const url = new URL(String(fetchSimulado.mock.calls[1][0]));
    expect(url.searchParams.get("estado_cupo")).toBe("DISPONIBLE");
    expect(url.searchParams.get("especialidad")).toBe("CARDIOLOGIA");
    expect(url.searchParams.get("desde")).toBe("2026-10-20");
    expect(url.searchParams.get("hasta")).toBe("2026-10-28");
    expect(screen.getByLabelText("URL actual").textContent).toContain("estado_cupo=DISPONIBLE");
  });

  it("valida que la fecha desde no sea posterior a la fecha hasta", async () => {
    montar();
    expect(await screen.findByText("#101")).toBeInTheDocument();

    const formulario = screen.getByRole("form", { name: "Filtrar cupos" });
    fireEvent.change(within(formulario).getByLabelText("Desde"), { target: { value: "2026-10-30" } });
    fireEvent.change(within(formulario).getByLabelText("Hasta"), { target: { value: "2026-10-20" } });
    await userEvent.click(within(formulario).getByRole("button", { name: "Aplicar filtros" }));

    expect(screen.getByText("La fecha inicial no puede ser posterior a la fecha final.")).toBeInTheDocument();
    expect(fetchSimulado).toHaveBeenCalledTimes(1);
  });

  it("limpia filtros y restablece la búsqueda", async () => {
    montar("RECEPCION", "/cupos?estado_cupo=DISPONIBLE&especialidad=CARDIOLOGIA");
    expect(await screen.findByText("#101")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("URL actual")).toHaveTextContent(/^\/cupos$/);
  });

  it("pagina hacia adelante y hacia atrás con el tamaño configurado", async () => {
    const cupoDos: CupoOut = { ...cupoEjemplo, id_cupo_liberado: 102 };
    simular([cupoEjemplo, cupoDos], 35);
    montar();
    expect(await screen.findByText("#101")).toBeInTheDocument();
    expect(screen.getByText("Página 1 de 2")).toBeInTheDocument();

    const botonSiguiente = screen.getByRole("button", { name: "Siguiente" });
    expect(botonSiguiente).toBeEnabled();
    await userEvent.click(botonSiguiente);

    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(2));
    const urlSiguiente = new URL(String(fetchSimulado.mock.calls[1][0]));
    expect(urlSiguiente.searchParams.get("desplazamiento")).toBe("20");

    const botonAnterior = screen.getByRole("button", { name: "Anterior" });
    expect(botonAnterior).toBeEnabled();
    await userEvent.click(botonAnterior);

    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(3));
    const urlAnterior = new URL(String(fetchSimulado.mock.calls[2][0]));
    expect(urlAnterior.searchParams.get("desplazamiento")).toBe("0");
  });
});
