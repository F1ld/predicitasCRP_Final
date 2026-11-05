import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../../nucleo/api/cliente";
import { useConsulta } from "../../nucleo/api/useConsulta";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import { etiqueta } from "../../nucleo/formato/formato";
import Dialogo from "./Dialogo";
import { ROLES, type UsuarioOut } from "./tipos";
import { camposError, errorCorreo, errorNombre, mensajeError, politicaClave } from "./validacion";

interface Propiedades {
  usuario?: UsuarioOut;
  cerrar: () => void;
  completado: (mensaje: string) => void;
}

// RF-005: editar consulta el detalle vigente M01-E08 antes de enviar el PATCH.
function CargarUsuario({ usuario, cerrar, completado }: Propiedades & { usuario: UsuarioOut }) {
  const { datos, cargando, error, reintentar } = useConsulta<UsuarioOut>(`/usuarios/${usuario.id_usuario}`);
  if (cargando) return <Cargando texto="Cargando usuario…" />;
  if (error || !datos) return <div className="usuarios-formulario"><Mensaje>{error || "El servidor no devolvió los datos del usuario."}</Mensaje><button className="boton-secundario" onClick={reintentar}>Reintentar</button></div>;
  return <CamposUsuario usuario={datos} cerrar={cerrar} completado={completado} />;
}

export default function FormularioUsuario(propiedades: Propiedades) {
  return <Dialogo titulo={propiedades.usuario ? "Editar usuario" : "Crear usuario"} cerrar={propiedades.cerrar}>
    {propiedades.usuario ? <CargarUsuario {...propiedades} usuario={propiedades.usuario} /> : <CamposUsuario {...propiedades} />}
  </Dialogo>;
}

// RF-004, RF-005, RF-007, RNF-016: campos del contrato, validación y errores 422 asociados.
function CamposUsuario({ usuario, cerrar, completado }: Propiedades) {
  const [nombre, setNombre] = useState(usuario?.nombre_completo ?? "");
  const [correo, setCorreo] = useState(usuario?.correo_institucional ?? "");
  const [rol, setRol] = useState(usuario?.rol ?? "RECEPCION");
  const [clave, setClave] = useState("");
  const [tocados, setTocados] = useState<Record<string, boolean>>({});
  const [campos, setCampos] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const ocupado = useRef(false);
  const peticion = useRef<AbortController | null>(null);
  useEffect(() => () => { peticion.current?.abort(); }, []);
  const politica = politicaClave(clave);
  const errores: Record<string, string> = {
    nombre_completo: errorNombre(nombre),
    correo_institucional: usuario ? "" : errorCorreo(correo),
    clave_inicial: usuario || Object.values(politica).every(Boolean) ? "" : "La contraseña debe tener entre 8 y 128 caracteres, al menos una letra y un número.",
  };

  function cambiar(campo: string, asignar: () => void) {
    asignar();
    setTocados((anteriores) => ({ ...anteriores, [campo]: true }));
    setCampos((anteriores) => ({ ...anteriores, [campo]: "" }));
  }

  const motivo = (campo: string): string => campos[campo] || (tocados[campo] ? errores[campo] ?? "" : "");
  const atributos = (campo: string) => ({
    "aria-invalid": Boolean(motivo(campo)),
    "aria-describedby": motivo(campo) ? `usuario-${campo}-error` : undefined,
  });
  const detalle = (campo: string) => motivo(campo) ? <p id={`usuario-${campo}-error`} className="usuarios-error-campo">{motivo(campo)}</p> : null;

  async function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (ocupado.current) return;
    setTocados({ nombre_completo: true, correo_institucional: true, clave_inicial: true });
    const invalido = Object.keys(errores).find((campo) => errores[campo]);
    if (invalido) { document.getElementById(`usuario-${invalido}`)?.focus(); return; }
    ocupado.current = true;
    setEnviando(true);
    setError("");
    setCampos({});
    const controlador = new AbortController();
    peticion.current = controlador;
    try {
      const datos = await api<UsuarioOut>(usuario ? `/usuarios/${usuario.id_usuario}` : "/usuarios", {
        metodo: usuario ? "PATCH" : "POST",
        json: usuario ? { nombre_completo: nombre, rol } : { nombre_completo: nombre, correo_institucional: correo.toLowerCase(), rol, clave_inicial: clave },
        signal: controlador.signal,
      });
      if (controlador.signal.aborted) return;
      if (!datos) throw new Error("El servidor no confirmó los datos del usuario.");
      setClave("");
      completado(usuario ? "Usuario actualizado correctamente." : "Usuario creado correctamente.");
    } catch (fallo: unknown) {
      if (!controlador.signal.aborted) { setCampos(camposError(fallo)); setError(mensajeError(fallo)); }
    } finally {
      ocupado.current = false;
      if (!controlador.signal.aborted) setEnviando(false);
    }
  }

  return <form onSubmit={guardar} noValidate className="usuarios-formulario">
    <Mensaje>{error}</Mensaje>
    <fieldset disabled={enviando} className="usuarios-formulario">
      <div><label htmlFor="usuario-nombre_completo">Nombre completo</label><input id="usuario-nombre_completo" name="nombre_completo" value={nombre} maxLength={120} required autoComplete="off" {...atributos("nombre_completo")} onChange={(e) => cambiar("nombre_completo", () => setNombre(e.target.value))} />{detalle("nombre_completo")}</div>
      <div><label htmlFor="usuario-correo_institucional">Correo institucional</label><input id="usuario-correo_institucional" name="correo_institucional" type="email" value={correo} maxLength={100} required readOnly={Boolean(usuario)} autoComplete="off" {...atributos("correo_institucional")} onChange={(e) => cambiar("correo_institucional", () => setCorreo(e.target.value))} />{usuario && <p className="usuarios-ayuda">El correo institucional se conserva al editar.</p>}{detalle("correo_institucional")}</div>
      <div><label htmlFor="usuario-rol">Rol</label><select id="usuario-rol" name="rol" value={rol} {...atributos("rol")} onChange={(e) => { const valor = ROLES.find((opcion) => opcion === e.target.value); if (valor) cambiar("rol", () => setRol(valor)); }}>{ROLES.map((valor) => <option key={valor} value={valor}>{etiqueta(valor)}</option>)}</select>{detalle("rol")}</div>
      {!usuario && <div><label htmlFor="usuario-clave_inicial">Contraseña inicial</label><input id="usuario-clave_inicial" name="clave_inicial" type="password" autoComplete="new-password" value={clave} maxLength={128} required {...atributos("clave_inicial")} aria-describedby={`usuario-politica${motivo("clave_inicial") ? " usuario-clave_inicial-error" : ""}`} onChange={(e) => cambiar("clave_inicial", () => setClave(e.target.value))} />
        <ul id="usuario-politica" className="usuarios-politica" aria-live="polite">
          <li data-cumple={politica.longitud}>{politica.longitud ? "✓" : "○"} Entre 8 y 128 caracteres</li>
          <li data-cumple={politica.letra}>{politica.letra ? "✓" : "○"} Al menos una letra</li>
          <li data-cumple={politica.numero}>{politica.numero ? "✓" : "○"} Al menos un número</li>
        </ul>{detalle("clave_inicial")}</div>}
    </fieldset>
    <div className="usuarios-acciones"><button type="button" className="boton-secundario" onClick={cerrar}>Cancelar</button><button type="submit" className="boton" disabled={enviando}>{enviando ? "Guardando…" : usuario ? "Guardar cambios" : "Crear usuario"}</button></div>
  </form>;
}
