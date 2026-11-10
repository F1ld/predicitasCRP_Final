import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError, esCancelacion } from "../../nucleo/api/cliente";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import Icono from "../../nucleo/componentes/Icono";
import RelojLocal from "../../nucleo/componentes/RelojLocal";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { mensajeErrorCitas } from "./errores";
import type { CatalogosOut, CitaDetalleOut, CitaRegistroIn } from "./tipos";
import { ROLES_ESCRITURA } from "./transiciones";
import "./Registrar.css";

type Campo = keyof CitaRegistroIn;
type Formulario = Record<Campo, string>;
type Errores = Partial<Record<Campo, string>>;
const INICIAL: Formulario = {
  id_cita_externa: "", paciente_anon_id: "", sede: "SAN_ISIDRO", especialidad: "", medico: "",
  fecha_hora_cita: "", fecha_registro_cita: "", tipo_paciente: "", canal_origen: "",
  inasistencias_previas: "", asistencias_previas: "", reprogramaciones_prev: "",
};
function generarIdCitaExterna(): string {
  const anio = new Date().getFullYear();
  const aleatorio = Math.floor(100000 + Math.random() * 900000);
  return `CIT-${anio}-${aleatorio}`;
}
const ETIQUETAS: Record<string, string> = {
  CARDIOLOGIA: "Cardiología", TRAUMATOLOGIA: "Traumatología", PEDIATRIA: "Pediatría",
  NUEVO: "Nuevo", CONTINUADOR: "Continuador", WEB: "Web", CALL_CENTER: "Call center", PRESENCIAL: "Presencial",
};

function fechaLocal(valor: string) {
  const fecha = new Date(valor);
  return Number.isFinite(fecha.getTime()) ? fecha.toISOString() : "";
}

function validar(datos: Formulario, catalogos: CatalogosOut | null): Errores {
  const errores: Errores = {};
  for (const [campo, maximo] of [["id_cita_externa", 50], ["paciente_anon_id", 50], ["medico", 100]] as const) {
    if (!datos[campo].trim()) errores[campo] = "Este campo es obligatorio.";
    else if (datos[campo].trim().length > maximo) errores[campo] = `Usa como máximo ${maximo} caracteres.`;
  }
  if (!datos.especialidad) errores.especialidad = "Selecciona la especialidad.";
  else if (!catalogos?.especialidades.includes(datos.especialidad)) errores.especialidad = "Selecciona una especialidad del piloto.";
  if (!datos.tipo_paciente) errores.tipo_paciente = "Selecciona el tipo de paciente.";
  else if (!catalogos?.tipos_paciente.includes(datos.tipo_paciente)) errores.tipo_paciente = "Selecciona un tipo de paciente del catálogo.";
  if (!datos.canal_origen) errores.canal_origen = "Selecciona el canal de origen.";
  else if (!catalogos?.canales_origen.includes(datos.canal_origen)) errores.canal_origen = "Selecciona un canal del catálogo.";
  for (const campo of ["fecha_hora_cita", "fecha_registro_cita"] as const) {
    if (!datos[campo]) errores[campo] = "Indica la fecha y hora.";
    else if (!Number.isFinite(new Date(fechaLocal(datos[campo])).getTime())) errores[campo] = "Indica una fecha y hora válida.";
  }
  if (!errores.fecha_hora_cita && datos.fecha_hora_cita) {
    const dia = new Date(`${datos.fecha_hora_cita.slice(0, 10)}T12:00:00Z`).getUTCDay();
    if (dia === 0) errores.fecha_hora_cita = "Los domingos están fuera del piloto. Revisa la fecha de la cita existente.";
  }
  if (!errores.fecha_registro_cita && datos.fecha_registro_cita && datos.fecha_hora_cita &&
    new Date(fechaLocal(datos.fecha_registro_cita)).getTime() > new Date(fechaLocal(datos.fecha_hora_cita)).getTime()) {
    errores.fecha_registro_cita = "El registro debe ser anterior o igual a la fecha y hora de la cita.";
  }
  for (const campo of ["inasistencias_previas", "asistencias_previas", "reprogramaciones_prev"] as const) {
    if (datos[campo] !== "" && (!/^\d+$/.test(datos[campo]) || !Number.isSafeInteger(Number(datos[campo])))) {
      errores[campo] = "Usa un número entero mayor o igual a 0.";
    }
  }
  return errores;
}

