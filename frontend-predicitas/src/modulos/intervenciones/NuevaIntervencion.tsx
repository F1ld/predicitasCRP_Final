import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../../nucleo/api/cliente";
import { useConsulta } from "../../nucleo/api/useConsulta";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import Dialogo from "./Dialogo";
import { camposError, mensajeError } from "./errores";
import { rotulo } from "./presentacion";
import { CANALES, type CanalContacto, type IntervencionOut, type PlantillaOut } from "./tipos";

interface Propiedades {
  idCita: number;
  referenciaCita?: string;
  cerrar: () => void;
  completado: (intervencion: IntervencionOut) => void;
}

// M05-V02, RF-058, RF-060, RN13: plantillas de la API; nunca se inventa su contenido.
export default function NuevaIntervencion(propiedades: Propiedades) {
  const { datos, cargando, error, reintentar } = useConsulta<PlantillaOut[]>("/intervenciones/plantillas");
  return <Dialogo titulo="Nueva intervención" cerrar={propiedades.cerrar}>
    <p className="m05-ayuda">Cita {propiedades.referenciaCita ?? `#${propiedades.idCita}`}. Registrar la intervención no cambia el estado de la cita.</p>
    <div className="mt-4">
      {cargando ? <Cargando texto="Cargando plantillas…" /> : error ? <><Mensaje>{error}</Mensaje><button className="boton-secundario mt-3" onClick={reintentar}>Reintentar</button></>
        : <Formulario {...propiedades} plantillas={datos ?? []} />}
    </div>
  </Dialogo>;
}

function Formulario({ idCita, cerrar, completado, plantillas }: Propiedades & { plantillas: PlantillaOut[] }) {
  const [canal, setCanal] = useState<CanalContacto>(plantillas[0]?.canal_contacto ?? "WHATSAPP");
  const [idPlantilla, setIdPlantilla] = useState("");
  const [consentimiento, setConsentimiento] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [campos, setCampos] = useState<Record<string, string>>({});
  const enCurso = useRef(false);
  const peticion = useRef<AbortController | null>(null);
  const casilla = useRef<HTMLInputElement>(null);
  useEffect(() => () => { peticion.current?.abort(); }, []);
  const disponibles = plantillas.filter((item) => item.canal_contacto === canal);
  const plantilla = disponibles.find((item) => item.id === idPlantilla) ?? disponibles[0];
  function limpiar(campo: string) { setCampos((antes) => ({ ...antes, [campo]: "" })); setError(""); }
  async function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (enCurso.current) return;
    if (!consentimiento) {
      setError("Confirma el consentimiento antes de crear la intervención.");
      setCampos({ consentimiento_confirmado: "Confirma el consentimiento antes de crear la intervención." });
      casilla.current?.focus(); return;
    }
    if (!plantilla) { setError("Selecciona una plantilla disponible para el canal elegido."); return; }
    enCurso.current = true; setEnviando(true); setError(""); setCampos({});
    const controlador = new AbortController(); peticion.current = controlador;
    try {
      // RF-058, RF-063, RN13: true literal; la elegibilidad y los límites los decide la API.
      const resultado = await api<IntervencionOut>("/intervenciones", { metodo: "POST", signal: controlador.signal,
        json: { id_cita: idCita, canal_contacto: canal, plantilla_mensaje: plantilla.id, consentimiento_confirmado: true } });
      if (controlador.signal.aborted) return;
      if (!resultado) throw new Error("El servidor no confirmó la creación de la intervención.");
      completado(resultado);
    } catch (fallo: unknown) {
      if (!controlador.signal.aborted) { setError(mensajeError(fallo)); setCampos(camposError(fallo)); }
    } finally { enCurso.current = false; if (!controlador.signal.aborted) setEnviando(false); }
  }
  const atributos = (campo: string) => ({ "aria-invalid": Boolean(campos[campo]), "aria-describedby": campos[campo] ? `nueva-${campo}-error` : undefined });
  const detalle = (campo: string) => campos[campo] ? <p id={`nueva-${campo}-error`} className="m05-campo-error">{campos[campo]}</p> : null;
  return <form className="m05-formulario" onSubmit={(evento) => { void guardar(evento); }} noValidate>
    <Mensaje>{error}</Mensaje>
    {!plantillas.length && <Mensaje tipo="info">No hay plantillas disponibles. Solicita al administrador que revise el catálogo antes de continuar.</Mensaje>}
    <fieldset disabled={enviando} className="m05-formulario">
      <div><label htmlFor="nueva-canal">Canal</label><select id="nueva-canal" name="canal_contacto" value={canal} {...atributos("canal_contacto")} onChange={(evento) => { const elegido = CANALES.find((valor) => valor === evento.target.value); if (elegido) { setCanal(elegido); setIdPlantilla(""); limpiar("canal_contacto"); limpiar("plantilla_mensaje"); } }}>{CANALES.map((valor) => <option key={valor} value={valor}>{rotulo(valor)}</option>)}</select>{detalle("canal_contacto")}</div>
      <div><label htmlFor="nueva-plantilla">Plantilla</label><select id="nueva-plantilla" name="plantilla_mensaje" value={plantilla?.id ?? ""} disabled={!disponibles.length || enviando} {...atributos("plantilla_mensaje")} onChange={(evento) => { setIdPlantilla(evento.target.value); limpiar("plantilla_mensaje"); }}>
        {!disponibles.length && <option value="">Sin plantillas para este canal</option>}{disponibles.map((item) => <option key={item.id} value={item.id}>{item.descripcion}</option>)}
      </select>{detalle("plantilla_mensaje")}</div>
      {plantilla && <div><h3 className="mb-2">Contenido de la plantilla</h3><p className="m05-plantilla">{plantilla.contenido}</p></div>}
      <div><label className="m05-consentimiento"><input ref={casilla} type="checkbox" name="consentimiento_confirmado" checked={consentimiento} required {...atributos("consentimiento_confirmado")} onChange={(evento) => { setConsentimiento(evento.target.checked); limpiar("consentimiento_confirmado"); }} /><span>El paciente cuenta con consentimiento para recibir comunicaciones</span></label>{detalle("consentimiento_confirmado")}</div>
    </fieldset>
    <p className="m05-ayuda">El avance de envío y entrega se registra como simulación. Solo se admite una intervención que llegue al paciente y un reintento tras un fallo (RN07).</p>
    <div className="m05-acciones"><button className="boton-secundario" type="button" onClick={cerrar}>Cancelar</button><button className="boton" type="submit" disabled={enviando || !plantilla}>{enviando ? "Creando…" : "Crear intervención"}</button></div>
  </form>;
}
