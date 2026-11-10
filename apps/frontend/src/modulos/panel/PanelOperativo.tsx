import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../nucleo/auth/useAuth";
import { useConsulta } from "../../nucleo/api/useConsulta";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta } from "../../nucleo/formato/formato";
import { leerConsulta, parametrosPanel, rutaPanel, rutasApi, type ConsultaPanel } from "./consulta";
import { fechaPanel, horaPanel, hoyLima } from "./formato";
import { esPaginaPanel, esResumenPanel } from "./validacion";
import FiltrosPanel from "./FiltrosPanel";
import { DesglosesPanel, TarjetasPanel } from "./ResumenPanel";
import PendientesPanel from "./PendientesPanel";
import { parametrosReporte, RUTA_REPORTE_DIARIO } from "./contratoReporteDiario";
import "./panel.css";

const ERROR_DATOS = "El servidor no devolvió los datos esperados. Vuelve a consultar.";

export default function PanelOperativo() {
  const { tieneRol } = useAuth();
  return tieneRol("RECEPCION", "ADMINISTRADOR") ? <PanelAutorizado puedeVerReporte={tieneRol("RECEPCION")} /> : <Mensaje>No tienes permiso para consultar el panel operativo.</Mensaje>;
}

function PanelAutorizado({ puedeVerReporte }: { puedeVerReporte: boolean }) {
  const [parametros, setParametros] = useSearchParams();
  const { consulta, error, normalizada } = leerConsulta(parametros);
  const actual = parametros.toString();
  useEffect(() => {
    if (actual !== normalizada) setParametros(normalizada, { replace: true });
  }, [actual, normalizada, setParametros]);
  const cambiar = (siguiente: ConsultaPanel) => setParametros(parametrosPanel(siguiente));
  const filtrosReporte = parametrosReporte({ fecha: consulta.fecha, especialidad: consulta.especialidad, nivel_riesgo: "" });
  return <div className="panel-vista">
    <div className="pagina-titulo"><div><p className="sobretitulo">RECEPCIÓN · JORNADA OPERATIVA</p><h1>Panel operativo</h1><p>Resumen de la jornada y tareas pendientes de atención.</p></div>
      {puedeVerReporte && <Link className="boton-secundario" to={error ? RUTA_REPORTE_DIARIO : `${RUTA_REPORTE_DIARIO}?${filtrosReporte}`}
        state={error ? undefined : { volver: rutaPanel(consulta) }}>Reporte diario</Link>}
    </div>
    {error ? <>
      <FiltrosPanel key={`${consulta.fecha}|${consulta.especialidad}`} fecha={consulta.fecha} especialidad={consulta.especialidad} cargando={false} deshabilitarActualizar
        aplicar={(fecha, especialidad) => cambiar({ ...consulta, fecha, especialidad, desplazamiento: 0 })}
        hoy={() => cambiar({ ...consulta, fecha: hoyLima(), desplazamiento: 0 })} actualizar={() => undefined} />
      <Mensaje>{error}</Mensaje>
    </> : actual !== normalizada ? <Cargando texto="Preparando la jornada…" /> : <ContenidoPanel consulta={consulta} cambiar={cambiar} />}
  </div>;
}

function ContenidoPanel({ consulta, cambiar }: { consulta: ConsultaPanel; cambiar: (siguiente: ConsultaPanel) => void }) {
  const rutas = rutasApi(consulta);
  const resumen = useConsulta<unknown>(rutas.resumen);
  const lista = useConsulta<unknown>(rutas.pendientes);
  const datosResumen = esResumenPanel(resumen.datos) && resumen.datos.fecha === consulta.fecha && resumen.datos.especialidad === (consulta.especialidad || null) ? resumen.datos : null;
  const datosLista = esPaginaPanel(lista.datos) && lista.datos.tipo === consulta.tipo && lista.datos.fecha === consulta.fecha && lista.datos.especialidad === (consulta.especialidad || null) && lista.datos.desplazamiento === consulta.desplazamiento ? lista.datos : null;
  function aplicar(fecha: string, especialidad: string) {
    const siguiente = { ...consulta, fecha, especialidad, desplazamiento: 0 };
    if (rutasApi(siguiente).resumen === rutas.resumen) resumen.reintentar();
    if (rutaPanel(siguiente) === rutaPanel(consulta)) lista.reintentar();
    cambiar(siguiente);
  }
  return <>
    <FiltrosPanel key={`${consulta.fecha}|${consulta.especialidad}`} fecha={consulta.fecha} especialidad={consulta.especialidad}
      cargando={resumen.cargando || lista.cargando} aplicar={aplicar} hoy={() => aplicar(hoyLima(), consulta.especialidad)}
      actualizar={() => { resumen.reintentar(); lista.reintentar(); }} />
    <div className="panel-contexto"><p><strong>{fechaPanel(consulta.fecha)}</strong> · {consulta.especialidad ? etiqueta(consulta.especialidad) : "Todas las especialidades"}</p>
      {datosResumen && <p>Resumen consultado a las {horaPanel(datosResumen.generado_en)} · Lima</p>}
    </div>
    <div aria-busy={resumen.cargando}>{resumen.cargando ? <Cargando texto="Cargando resumen de la jornada…" /> : !datosResumen ? <div className="panel-error-bloque"><Mensaje>{resumen.error || ERROR_DATOS}</Mensaje><button type="button" className="boton-secundario" onClick={resumen.reintentar}>Reintentar resumen</button></div> : <TarjetasPanel datos={datosResumen} />}</div>
    <PendientesPanel tipo={consulta.tipo} resumen={datosResumen} datos={datosLista} cargando={lista.cargando}
      error={!lista.cargando && !datosLista ? lista.error || ERROR_DATOS : ""} volver={rutaPanel(consulta)}
      seleccionar={tipo => { if (tipo !== consulta.tipo) cambiar({ ...consulta, tipo, desplazamiento: 0 }); }}
      paginar={desplazamiento => cambiar({ ...consulta, desplazamiento })} reintentar={lista.reintentar} />
    {datosResumen && <DesglosesPanel datos={datosResumen} />}
  </>;
}
