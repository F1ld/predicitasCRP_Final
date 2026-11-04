import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { ApiError } from "../../nucleo/api/cliente";
import { useAuth } from "../../nucleo/auth/useAuth";
import Cargando from "../../nucleo/componentes/Cargando";
import Mensaje from "../../nucleo/componentes/Mensaje";
import Marca from "../../nucleo/componentes/Marca";
import Icono from "../../nucleo/componentes/Icono";
import { leerMotivoSesion, limpiarMotivoSesion } from "../../nucleo/sesion";

/** RF-001, RNF-016: inicio de sesión actual, accesible y con errores 401/429 del contrato M01. */
export default function Login() {
  const { usuario, cargando, mensajeSesion, iniciarSesion } = useAuth();
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [motivoSesion, setMotivoSesion] = useState(leerMotivoSesion);
  if (cargando) return <Cargando texto="Verificando sesión…" />;
  if (usuario) return <Navigate to="/citas" replace />;
  async function ingresar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (enviando) return;
    const campos = new FormData(evento.currentTarget);
    const correo = campos.get("correo");
    const clave = campos.get("clave");
    if (typeof correo !== "string" || typeof clave !== "string") return;
    limpiarMotivoSesion(); setMotivoSesion("");
    setEnviando(true);
    setError("");
    try { await iniciarSesion(correo, clave); }
    catch (fallo: unknown) {
      setError(fallo instanceof ApiError && fallo.status === 401
        ? "Correo o contraseña incorrectos."
        : fallo instanceof Error ? fallo.message : "No se pudo completar la solicitud.");
    }
    finally { setEnviando(false); }
  }
  return <main className="login-pagina">
    <header className="login-cabecera"><Marca /><span>Clínica Ricardo Palma <span aria-hidden="true">/</span> San Isidro</span></header>
    <div className="login-cuerpo">
      <aside className="login-bienvenida" aria-label="Sobre PrediCitas">
        <p className="sobretitulo">CERCA DE CADA PACIENTE</p>
        <h2>Cada cita merece<br /><span>seguimiento.</span></h2>
        <p className="login-introduccion">Un espacio para acompañar el trabajo de recepción, mantener las citas al día y dar continuidad a cada atención.</p>
        <div className="login-principios"><p><Icono nombre="calendario" /><span>Las citas y su historial, en un solo lugar.</span></p><p><Icono nombre="escudo" /><span>Acceso de acuerdo con tu rol en el equipo.</span></p></div>
        <p className="login-piloto">Piloto de seguimiento · Sede San Isidro</p>
      </aside>
      <section className="login-formulario">
        <div className="login-titulo"><span className="sobretitulo">ACCESO DEL EQUIPO</span><h1>Iniciar sesión</h1>
          <p>Bienvenido. Ingresa con tu correo institucional para continuar.</p></div>
        {(motivoSesion || mensajeSesion) && <Mensaje tipo="info">{motivoSesion || mensajeSesion}</Mensaje>}
        {error && <Mensaje>{error}</Mensaje>}
        <form onSubmit={(evento) => { void ingresar(evento); }} className="login-form">
          <fieldset disabled={enviando} className="space-y-5">
            <div><label htmlFor="correo">Correo institucional</label><input id="correo" name="correo" type="email" autoComplete="username" placeholder="tu.correo@predicitas.crp" required /></div>
            <div><label htmlFor="clave">Contraseña</label><input id="clave" name="clave" type="password" autoComplete="current-password" placeholder="Ingresa tu contraseña" required /></div>
            <button className="boton w-full" type="submit">{enviando ? "Ingresando…" : "Ingresar"}<Icono nombre="flecha" /></button>
          </fieldset>
        </form>
        <details className="login-demo"><summary>Usuarios de demostración</summary><div>
          <p>recepcion@predicitas.crp</p><p>admin@predicitas.crp</p><p>tecnico.ia@predicitas.crp</p>
          <p className="mt-3">Usa la contraseña configurada al crear los usuarios.</p>
        </div></details>
        <p className="login-ayuda">Si no puedes ingresar, consulta con el administrador del piloto.</p>
      </section>
    </div>
    <footer className="login-pie"><span>PrediCitas CRP</span><span>Entorno académico · Datos sintéticos de demostración</span></footer>
  </main>;
}
