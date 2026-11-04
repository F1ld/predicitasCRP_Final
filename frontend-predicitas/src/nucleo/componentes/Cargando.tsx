// RNF-016: estado anunciado, animación decorativa y movimiento reducido.
export default function Cargando({ texto = "Cargando…" }: { texto?: string }) {
  return <div role="status" className="flex items-center justify-center gap-3 p-8 text-sm text-slate-600">
    <span aria-hidden="true" className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-teal-700 motion-reduce:animate-none" />
    {texto}
  </div>;
}