function camposDelServidor(fallo: unknown): Errores {
  if (!(fallo instanceof ApiError)) return {};
  const recibidos: Errores = {};
  for (const [campo, motivo] of Object.entries(fallo.campos)) {
    const nombre = campo.replace(/^body\./, "");
    if (nombre in INICIAL) recibidos[nombre as Campo] = motivo;
  }
  if (Object.keys(recibidos).length > 0) return recibidos;
  if (fallo.codigo === "CITA_DUPLICADA") return { id_cita_externa: "Ya existe una cita con este identificador externo." };
  if (fallo.codigo === "FECHAS_INCONSISTENTES") return {
    fecha_hora_cita: "Revisa la fecha y hora de la cita existente.",
    fecha_registro_cita: "El registro debe ser anterior o igual a la fecha y hora de la cita.",
  };
  if (fallo.codigo === "FUERA_DE_PERIMETRO") return {
    sede: "Revisa que la cita existente corresponda a la sede San Isidro.",
    especialidad: "Revisa que la especialidad pertenezca al piloto.",
    fecha_hora_cita: "Revisa la fecha: los domingos están fuera del piloto.",
  };
  return {};
}

// RF-010, RN03, RN17 y RNF-007: incorpora una cita existente, con seudónimo y sin agendar.
export default function Registrar() {
  const { tieneRol } = useAuth();
  const puedeEscribir = tieneRol(...ROLES_ESCRITURA);
  const navegar = useNavigate();
  const [catalogos, setCatalogos] = useState<CatalogosOut | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState("");
  const [intento, setIntento] = useState(0);
  const [datos, setDatos] = useState<Formulario>(INICIAL);
  const [tocados, setTocados] = useState<Partial<Record<Campo, boolean>>>({});
  const [erroresEntrada, setErroresEntrada] = useState<Errores>({});
  const [erroresServidor, setErroresServidor] = useState<Errores>({});
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [exito, setExito] = useState(false);
  const envioEnCurso = useRef(false);
  const formularioRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (!puedeEscribir) return;
    const controlador = new AbortController();
    api<CatalogosOut>("/citas/catalogos", { signal: controlador.signal })
      .then((resultado) => { if (!controlador.signal.aborted) setCatalogos(resultado); })
      .catch((fallo: unknown) => { if (!esCancelacion(fallo) && !controlador.signal.aborted) setErrorCarga(mensajeErrorCitas(fallo)); })
      .finally(() => { if (!controlador.signal.aborted) setCargando(false); });
    return () => controlador.abort();
  }, [puedeEscribir, intento]);

  const validacion = { ...validar(datos, catalogos), ...erroresEntrada };
  const errores: Errores = { ...Object.fromEntries(Object.entries(validacion).filter(([campo]) => tocados[campo as Campo])), ...erroresServidor };
  const catalogoVacio = !catalogos || catalogos.especialidades.length === 0 || catalogos.tipos_paciente.length === 0 || catalogos.canales_origen.length === 0;

  function cambiar(campo: Campo, valor: string) {
    setDatos((actual) => ({ ...actual, [campo]: valor }));
    setTocados((actual) => ({ ...actual, [campo]: true }));
    setErroresServidor((actual) => {
      const siguientes = { ...actual };
      delete siguientes[campo];
      if (campo === "fecha_hora_cita" || campo === "fecha_registro_cita") {
        delete siguientes.fecha_hora_cita; delete siguientes.fecha_registro_cita;
      }
      return siguientes;
    });
  }

  function propiedades(campo: Campo, ayuda?: string) {
    return {
      id: `registro-${campo}`, name: campo, value: datos[campo],
      "aria-invalid": Boolean(errores[campo]),
      "aria-describedby": [ayuda, errores[campo] ? `error-${campo}` : undefined].filter(Boolean).join(" ") || undefined,
      onChange: (evento: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => cambiar(campo, evento.target.value),
      onInput: (evento: FormEvent<HTMLInputElement | HTMLSelectElement>) => {
        const control = evento.currentTarget;
        // RF-010/RN17: '-' o 'e' pueden tener value vacío y badInput; no son un contador omitido.
        if (control instanceof HTMLInputElement && control.type === "number") {
          const entradaInvalida = control.validity.badInput;
          setTocados((actual) => ({ ...actual, [campo]: true }));
          setErroresEntrada((actual) => {
            const siguientes = { ...actual };
            if (entradaInvalida) siguientes[campo] = "Usa un número entero mayor o igual a 0.";
            else delete siguientes[campo];
            return siguientes;
          });
        }
      },
      onBlur: () => setTocados((actual) => ({ ...actual, [campo]: true })),
    };
  }

  function errorCampo(campo: Campo) {
    return errores[campo] ? <p aria-live="polite" className="registro-error-campo" id={`error-${campo}`}>{errores[campo]}</p> : null;
  }

  async function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!puedeEscribir || envioEnCurso.current || catalogoVacio || cargando || errorCarga) return;
    setTocados(Object.fromEntries(Object.keys(INICIAL).map((campo) => [campo, true])));
    setErroresServidor({}); setError("");
    if (Object.keys(validacion).length > 0) {
      setError("Revisa los campos indicados antes de incorporar la cita.");
      const primerCampo = Object.keys(validacion)[0];
      formularioRef.current?.querySelector<HTMLElement>(`[name="${primerCampo}"]`)?.focus();
      return;
    }
    const peticion: CitaRegistroIn = {
      id_cita_externa: datos.id_cita_externa.trim(), paciente_anon_id: datos.paciente_anon_id.trim(), sede: "SAN_ISIDRO",
      especialidad: datos.especialidad as CitaRegistroIn["especialidad"], medico: datos.medico.trim(),
      fecha_hora_cita: fechaLocal(datos.fecha_hora_cita), fecha_registro_cita: fechaLocal(datos.fecha_registro_cita),
      tipo_paciente: datos.tipo_paciente as CitaRegistroIn["tipo_paciente"], canal_origen: datos.canal_origen as CitaRegistroIn["canal_origen"],
      ...(datos.inasistencias_previas !== "" ? { inasistencias_previas: Number(datos.inasistencias_previas) } : {}),
      ...(datos.asistencias_previas !== "" ? { asistencias_previas: Number(datos.asistencias_previas) } : {}),
      reprogramaciones_prev: datos.reprogramaciones_prev === "" ? 0 : Number(datos.reprogramaciones_prev),
    };
    envioEnCurso.current = true; setEnviando(true);
    try {
      const resultado = await api<CitaDetalleOut>("/citas", { metodo: "POST", json: peticion });
      if (!resultado) throw new Error("El servidor no devolvió la cita incorporada. Revisa la bandeja antes de volver a intentarlo.");
      setExito(true);
      navegar(`/citas/${resultado.id_cita}`, { replace: true, state: { mensaje: "Cita incorporada al piloto.", volver: "/citas" } });
    } catch (fallo: unknown) {
      setError(mensajeErrorCitas(fallo));
      const campos = camposDelServidor(fallo);
      setErroresServidor(campos);
      const primerCampo = Object.keys(campos)[0];
      if (primerCampo) requestAnimationFrame(() => formularioRef.current?.querySelector<HTMLElement>(`[name="${primerCampo}"]`)?.focus());
    } finally { envioEnCurso.current = false; setEnviando(false); }
  }

  return <>
    <Link className="volver-enlace" to="/citas">← Volver a la bandeja</Link>
    <div className="pagina-titulo"><div><p className="sobretitulo">INCORPORACIÓN AL PILOTO</p><h1>Registrar cita existente</h1><p>Transcribe los datos de una cita ya agendada para incorporarla al seguimiento.</p></div><span className="contexto-horario"><RelojLocal /></span></div>
    <div className="registro-aviso"><Icono nombre="archivo" /><p>Solo incorpora al piloto una cita que ya existe; no agenda</p></div>
    {!puedeEscribir ? <Mensaje tipo="info">Tu rol permite consultar las citas. El registro está disponible para Recepción y Administración.</Mensaje> : <>
      {cargando && <Cargando texto="Cargando catálogos…" />}
      {errorCarga && <Mensaje>{errorCarga}<button type="button" className="boton-secundario registro-reintento" onClick={() => { setErrorCarga(""); setCargando(true); setIntento((actual) => actual + 1); }}>Reintentar</button></Mensaje>}
      {!cargando && !errorCarga && catalogoVacio && <Mensaje tipo="info">No hay opciones en los catálogos necesarios para registrar la cita. Consulta con Administración.<button type="button" className="boton-secundario registro-reintento" onClick={() => { setCargando(true); setIntento((actual) => actual + 1); }}>Actualizar catálogos</button></Mensaje>}
      {!cargando && !errorCarga && !catalogoVacio && catalogos && <>
        {error && <Mensaje>{error}</Mensaje>}
        {exito && <Mensaje tipo="exito">Cita incorporada al piloto.</Mensaje>}
        {enviando && <p role="status" className="registro-enviando">Incorporando la cita al piloto…</p>}
        <form ref={formularioRef} onSubmit={guardar} noValidate aria-label="Registrar cita existente" className="registro-cita">
          <fieldset disabled={enviando || exito}>
            <section className="tarjeta registro-seccion" aria-labelledby="registro-identificacion"><div className="seccion-cabecera"><div><h2 id="registro-identificacion">1. Identificación de la cita</h2><p>Los campos marcados con * son obligatorios.</p></div></div><div className="registro-campos">
              <div>
                <div className="registro-etiqueta-fila">
                  <label htmlFor="registro-id_cita_externa">ID de cita externa *</label>
                  <button
                    type="button"
                    className="boton-enlace-generar"
                    onClick={() => cambiar("id_cita_externa", generarIdCitaExterna())}
                    title="Generar un nuevo código aleatorio"
                  >
                    Generar otro código
                  </button>
                </div>
                <div className="registro-id-grupo">
                  <input {...propiedades("id_cita_externa")} required maxLength={50} autoComplete="off" placeholder="Ej. CIT-2026-104928" />
                  <button
                    type="button"
                    className="boton-secundario boton-generar-id"
                    onClick={() => cambiar("id_cita_externa", generarIdCitaExterna())}
                    title="Generar identificador"
                  >
                    Generar
                  </button>
                </div>
                <p className="registro-ayuda">Generado automáticamente. Puedes editarlo o hacer clic en «Generar» para obtener otro.</p>
                {errorCampo("id_cita_externa")}
              </div>
              <div><label htmlFor="registro-paciente_anon_id">ID seudonimizado del paciente *</label><input {...propiedades("paciente_anon_id", "registro-ayuda-paciente")} required maxLength={50} autoComplete="off" /><p className="registro-ayuda" id="registro-ayuda-paciente">Usa el seudónimo; no ingreses nombres, DNI ni datos personales.</p>{errorCampo("paciente_anon_id")}</div>
              <div><label htmlFor="registro-sede">Sede</label><input {...propiedades("sede")} value="San Isidro" readOnly />{errorCampo("sede")}</div>
              <div><label htmlFor="registro-especialidad">Especialidad *</label><select {...propiedades("especialidad")} required><option value="">Selecciona una especialidad</option>{catalogos.especialidades.map((opcion) => <option value={opcion} key={opcion}>{ETIQUETAS[opcion] || opcion}</option>)}</select>{errorCampo("especialidad")}</div>
              <div className="registro-campo-completo"><label htmlFor="registro-medico">Médico *</label><input {...propiedades("medico")} list="registro-medicos" required maxLength={100} autoComplete="off" /><datalist id="registro-medicos">{catalogos.medicos.map((medico) => <option value={medico} key={medico} />)}</datalist>{errorCampo("medico")}</div>
            </div></section>
            <section className="tarjeta registro-seccion" aria-labelledby="registro-fechas"><div className="seccion-cabecera"><div><h2 id="registro-fechas">2. Fechas y origen</h2><p>Ingresa ambas fechas según la cita original, en hora local.</p></div></div><div className="registro-campos">
              <div><label htmlFor="registro-fecha_hora_cita">Fecha y hora de la cita *</label><input {...propiedades("fecha_hora_cita")} type="datetime-local" required />{errorCampo("fecha_hora_cita")}</div>
              <div><label htmlFor="registro-fecha_registro_cita">Fecha y hora de registro original *</label><input {...propiedades("fecha_registro_cita")} type="datetime-local" required />{errorCampo("fecha_registro_cita")}</div>
              <div><label htmlFor="registro-tipo_paciente">Tipo de paciente *</label><select {...propiedades("tipo_paciente")} required><option value="">Selecciona un tipo</option>{catalogos.tipos_paciente.map((opcion) => <option value={opcion} key={opcion}>{ETIQUETAS[opcion] || opcion}</option>)}</select>{errorCampo("tipo_paciente")}</div>
              <div><label htmlFor="registro-canal_origen">Canal de origen *</label><select {...propiedades("canal_origen")} required><option value="">Selecciona un canal</option>{catalogos.canales_origen.map((opcion) => <option value={opcion} key={opcion}>{ETIQUETAS[opcion] || opcion}</option>)}</select>{errorCampo("canal_origen")}</div>
            </div></section>
            <section className="tarjeta registro-seccion" aria-labelledby="registro-historial"><div className="seccion-cabecera"><div><h2 id="registro-historial">3. Historial conocido al registrar</h2><p>Opcional. Copia estos contadores solo si la fuente original los incluye.</p></div></div><p id="registro-ayuda-contadores" className="registro-ayuda registro-ayuda-contadores">Si dejas vacías las inasistencias y asistencias, el sistema las calcula con citas del mismo paciente anteriores al registro original. Las reprogramaciones vacías empiezan en 0.</p><div className="registro-campos registro-contadores">
              <div><label htmlFor="registro-inasistencias_previas">Inasistencias previas</label><input {...propiedades("inasistencias_previas", "registro-ayuda-contadores")} type="number" min="0" step="1" inputMode="numeric" />{errorCampo("inasistencias_previas")}</div>
              <div><label htmlFor="registro-asistencias_previas">Asistencias previas</label><input {...propiedades("asistencias_previas", "registro-ayuda-contadores")} type="number" min="0" step="1" inputMode="numeric" />{errorCampo("asistencias_previas")}</div>
              <div><label htmlFor="registro-reprogramaciones_prev">Reprogramaciones previas</label><input {...propiedades("reprogramaciones_prev", "registro-ayuda-contadores")} type="number" min="0" step="1" inputMode="numeric" />{errorCampo("reprogramaciones_prev")}</div>
            </div></section>
            <div className="registro-acciones"><p>La cita se incorpora con estado Recibida.</p><div><Link to="/citas" className="boton-secundario" aria-disabled={enviando || exito} onClick={(evento) => { if (enviando || exito) evento.preventDefault(); }}>Cancelar</Link><button className="boton" type="submit" disabled={enviando || exito}><Icono nombre="check" />{enviando ? "Guardando…" : "Registrar cita"}</button></div></div>
          </fieldset>
        </form>
      </>}
    </>}
  </>;
}
