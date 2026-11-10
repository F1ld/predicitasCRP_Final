import type { RutaModulo } from "../../nucleo/layout/ranuras";
import PanelOperativo from "./PanelOperativo";
import ReporteDiario from "./ReporteDiario";
import { RUTA_REPORTE_DIARIO } from "./contratoReporteDiario";

export default [
  { ruta: "/panel", elemento: <PanelOperativo />, roles: ["RECEPCION", "ADMINISTRADOR"] },
  { ruta: RUTA_REPORTE_DIARIO, elemento: <ReporteDiario />, roles: ["RECEPCION"] },
] satisfies RutaModulo[];
