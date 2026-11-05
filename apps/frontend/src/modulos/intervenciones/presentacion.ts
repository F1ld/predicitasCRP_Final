import { etiqueta } from "../../nucleo/formato/formato";

// RF-060, RF-062: las etiquetas visibles no modifican los enums enviados a la API.
const ETIQUETAS: Record<string, string> = {
  WHATSAPP: "WhatsApp", SMS: "SMS", LLAMADA_TELEFONICA: "Llamada telefónica",
  PENDIENTE: "Pendiente", ENVIADA: "Enviada", ENTREGADA: "Entregada", RESPONDIDA: "Respondida", FALLIDA: "Fallida",
  CONFIRMA: "Confirma", SOLICITA_LIBERACION: "Solicita liberación", SOLICITA_REPROG: "Solicita reprogramación", SIN_RESPUESTA: "Sin respuesta",
  ALTO: "Alto", MEDIO: "Medio", BAJO: "Bajo",
};
export const rotulo = (valor: string | null | undefined): string => valor ? ETIQUETAS[valor] ?? etiqueta(valor) : "Sin respuesta registrada";

export function idPositivo(valor: string | null | undefined): number | null {
  if (!valor || !/^\d+$/.test(valor)) return null;
  const id = Number(valor);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}
