import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./nucleo/auth/AuthProvider";
import App from "./App";
import "./index.css";

const raiz = document.getElementById("root");
if (!raiz) throw new Error("No se encontró el contenedor de la aplicación.");
createRoot(raiz).render(<StrictMode><BrowserRouter><AuthProvider><App /></AuthProvider></BrowserRouter></StrictMode>);
