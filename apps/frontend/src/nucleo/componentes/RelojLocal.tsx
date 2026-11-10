import { useEffect, useState } from "react";

const formatoHora = new Intl.DateTimeFormat("es-PE", {
  hour: "2-digit",
  minute: "2-digit",
});

export default function RelojLocal() {
  const [hora, setHora] = useState(() => formatoHora.format(new Date()));

  useEffect(() => {
    const intervalo = window.setInterval(() => setHora(formatoHora.format(new Date())), 1000);
    return () => window.clearInterval(intervalo);
  }, []);

  return <span>Hora local <time>{hora}</time></span>;
}
