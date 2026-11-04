import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import Cargando from "../components/Cargando";
import Mensaje from "../components/Mensaje";
import Marca from "../components/Marca";
import Icono from "../components/Icono";

export default function Login() {
  const { usuario, cargando, mensajeSesion, iniciarSesion } = useAuth();
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  if (cargando) return <Cargando texto="Verificando sesión…" />;
  if (usuario) return <Navigate to="/citas" replace />;
  async function ingresar(evento) {
    evento.preventDefault();
    if (enviando) return;
    const campos = new FormData(evento.currentTarget);
    setEnviando(true); setError("");
    try { await iniciarSesion(campos.get("correo"), campos.get("clave")); }
    catch (fallo) { setError(fallo.status === 401 ? "Correo o contraseña incorrectos." : fallo.message); }
    finally { setEnviando(false); }
  }
  return <main className="login-pagina">
    <header className="login-cabecera"><Marca /><span>Clínica Ricardo Palma <span aria-hidden="true">/</span> San Isidro</span></header>
    <div className="login-cuerpo">
      <aside className="login-bienvenida" aria-label="Sobre PrediCitas">
        <p className="sobretitulo">CERCA DE CADA PACIENTE</p>
        <h2>Cada cita merece<br /><span>seguimiento.</span></h2>
        <p className="login-introduccion">Un espacio para acompañar el trabajo de recepción, mantener las citas al día y dar continuidad a cada atención médica.</p>
        <div className="login-principios"><p><Icono nombre="calendario" /><span>Las citas y su historial clínico-operativo, en un solo lugar.</span></p><p><Icono nombre="escudo" /><span>Acceso de acuerdo con tu perfil en el equipo de la clínica.</span></p></div>
        <p className="login-piloto">Gestión Ambulatoria · Sede San Isidro</p>
      </aside>
      <section className="login-formulario">
      <div className="login-titulo"><span className="sobretitulo">ACCESO DEL EQUIPO</span><h1>Iniciar sesión</h1>
        <p>Bienvenido. Ingresa con tu correo institucional para continuar.</p></div>
      {mensajeSesion && <Mensaje tipo="info">{mensajeSesion}</Mensaje>}
      {error && <Mensaje>{error}</Mensaje>}
      <form onSubmit={ingresar} className="login-form">
        <fieldset disabled={enviando} className="space-y-5">
          <div><label htmlFor="correo">Correo institucional</label><input id="correo" name="correo" type="email" autoComplete="username" placeholder="tu.correo@predicitas.crp" required /></div>
          <div><label htmlFor="clave">Contraseña</label><input id="clave" name="clave" type="password" autoComplete="current-password" placeholder="Ingresa tu contraseña" required /></div>
          <button className="boton w-full" type="submit">{enviando ? "Ingresando…" : "Ingresar"}<Icono nombre="flecha" /></button>
        </fieldset>
      </form>
      <details className="login-demo"><summary>Perfiles habilitados</summary><div>
        <p>recepcion@predicitas.crp</p><p>admin@predicitas.crp</p><p>tecnico.ia@predicitas.crp</p>
        <p className="mt-3">Usa las credenciales asignadas a tu cuenta institucional.</p>
      </div></details>
      <p className="login-ayuda">Si no puedes ingresar, consulta con la administración de sistemas de la sede.</p>
      </section>
    </div>
    <footer className="login-pie"><span>PrediCitas CRP</span><span>Clínica Ricardo Palma · Asistencia Predictiva de Citas Médicas</span></footer>
  </main>;
}
