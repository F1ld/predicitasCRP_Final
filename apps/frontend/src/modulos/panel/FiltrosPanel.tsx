import { useState, type FormEvent } from "react";
import { etiqueta } from "../../nucleo/formato/formato";
import { validarFiltros } from "./consulta";
import { ESPECIALIDADES } from "./tipos";

interface Props { fecha: string; especialidad: string; cargando: boolean; deshabilitarActualizar?: boolean; aplicar: (fecha: string, especialidad: string) => void; hoy: () => void; actualizar: () => void }
export default function FiltrosPanel({ fecha, especialidad, cargando, deshabilitarActualizar = false, aplicar, hoy, actualizar }: Props) {
  const [error, setError] = useState("");
  function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const datos = new FormData(e.currentTarget);
    const dia = String(datos.get("fecha") || "");
    const area = String(datos.get("especialidad") || "");
    const mensaje = validarFiltros(dia, area);
    setError(mensaje);
    if (!mensaje) aplicar(dia, area);
  }
  return <form className="tarjeta panel-filtros" aria-label="Filtrar jornada" onSubmit={enviar} noValidate>
    <div><label htmlFor="panel-fecha">Fecha de la jornada</label><input id="panel-fecha" name="fecha" type="date" required defaultValue={fecha} aria-describedby={error ? "panel-error-filtros" : undefined} /></div>
    <div><label htmlFor="panel-especialidad">Especialidad</label><select id="panel-especialidad" name="especialidad" defaultValue={especialidad}>
      <option value="">Todas las especialidades</option>{especialidad && !ESPECIALIDADES.some(e => e === especialidad) && <option value={especialidad}>Especialidad no válida</option>}
      {ESPECIALIDADES.map(e => <option key={e} value={e}>{etiqueta(e)}</option>)}
    </select></div>
    <div className="panel-acciones"><button className="boton" type="submit">Aplicar filtros</button><button className="boton-secundario" type="button" onClick={hoy}>Hoy</button><button className="boton-secundario" type="button" disabled={cargando || deshabilitarActualizar} onClick={actualizar}>{cargando ? "Consultando…" : "Actualizar"}</button></div>
    {error && <p id="panel-error-filtros" className="panel-error" role="alert">{error}</p>}
  </form>;
}
