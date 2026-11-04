import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../nucleo/api/cliente";
import type { Pagina } from "../../nucleo/api/tipos";
import { useConsulta } from "../../nucleo/api/useConsulta";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta, formatearFechaHora } from "../../nucleo/formato/formato";
import { mensajeErrorM06 } from "./errores";
import { ESPECIALIDADES, ESTADOS_CANDIDATO, FRANJAS, ROLES_ESCRITURA, type CandidatoCambioIn, type CandidatoOut, type CandidatoRegistroIn } from "./tipos";
import "./lista-espera.css";

const FILTROS = ["q", "especialidad_req", "franja_preferida", "estado_candidato"] as const;
const ESTADOS = { ACTIVO: "Activo", CONTACTADO: "Contactado", ASIGNADO: "Asignado", DESISTIDO: "Desistido" };
const nombreFranja = (franja: string) => franja === "INDIFERENTE" ? "Indiferente" : etiqueta(franja);
function pertenece<T extends string>(valor: string, opciones: readonly T[]): valor is T {
  return opciones.some((opcion) => opcion === valor);
}

// RF-069 a RF-072 y RNF-028: la barrera local impide consultar o montar M06
// para Técnico IA, incluso al renderizar la vista fuera del router protegido.
export default function ListaEspera() {
  const { tieneRol } = useAuth();
  return tieneRol(...ROLES_ESCRITURA) ? <ListaEsperaContenido /> : <Mensaje>No tienes permiso para esta sección.</Mensaje>;
}

