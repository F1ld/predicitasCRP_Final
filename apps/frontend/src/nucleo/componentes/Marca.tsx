import logo from "../../assets/logo.svg";
import logoLateral from "../../assets/logo-lateral.svg";
export default function Marca({ className = "", lateral = false }: { className?: string; lateral?: boolean }) {
  return <img className={`marca ${className}`} src={lateral ? logoLateral : logo} alt="PrediCitas CRP" width="1690" height="435" />;
}
