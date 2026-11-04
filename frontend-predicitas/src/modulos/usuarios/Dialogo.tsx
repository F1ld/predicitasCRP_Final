import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import "./usuarios.css";

const SELECTOR_FOCO = 'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]';

function controlesFoco(dialogo: HTMLElement): HTMLElement[] {
  // El orden debe seguir el DOM incluso si el motor agrupa un selector compuesto.
  return Array.from(dialogo.querySelectorAll<HTMLElement>(SELECTOR_FOCO))
    .sort((a, b) => a === b ? 0 : a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1);
}

// RNF-016: portal modal con fondo inerte, foco atrapado, Escape y retorno al activador.
export default function Dialogo({ titulo, cerrar, children }: { titulo: string; cerrar: () => void; children: ReactNode }) {
  const id = useId();
  const referencia = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const dialogo = referencia.current;
    if (!dialogo) return;
    const activador = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const contenedor = dialogo.parentElement;
    const fondo = Array.from(document.body.children).filter((nodo): nodo is HTMLElement => nodo instanceof HTMLElement && nodo !== contenedor);
    const estados = fondo.map((nodo) => ({ nodo, inerte: nodo.inert, oculto: nodo.getAttribute("aria-hidden") }));
    estados.forEach(({ nodo }) => { nodo.inert = true; nodo.setAttribute("aria-hidden", "true"); });
    const desbordamiento = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    (controlesFoco(dialogo)[0] ?? dialogo).focus();
    const mantenerFoco = (evento: FocusEvent) => {
      if (evento.target instanceof Node && !dialogo.contains(evento.target)) {
        (controlesFoco(dialogo)[0] ?? dialogo).focus();
      }
    };
    document.addEventListener("focusin", mantenerFoco);
    return () => {
      document.removeEventListener("focusin", mantenerFoco);
      estados.forEach(({ nodo, inerte, oculto }) => {
        nodo.inert = inerte;
        if (oculto === null) nodo.removeAttribute("aria-hidden"); else nodo.setAttribute("aria-hidden", oculto);
      });
      document.body.style.overflow = desbordamiento;
      if (activador?.isConnected) activador.focus();
    };
  }, []);

  function teclado(evento: KeyboardEvent<HTMLDivElement>) {
    if (evento.key === "Escape") { evento.preventDefault(); evento.stopPropagation(); cerrar(); }
    if (evento.key !== "Tab") return;
    const controles = referencia.current ? controlesFoco(referencia.current) : [];
    const primero = controles[0];
    const ultimo = controles[controles.length - 1];
    if (!primero || !ultimo) { evento.preventDefault(); referencia.current?.focus(); return; }
    if (evento.shiftKey && (document.activeElement === primero || document.activeElement === referencia.current)) {
      evento.preventDefault(); ultimo.focus();
    } else if (!evento.shiftKey && document.activeElement === ultimo) {
      evento.preventDefault(); primero.focus();
    }
  }

  return createPortal(<div className="usuarios-modal-fondo">
    <div ref={referencia} role="dialog" aria-modal="true" aria-labelledby={id} tabIndex={-1} className="usuarios-dialogo" onKeyDown={teclado}>
      <div className="usuarios-dialogo-cabecera"><h2 id={id}>{titulo}</h2><button type="button" className="boton-secundario" onClick={cerrar} aria-label="Cerrar diálogo">Cerrar</button></div>
      {children}
    </div>
  </div>, document.body);
}
