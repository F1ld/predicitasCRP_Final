import { useEffect, useState } from "react";
import { api, esCancelacion } from "./cliente";

interface Resultado<T> { ruta: string; intento: number; datos: T | null; error: string }

// RF-014: cada respuesta pertenece a una URL y a un intento; cancelar o cambiar
// filtros impide que una respuesta anterior reemplace la consulta vigente.
export function useConsulta<T>(ruta: string) {
  const [intento, setIntento] = useState(0);
  const [resultado, setResultado] = useState<Resultado<T> | null>(null);
  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    api<T>(ruta, { signal: controlador.signal }).then(
      (datos) => { if (vigente) setResultado({ ruta, intento, datos, error: "" }); },
      (error: unknown) => {
        if (vigente && !esCancelacion(error)) {
          setResultado({ ruta, intento, datos: null, error: error instanceof Error ? error.message : "No se pudo completar la solicitud." });
        }
      },
    );
    return () => { vigente = false; controlador.abort(); };
  }, [ruta, intento]);
  const cargando = resultado?.ruta !== ruta || resultado?.intento !== intento;
  return {
    cargando,
    datos: cargando ? null : resultado?.datos ?? null,
    error: cargando ? "" : resultado?.error ?? "",
    reintentar: () => setIntento((valor) => valor + 1),
    actualizar: (datos: T | null) => setResultado({ ruta, intento, datos, error: "" }),
  };
}