function ListaEsperaContenido() {
  const [busqueda, setBusqueda] = useSearchParams();
  const offset = Number(busqueda.get("desplazamiento") || 0);
  const desplazamiento = Number.isSafeInteger(offset) && offset >= 0 ? offset : 0;
  const tamano = Number(busqueda.get("limite") || 50);
  const limite = Number.isSafeInteger(tamano) && tamano >= 1 && tamano <= 200 ? tamano : 50;
  const consulta = new URLSearchParams({ limite: String(limite), desplazamiento: String(desplazamiento) });
  FILTROS.forEach((nombre) => { const valor = busqueda.get(nombre); if (valor) consulta.set(nombre, valor); });
  const { datos, error, cargando, reintentar } = useConsulta<Pagina<CandidatoOut>>(`/lista-espera?${consulta}`);
  const [operacion, setOperacion] = useState<"registro" | "edicion" | "desistir" | null>(null);
  const enCurso = useRef(false);
  const [errorRegistro, setErrorRegistro] = useState("");
  const [camposRegistro, setCamposRegistro] = useState<Record<string, string>>({});
  const [errorCambio, setErrorCambio] = useState("");
  const [camposCambio, setCamposCambio] = useState<Record<string, string>>({});
  const [exito, setExito] = useState("");
  const [seleccionado, setSeleccionado] = useState<CandidatoOut | null>(null);
  const franjaEdicion = useRef<HTMLSelectElement>(null);
  const origenEdicion = useRef<HTMLButtonElement | null>(null);
  useEffect(() => { if (seleccionado) franjaEdicion.current?.focus(); }, [seleccionado]);

  function filtrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const formulario = new FormData(evento.currentTarget);
    const siguientes = new URLSearchParams();
    FILTROS.forEach((nombre) => {
      const valor = String(formulario.get(nombre) || "").trim();
      if (valor) siguientes.set(nombre, valor);
    });
    if (busqueda.has("limite")) siguientes.set("limite", String(limite));
    setBusqueda(siguientes);
  }

  function paginar(nuevo: number) {
    const siguientes = new URLSearchParams(busqueda);
    siguientes.set("desplazamiento", String(nuevo));
    setBusqueda(siguientes);
  }

  // RF-069, RF-070, RN05: solo se envían los tres campos del contrato.
  // prioridad_registro y estado_candidato los asigna exclusivamente el servidor.
  async function registrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (enCurso.current) return;
    const formulario = evento.currentTarget;
    const valores = new FormData(formulario);
    const paciente_anon_id = String(valores.get("paciente_anon_id") || "").trim();
    const especialidad_req = String(valores.get("especialidad_req") || "");
    const franja_preferida = String(valores.get("franja_preferida") || "");
    const campos: Record<string, string> = {};
    if (!paciente_anon_id || paciente_anon_id.length > 50) campos.paciente_anon_id = "Ingresa un identificador seudonimizado de 1 a 50 caracteres.";
    if (!pertenece(especialidad_req, ESPECIALIDADES)) campos.especialidad_req = "Selecciona una especialidad del piloto.";
    if (!pertenece(franja_preferida, FRANJAS)) campos.franja_preferida = "Selecciona una franja preferida.";
    setCamposRegistro(campos);
    setErrorRegistro("");
    setExito("");
    if (Object.keys(campos).length || !pertenece(especialidad_req, ESPECIALIDADES) || !pertenece(franja_preferida, FRANJAS)) return;
    const cuerpo: CandidatoRegistroIn = { paciente_anon_id, especialidad_req, franja_preferida };
    enCurso.current = true;
    setOperacion("registro");
    try {
      const candidato = await api<CandidatoOut>("/lista-espera", { metodo: "POST", json: cuerpo });
      if (!candidato) throw new Error("El servidor no devolvió el candidato registrado.");
      formulario.reset();
      setExito(`Candidato registrado. Orden de inscripción asignado por el sistema: ${candidato.prioridad_registro}. Si no aparece, revisa los filtros.`);
      reintentar();
    } catch (fallo: unknown) {
      const mensaje = mensajeErrorM06(fallo);
      setErrorRegistro(mensaje);
      if (fallo instanceof ApiError) setCamposRegistro({ ...fallo.campos, ...(fallo.codigo === "CANDIDATO_DUPLICADO" ? { paciente_anon_id: mensaje } : {}) });
    } finally {
      enCurso.current = false;
      setOperacion(null);
    }
  }

  // RF-071: el PATCH cambia solo disponibilidad o registra el desistimiento;
  // CONTACTADO y ASIGNADO pertenecen al flujo de ofertas del servidor (F-11).
  async function cambiar(candidato: CandidatoOut, cuerpo: CandidatoCambioIn, tipo: "edicion" | "desistir") {
    if (enCurso.current) return;
    enCurso.current = true;
    setOperacion(tipo);
    setErrorCambio("");
    setCamposCambio({});
    setExito("");
    try {
      const actualizado = await api<CandidatoOut>(`/lista-espera/${candidato.id_candidato}`, { metodo: "PATCH", json: cuerpo });
      if (!actualizado) throw new Error("El servidor no devolvió el candidato actualizado.");
      setExito(tipo === "edicion" ? "Franja preferida actualizada." : "Candidato marcado como desistido.");
      setSeleccionado(null);
      reintentar();
    } catch (fallo: unknown) {
      setErrorCambio(mensajeErrorM06(fallo));
      if (fallo instanceof ApiError) setCamposCambio(fallo.campos);
    } finally {
      enCurso.current = false;
      setOperacion(null);
    }
  }

  function guardarFranja(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!seleccionado || enCurso.current) return;
    const franja_preferida = String(new FormData(evento.currentTarget).get("franja_preferida") || "");
    if (!pertenece(franja_preferida, FRANJAS)) {
      setCamposCambio({ franja_preferida: "Selecciona una franja preferida." });
      return;
    }
    void cambiar(seleccionado, { franja_preferida }, "edicion");
  }

  return <div className="m06-vista">
    <div className="pagina-titulo"><div><p className="sobretitulo">REASIGNACIÓN ASISTIDA</p><h1>Lista de espera</h1><p>Registra la disponibilidad de los pacientes para los cupos liberados.</p></div><button className="boton-secundario" disabled={cargando || !!operacion} onClick={reintentar}>Actualizar lista</button></div>
    <p className="m06-aviso">El orden de inscripción dentro de cada especialidad lo asigna el sistema. La disponibilidad se registra mediante la franja preferida.</p>
    {exito && <Mensaje tipo="exito">{exito}</Mensaje>}
    <section className="tarjeta" aria-labelledby="lista-registro-titulo">
      <div className="seccion-cabecera"><h2 id="lista-registro-titulo">Registrar candidato</h2><p>Utiliza únicamente el identificador seudonimizado del paciente.</p></div>
      <form noValidate aria-labelledby="lista-registro-titulo" onSubmit={(evento) => { void registrar(evento); }} onChange={(evento) => {
        const control = evento.target;
        if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) setCamposRegistro((previos) => ({ ...previos, [control.name]: "" }));
      }}>
        <fieldset disabled={!!operacion} className="m06-formulario"><legend className="sr-only">Datos del candidato</legend>
          <div><label htmlFor="lista-paciente">Identificador del paciente</label><input id="lista-paciente" name="paciente_anon_id" maxLength={50} required aria-describedby="lista-paciente-ayuda lista-paciente-error" aria-invalid={!!camposRegistro.paciente_anon_id} /><p id="lista-paciente-ayuda" className="ayuda-seccion">Identificador seudonimizado, sin nombres ni documentos.</p><p id="lista-paciente-error" className="m06-error-campo">{camposRegistro.paciente_anon_id}</p></div>
          <div><label htmlFor="lista-especialidad">Especialidad requerida</label><select id="lista-especialidad" name="especialidad_req" defaultValue="" required aria-invalid={!!camposRegistro.especialidad_req} aria-describedby="lista-especialidad-error"><option value="">Selecciona una especialidad</option>{ESPECIALIDADES.map((valor) => <option key={valor} value={valor}>{etiqueta(valor)}</option>)}</select><p id="lista-especialidad-error" className="m06-error-campo">{camposRegistro.especialidad_req}</p></div>
          <div><label htmlFor="lista-franja">Franja preferida</label><select id="lista-franja" name="franja_preferida" defaultValue="" required aria-invalid={!!camposRegistro.franja_preferida} aria-describedby="lista-franja-error"><option value="">Selecciona una franja</option>{FRANJAS.map((valor) => <option key={valor} value={valor}>{nombreFranja(valor)}</option>)}</select><p id="lista-franja-error" className="m06-error-campo">{camposRegistro.franja_preferida}</p></div>
          <div className="m06-acciones"><button className="boton" type="submit">{operacion === "registro" ? "Registrando…" : "Registrar candidato"}</button></div>
        </fieldset>
      </form>
      {errorRegistro && <Mensaje>{errorRegistro}</Mensaje>}
    </section>
    {errorCambio && <Mensaje>{errorCambio}</Mensaje>}
    {seleccionado && <section className="tarjeta" aria-labelledby="lista-edicion-titulo">
      <h2 id="lista-edicion-titulo">Cambiar franja de {seleccionado.paciente_anon_id}</h2>
      <form key={seleccionado.id_candidato} aria-labelledby="lista-edicion-titulo" noValidate onSubmit={guardarFranja}>
        <fieldset disabled={!!operacion} className="m06-formulario"><legend className="sr-only">Actualizar disponibilidad</legend>
          <div><label htmlFor="lista-nueva-franja">Nueva franja preferida</label><select id="lista-nueva-franja" ref={franjaEdicion} name="franja_preferida" defaultValue={seleccionado.franja_preferida} aria-invalid={!!camposCambio.franja_preferida} aria-describedby="lista-edicion-error" onChange={() => setCamposCambio({})}>{FRANJAS.map((valor) => <option key={valor} value={valor}>{nombreFranja(valor)}</option>)}</select><p id="lista-edicion-error" className="m06-error-campo">{camposCambio.franja_preferida}</p></div>
          <div className="m06-acciones"><button className="boton" type="submit">{operacion === "edicion" ? "Guardando…" : "Guardar franja"}</button><button className="boton-secundario" type="button" onClick={() => { setSeleccionado(null); setErrorCambio(""); setCamposCambio({}); origenEdicion.current?.focus(); }}>Cancelar edición</button></div>
        </fieldset>
      </form>
    </section>}
    <form key={busqueda.toString()} className="tarjeta" aria-labelledby="lista-filtros-titulo" onSubmit={filtrar}>
      <div className="seccion-cabecera"><h2 id="lista-filtros-titulo">Filtrar candidatos</h2></div>
      <fieldset className="m06-formulario" disabled={cargando || !!operacion}><legend className="sr-only">Filtros de la lista de espera</legend>
        <div><label htmlFor="lista-filtro-q">Buscar paciente</label><input id="lista-filtro-q" name="q" defaultValue={busqueda.get("q") || ""} /></div>
        <div><label htmlFor="lista-filtro-especialidad">Especialidad</label><select id="lista-filtro-especialidad" name="especialidad_req" defaultValue={busqueda.get("especialidad_req") || ""}><option value="">Todas</option>{ESPECIALIDADES.map((valor) => <option key={valor} value={valor}>{etiqueta(valor)}</option>)}</select></div>
        <div><label htmlFor="lista-filtro-franja">Franja</label><select id="lista-filtro-franja" name="franja_preferida" defaultValue={busqueda.get("franja_preferida") || ""}><option value="">Todas</option>{FRANJAS.map((valor) => <option key={valor} value={valor}>{nombreFranja(valor)}</option>)}</select></div>
        <div><label htmlFor="lista-filtro-estado">Estado del candidato</label><select id="lista-filtro-estado" name="estado_candidato" defaultValue={busqueda.get("estado_candidato") || ""}><option value="">Todos</option>{ESTADOS_CANDIDATO.map((valor) => <option key={valor} value={valor}>{ESTADOS[valor]}</option>)}</select></div>
        <div className="m06-acciones"><button className="boton" type="submit">Aplicar filtros</button><button className="boton-secundario" type="button" onClick={(evento) => { evento.currentTarget.form?.reset(); setBusqueda({}); }}>Limpiar filtros</button></div>
      </fieldset>
    </form>
    {cargando ? <Cargando texto="Cargando lista de espera…" /> : error ? <div className="space-y-3"><Mensaje>{error}</Mensaje><button className="boton-secundario" onClick={reintentar}>Reintentar lista</button></div> : (() => {
      const listaCandidatos = Array.isArray(datos) ? datos : (datos?.items ?? []);
      const totalCandidatos = typeof datos?.total === "number" ? datos.total : listaCandidatos.length;
      return <>
      <div className="resultados-cabecera"><h2>Candidatos <span className="contador-citas">{totalCandidatos}</span></h2><p>Se conserva el orden enviado por el sistema.</p></div>
      <div className="tabla-contenedor" role="region" aria-label="Candidatos de la lista de espera" tabIndex={0}>
        <table className="tabla-citas w-full"><caption className="sr-only">Candidatos ordenados por especialidad, inscripción y fecha de registro</caption><thead><tr><th scope="col">Paciente</th><th scope="col">Especialidad</th><th scope="col">Franja preferida</th><th scope="col">Estado</th><th scope="col">Orden de inscripción</th><th scope="col">Fecha de registro</th><th scope="col">Acciones</th></tr></thead>
          <tbody>{listaCandidatos.length === 0 ? <tr><td colSpan={7}><div className="estado-vacio"><p>No hay candidatos con estos filtros.</p><span>Amplía la búsqueda o registra un candidato.</span></div></td></tr> : listaCandidatos.map((candidato) => <tr key={candidato.id_candidato}>
            <th scope="row">{candidato.paciente_anon_id}</th><td>{etiqueta(candidato.especialidad_req)}</td><td>{nombreFranja(candidato.franja_preferida)}</td><td><span className="m06-estado">{ESTADOS[candidato.estado_candidato]}</span></td><td>{candidato.prioridad_registro}</td><td>{formatearFechaHora(candidato.fecha_registro)}</td>
            <td>{candidato.estado_candidato === "ASIGNADO" || candidato.estado_candidato === "DESISTIDO" ? "Sin acciones disponibles" : <div className="m06-acciones"><button className="boton-secundario" disabled={!!operacion} onClick={(evento) => { origenEdicion.current = evento.currentTarget; setSeleccionado(candidato); setErrorCambio(""); setCamposCambio({}); }}>Cambiar franja{" "}<span className="sr-only">de {candidato.paciente_anon_id}</span></button><button className="boton-secundario" disabled={!!operacion} onClick={() => { void cambiar(candidato, { estado_candidato: "DESISTIDO" }, "desistir"); }}>Marcar desistido{" "}<span className="sr-only">a {candidato.paciente_anon_id}</span></button></div>}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <div className="paginacion"><p>Página {Math.floor(desplazamiento / limite) + 1} de {Math.max(1, Math.ceil(totalCandidatos / limite))}</p><div className="m06-acciones"><button className="boton-secundario" disabled={desplazamiento === 0 || !!operacion} onClick={() => paginar(Math.max(0, desplazamiento - limite))}>Anterior</button><button className="boton-secundario" disabled={desplazamiento + limite >= totalCandidatos || !!operacion} onClick={() => paginar(desplazamiento + limite)}>Siguiente</button></div></div>
    </>;
    })()}
  </div>;
}
