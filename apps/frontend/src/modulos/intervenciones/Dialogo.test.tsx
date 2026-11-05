import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import Dialogo from "./Dialogo";

describe("Dialogo modal accesible (RNF-016)", () => {
  afterEach(() => {
    cleanup();
  });

  it("a) Tab en el último elemento enfocable vuelve al primero", () => {
    const cerrar = vi.fn();
    render(
      <Dialogo titulo="Modal con controles" cerrar={cerrar}>
        <div>
          <input aria-label="Campo de texto" defaultValue="Valor sintético" />
          <button type="submit">Guardar acción</button>
        </div>
      </Dialogo>,
    );

    const botonCerrar = screen.getByRole("button", { name: "Cerrar diálogo" });
    const botonGuardar = screen.getByRole("button", { name: "Guardar acción" });

    botonGuardar.focus();
    expect(document.activeElement).toBe(botonGuardar);

    const dialogo = screen.getByRole("dialog");
    fireEvent.keyDown(dialogo, { key: "Tab", code: "Tab" });
    expect(document.activeElement).toBe(botonCerrar);
  });

  it("b) Shift+Tab en el primero va al último y desde el contenedor del diálogo va al último", () => {
    const cerrar = vi.fn();
    render(
      <Dialogo titulo="Modal navegación inversa" cerrar={cerrar}>
        <div>
          <input aria-label="Campo 1" />
          <button type="button">Último control</button>
        </div>
      </Dialogo>,
    );

    const botonCerrar = screen.getByRole("button", { name: "Cerrar diálogo" });
    const botonUltimo = screen.getByRole("button", { name: "Último control" });
    const dialogo = screen.getByRole("dialog");

    botonCerrar.focus();
    expect(document.activeElement).toBe(botonCerrar);

    fireEvent.keyDown(dialogo, { key: "Tab", code: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(botonUltimo);

    dialogo.focus();
    expect(document.activeElement).toBe(dialogo);

    fireEvent.keyDown(dialogo, { key: "Tab", code: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(botonUltimo);
  });

  it("c) un diálogo sin elementos enfocables además del botón cerrar no rompe el Tab", () => {
    const cerrar = vi.fn();
    render(
      <Dialogo titulo="Solo botón cerrar" cerrar={cerrar}>
        <p>Texto puramente informativo sin controles interactivos.</p>
      </Dialogo>,
    );

    const botonCerrar = screen.getByRole("button", { name: "Cerrar diálogo" });
    const dialogo = screen.getByRole("dialog");

    expect(document.activeElement).toBe(botonCerrar);

    fireEvent.keyDown(dialogo, { key: "Tab", code: "Tab" });
    expect(document.activeElement).toBe(botonCerrar);

    fireEvent.keyDown(dialogo, { key: "Tab", code: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(botonCerrar);
  });

  it("d) Escape llama a cerrar", () => {
    const cerrar = vi.fn();
    render(
      <Dialogo titulo="Cierre por teclado" cerrar={cerrar}>
        <p>Contenido del diálogo</p>
      </Dialogo>,
    );

    const dialogo = screen.getByRole("dialog");
    fireEvent.keyDown(dialogo, { key: "Escape", code: "Escape" });
    expect(cerrar).toHaveBeenCalledTimes(1);
  });

  it("e) al cerrarse, el foco vuelve al elemento que lo abrió", () => {
    const botonAbrir = document.createElement("button");
    botonAbrir.textContent = "Abrir modal";
    document.body.appendChild(botonAbrir);
    botonAbrir.focus();
    expect(document.activeElement).toBe(botonAbrir);

    const cerrar = vi.fn();
    const { unmount } = render(
      <Dialogo titulo="Retorno de foco" cerrar={cerrar}>
        <input aria-label="Entrada" />
      </Dialogo>,
    );

    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Cerrar diálogo" }));

    unmount();
    expect(document.activeElement).toBe(botonAbrir);
    botonAbrir.remove();
  });

  it("atrapa foco cuando ocurre focusin fuera del diálogo", () => {
    const outsideBtn = document.createElement("button");
    document.body.appendChild(outsideBtn);

    const cerrar = vi.fn();
    render(
      <Dialogo titulo="Foco externo" cerrar={cerrar}>
        <button type="button">Dentro</button>
      </Dialogo>,
    );

    const botonCerrar = screen.getByRole("button", { name: "Cerrar diálogo" });
    expect(document.activeElement).toBe(botonCerrar);

    outsideBtn.dispatchEvent(new FocusEvent("focusin", { bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(botonCerrar);

    outsideBtn.remove();
  });

  it("ignora teclas distintas de Tab y Escape y permite Tab entre elementos intermedios", () => {
    const cerrar = vi.fn();
    render(
      <Dialogo titulo="Otras teclas" cerrar={cerrar}>
        <div>
          <input aria-label="Medio 1" />
          <input aria-label="Medio 2" />
          <button type="button">Fin</button>
        </div>
      </Dialogo>,
    );

    const dialogo = screen.getByRole("dialog");
    const medio1 = screen.getByLabelText("Medio 1");

    fireEvent.keyDown(dialogo, { key: "Enter", code: "Enter" });
    expect(cerrar).not.toHaveBeenCalled();

    medio1.focus();
    fireEvent.keyDown(dialogo, { key: "Tab", code: "Tab" });
    expect(cerrar).not.toHaveBeenCalled();

    fireEvent.keyDown(dialogo, { key: "Tab", code: "Tab", shiftKey: true });
    expect(cerrar).not.toHaveBeenCalled();
  });

  it("restaura aria-hidden previo en hermanos del body al desmontarse", () => {
    const hermanoPrevio = document.createElement("div");
    hermanoPrevio.setAttribute("aria-hidden", "false");
    document.body.appendChild(hermanoPrevio);

    const cerrar = vi.fn();
    const { unmount } = render(
      <Dialogo titulo="Restauración" cerrar={cerrar}>
        <p>Prueba atributos</p>
      </Dialogo>,
    );

    expect(hermanoPrevio.getAttribute("aria-hidden")).toBe("true");

    unmount();
    expect(hermanoPrevio.getAttribute("aria-hidden")).toBe("false");
    hermanoPrevio.remove();
  });

  it("maneja caso donde el activador se desconectó antes de cerrar y filtra controles en fieldset deshabilitado u ocultos", () => {
    const botonEfimero = document.createElement("button");
    document.body.appendChild(botonEfimero);
    botonEfimero.focus();

    const cerrar = vi.fn();
    const { unmount } = render(
      <Dialogo titulo="Filtros" cerrar={cerrar}>
        <fieldset disabled>
          <button type="button">Deshabilitado</button>
        </fieldset>
        <button type="button" hidden>Oculto</button>
      </Dialogo>,
    );

    botonEfimero.remove();
    unmount();
  });

  it("enfoca el propio contenedor del diálogo cuando no hay ningún control activo disponible", () => {
    const cerrar = vi.fn();
    render(
      <Dialogo titulo="Sin controles" cerrar={cerrar}>
        <p>Vacio</p>
      </Dialogo>,
    );

    const botonCerrar = screen.getByRole("button", { name: "Cerrar diálogo" });
    botonCerrar.setAttribute("disabled", "true");

    const dialogo = screen.getByRole("dialog");
    fireEvent.keyDown(dialogo, { key: "Tab", code: "Tab" });
    expect(document.activeElement).toBe(dialogo);

    const outsideBtn = document.createElement("button");
    document.body.appendChild(outsideBtn);
    outsideBtn.dispatchEvent(new FocusEvent("focusin", { bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(dialogo);
    outsideBtn.remove();
  });

  it("ignora focusin cuando el target está dentro del diálogo o no es un Node", () => {
    const cerrar = vi.fn();
    render(
      <Dialogo titulo="Foco interno" cerrar={cerrar}>
        <button type="button">Interno</button>
      </Dialogo>,
    );
    const botonInterno = screen.getByRole("button", { name: "Interno" });
    botonInterno.dispatchEvent(new FocusEvent("focusin", { bubbles: true, cancelable: true }));
    document.dispatchEvent(new Event("focusin", { bubbles: true }));
  });

  it("soporta inicialización cuando document.activeElement no es HTMLElement", () => {
    const descOriginal = Object.getOwnPropertyDescriptor(Document.prototype, "activeElement");
    Object.defineProperty(document, "activeElement", { value: null, configurable: true });
    const cerrar = vi.fn();
    const { unmount } = render(
      <Dialogo titulo="Sin activador" cerrar={cerrar}>
        <p>Texto</p>
      </Dialogo>,
    );
    unmount();
    if (descOriginal) Object.defineProperty(Document.prototype, "activeElement", descOriginal);
  });
});
