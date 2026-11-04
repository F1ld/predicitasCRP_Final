import { useEffect, useRef, useState } from "react";
import { api } from "../../nucleo/api/cliente";
import Mensaje from "../../nucleo/componentes/Mensaje";
import Dialogo from "./Dialogo";
import type { ClaveTemporalOut, UsuarioOut } from "./tipos";
import { mensajeError } from "./validacion";

interface Propiedades { usuario: UsuarioOut; cerrar: () => void; completado: (mensaje: string) => void }

// RF-006, RNF-001: baja lógica explícita, confirmación y protección de administradores.
export function CambiarEstado({ usuario, cerrar, completado }: Propiedades) {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const ocupado = useRef(false);
  const peticion = useRef<AbortController | null>(null);
  useEffect(() => () => { peticion.current?.abort(); }, []);
  const accion = usuario.activo ? "Desactivar" : "Activar";

  async function confirmar() {
    if (ocupado.current) return;
    ocupado.current = true;
    setEnviando(true); setError("");
    const controlador = new AbortController();
    peticion.current = controlador;
    try {
      const actualizado = await api<UsuarioOut>(`/usuarios/${usuario.id_usuario}/estado`, { metodo: "POST", json: { activo: !usuario.activo }, signal: controlador.signal });
      if (controlador.signal.aborted) return;
      if (!actualizado) throw new Error("El servidor no confirmó el estado del usuario.");
      completado(usuario.activo ? "Usuario desactivado correctamente." : "Usuario activado correctamente.");
    } catch (fallo: unknown) {
      if (!controlador.signal.aborted) setError(mensajeError(fallo));
    } finally { ocupado.current = false; if (!controlador.signal.aborted) setEnviando(false); }
  }

  return <Dialogo titulo={`${accion} usuario`} cerrar={cerrar}>
    <p>¿Confirmas que deseas {accion.toLowerCase()} a <strong>{usuario.nombre_completo}</strong>?</p>
    <p className="usuarios-ayuda">{usuario.activo ? "Perderá el acceso y sus sesiones dejarán de ser válidas. Se conservarán su historial y su auditoría." : "Podrá volver a iniciar sesión con su contraseña vigente."}</p>
    <div className="mt-4"><Mensaje>{error}</Mensaje></div>
    <div className="usuarios-acciones"><button type="button" className="boton-secundario" onClick={cerrar}>Cancelar</button><button type="button" className="boton" onClick={confirmar} disabled={enviando}>{enviando ? "Guardando…" : `${accion} usuario`}</button></div>
  </Dialogo>;
}

// RF-008: la clave existe solo en memoria mientras el diálogo está montado.
// El POST se origina al confirmar; ni el render ni un efecto generan otra clave.
export function RestablecerAcceso({ usuario, cerrar }: Omit<Propiedades, "completado">) {
  const [clave, setClave] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const ocupado = useRef(false);
  const botonCopiar = useRef<HTMLButtonElement>(null);
  const peticion = useRef<AbortController | null>(null);
  useEffect(() => () => { peticion.current?.abort(); }, []);
  // RNF-016: al sustituir la confirmación, conserva el foco dentro del diálogo.
  useEffect(() => { if (clave) botonCopiar.current?.focus(); }, [clave]);

  function terminar() { setClave(""); setAviso(""); cerrar(); }

  async function confirmar() {
    if (ocupado.current || clave) return;
    ocupado.current = true;
    setEnviando(true); setError("");
    const controlador = new AbortController();
    peticion.current = controlador;
    try {
      const resultado = await api<ClaveTemporalOut>(`/usuarios/${usuario.id_usuario}/restablecer-acceso`, { metodo: "POST", signal: controlador.signal });
      if (controlador.signal.aborted) return;
      if (!resultado) throw new Error("El servidor no devolvió la contraseña temporal.");
      setClave(resultado.clave_temporal);
    } catch (fallo: unknown) {
      if (!controlador.signal.aborted) setError(mensajeError(fallo));
    } finally { ocupado.current = false; if (!controlador.signal.aborted) setEnviando(false); }
  }

  async function copiar() {
    setAviso(""); setError("");
    try {
      if (!navigator.clipboard?.writeText) throw new Error("No se pudo copiar. Selecciona la contraseña temporal y cópiala manualmente.");
      await navigator.clipboard.writeText(clave);
      setAviso("Contraseña temporal copiada.");
    } catch { setError("No se pudo copiar. Selecciona la contraseña temporal y cópiala manualmente."); }
  }

  return <Dialogo titulo="Restablecer acceso" cerrar={terminar}>
    {clave ? <>
      <p>Contraseña temporal de <strong>{usuario.nombre_completo}</strong></p>
      <output aria-label="Contraseña temporal" className="usuarios-clave-temporal">{clave}</output>
      <Mensaje tipo="info">Esta contraseña se muestra una sola vez. Al cerrar no se volverá a ver. Entrégala por un canal seguro y pide al usuario cambiarla en «Mi cuenta».</Mensaje>
      <div className="mt-4"><Mensaje tipo="exito">{aviso}</Mensaje><Mensaje>{error}</Mensaje></div>
      <div className="usuarios-acciones"><button ref={botonCopiar} type="button" className="boton-secundario" onClick={copiar}>Copiar contraseña</button><button type="button" className="boton" onClick={terminar}>Cerrar y descartar</button></div>
    </> : <>
      <p>¿Deseas restablecer el acceso de <strong>{usuario.nombre_completo}</strong>?</p>
      <p className="usuarios-ayuda">Se generará una contraseña temporal y se invalidarán sus sesiones actuales. La contraseña solo se verá en este diálogo.</p>
      <div className="mt-4"><Mensaje>{error}</Mensaje></div>
      <div className="usuarios-acciones"><button type="button" className="boton-secundario" onClick={terminar}>Cancelar</button><button type="button" className="boton" onClick={confirmar} disabled={enviando}>{enviando ? "Restableciendo…" : "Generar contraseña temporal"}</button></div>
    </>}
  </Dialogo>;
}
