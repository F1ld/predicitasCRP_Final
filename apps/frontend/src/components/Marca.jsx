import logo from "../assets/logo.svg";

export default function Marca({ className = "" }) {
  return <img className={`marca ${className}`} src={logo} alt="PrediCitas CRP" width="850" height="200" />;
}
