import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import "./intervenciones.css";

const SELECTOR = 'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]';
function controles(elemento: HTMLElement): HTMLElement[] {
  return Array.from(elemento.querySelectorAll<HTMLElement>(SELECTOR))
    .filter((control) => !control.closest("fieldset:disabled") && !control.hidden)
    .sort((a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
}

// RNF-016: modal con foco atrapado, Escape, fondo inerte y retorno al activador.
export default function Dialogo({ titulo, cerrar, children }: { titulo: string; cerrar: () => void; children: ReactNode }) {
  const id = useId();
  const referencia = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const dialogo = referencia.current;
    if (!dialogo) return;
    const activador = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const fondo = Array.from(document.body.children).filter((nodo): nodo is HTMLElement => nodo instanceof HTMLElement && nodo !== dialogo.parentElement);
    const estados = fondo.map((nodo) => ({ nodo, inerte: nodo.inert, oculto: nodo.getAttribute("aria-hidden") }));
    estados.forEach(({ nodo }) => { nodo.inert = true; nodo.setAttribute("aria-hidden", "true"); });
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    (controles(dialogo)[0] ?? dialogo).focus();
    const mantener = (evento: FocusEvent) => { if (evento.target instanceof Node && !dialogo.contains(evento.target)) (controles(dialogo)[0] ?? dialogo).focus(); };
    document.addEventListener("focusin", mantener);
    return () => {
      document.removeEventListener("focusin", mantener);
      estados.forEach(({ nodo, inerte, oculto }) => { nodo.inert = inerte; if (oculto === null) nodo.removeAttribute("aria-hidden"); else nodo.setAttribute("aria-hidden", oculto); });
      document.body.style.overflow = overflow;
      if (activador?.isConnected) activador.focus();
    };
  }, []);
  function teclado(evento: KeyboardEvent<HTMLDivElement>) {
    if (evento.key === "Escape") { evento.preventDefault(); evento.stopPropagation(); cerrar(); return; }
    if (evento.key !== "Tab" || !referencia.current) return;
    const lista = controles(referencia.current);
    const primero = lista[0]; const ultimo = lista[lista.length - 1];
    if (!primero || !ultimo) { evento.preventDefault(); referencia.current.focus(); return; }
    if (evento.shiftKey && (document.activeElement === primero || document.activeElement === referencia.current)) { evento.preventDefault(); ultimo.focus(); }
    else if (!evento.shiftKey && document.activeElement === ultimo) { evento.preventDefault(); primero.focus(); }
  }
  return createPortal(<div className="m05-modal-fondo"><div ref={referencia} className="m05-dialogo" role="dialog" aria-modal="true" aria-labelledby={id} tabIndex={-1} onKeyDown={teclado}>
    <div className="m05-dialogo-cabecera"><h2 id={id}>{titulo}</h2><button type="button" className="boton-secundario" aria-label="Cerrar diálogo" onClick={cerrar}>Cerrar</button></div>{children}
  </div></div>, document.body);
}
