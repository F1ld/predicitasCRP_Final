import { useEffect, useState } from "react";
import { api } from "./api";

// Cada resultado pertenece a una URL y a un intento. Una respuesta antigua no
// puede reemplazar la consulta vigente, incluso si fetch ya había terminado.
export function useConsulta(ruta) {
  const [intento, setIntento] = useState(0);
  const [resultado, setResultado] = useState(null);
  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    api(ruta, { signal: controlador.signal }).then(
      (datos) => { if (vigente) setResultado({ ruta, intento, datos, error: "" }); },
      (error) => {
        if (vigente && error.name !== "AbortError") {
          setResultado({ ruta, intento, datos: null, error: error.message });
        }
      },
    );
    return () => { vigente = false; controlador.abort(); };
  }, [ruta, intento]);
  const cargando = resultado?.ruta !== ruta || resultado?.intento !== intento;
  return {
    cargando,
    datos: cargando ? null : resultado.datos,
    error: cargando ? "" : resultado.error,
    reintentar: () => setIntento((valor) => valor + 1),
    actualizar: (datos) => setResultado({ ruta, intento, datos, error: "" }),
  };
}
