from sqlalchemy.orm import Session

from app.core.errores import Validacion
from app.modules.auditoria.public import registrar_evento
from app.modules.auth.public import Principal
from app.modules.reportes.consultas import generar_rep02, generar_rep03, generar_rep02_csv, generar_rep03_csv
from app.modules.reportes.schemas import Rep02Out


def preparar_rep02(db: Session, *, usuario: Principal, ip: str, formato="json", desde=None,
                   hasta=None, canal_contacto=None, nivel_riesgo=None, especialidad=None) -> tuple[Rep02Out, str]:
    """Caso de uso de consulta/exportación: la auditoría cierra aquí, no en HTTP."""
    formato_norm = (formato or "json").lower()
    if formato_norm not in ("json", "csv", "xlsx"):
        raise Validacion("Formato no disponible", codigo="FORMATO_NO_DISPONIBLE", campos={"formato": "Formato no disponible"})
    if canal_contacto and canal_contacto.upper() not in ("WHATSAPP", "SMS", "LLAMADA_TELEFONICA"):
        raise Validacion("Canal de contacto no admitido", campos={"canal_contacto": "Canal no admitido"})
    reporte = generar_rep02(db, desde=desde, hasta=hasta, canal_contacto=canal_contacto,
                            nivel_riesgo=nivel_riesgo, especialidad=especialidad)
    if formato_norm in ("csv", "xlsx"):
        filtros = {}
        if desde:
            filtros["desde"] = desde
        if hasta:
            filtros["hasta"] = hasta
        if especialidad:
            filtros["especialidad"] = especialidad.upper()
        if canal_contacto:
            filtros["canal_contacto"] = canal_contacto.upper()
        if nivel_riesgo:
            filtros["nivel_riesgo"] = nivel_riesgo.upper()
        registrar_evento(db, modulo="REPORTES", accion="EXPORT", entidad_afectada="rep-02",
            direccion_ip=ip, id_usuario=usuario.id_usuario,
            datos_after={"formato": formato_norm, "filtros": filtros})
        db.commit()
    return reporte, formato_norm
