import { useEffect, useRef, useState } from "react";
import { api, ApiError, esCancelacion } from "../../nucleo/api/cliente";
import Mensaje from "../../nucleo/componentes/Mensaje";

export default function PredecirLote({ alCompletar }: { alCompletar: () => void }) {
  const solicitud = useRef<AbortController | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "error" | "exito"; texto: string } | null>(null);
  useEffect(() => () => solicitud.current?.abort(), []);

  async function predecir() {
    if (solicitud.current) return;
    const controlador = new AbortController();
    solicitud.current = controlador;
    setOcupado(true);
    setAviso(null);
    try {
      const resultado = await api<{ evaluadas: number }>("/ia/predecir-lote", {
        metodo: "POST", signal: controlador.signal,
      });
      if (controlador.signal.aborted) return;
      if (!resultado) throw new Error("El servidor no devolvió el resultado del lote.");
      setAviso({ tipo: "exito", texto: `Citas evaluadas: ${resultado.evaluadas}.` });
      alCompletar();
    } catch (error: unknown) {
      if (controlador.signal.aborted || esCancelacion(error)) return;
      const texto = error instanceof ApiError && error.codigo === "MOTOR_IA_NO_DISPONIBLE"
        ? "Motor de IA no disponible. Puedes seguir consultando las intervenciones."
        : error instanceof Error ? error.message : "No se pudo calcular el riesgo del lote.";
      setAviso({ tipo: "error", texto });
    } finally {
      solicitud.current = null;
      if (!controlador.signal.aborted) setOcupado(false);
    }
  }

  return <div className="space-y-2">
    <button type="button" className="boton-secundario" disabled={ocupado} onClick={predecir}>
      {ocupado ? "Calculando riesgo…" : "Calcular riesgo por lote"}
    </button>
    {aviso && <Mensaje tipo={aviso.tipo}>{aviso.texto}</Mensaje>}
  </div>;
}
