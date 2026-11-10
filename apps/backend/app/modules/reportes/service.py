from datetime import date, datetime, time, timedelta

from fastapi import Response
from sqlalchemy.orm import Session

from app.core.errores import Validacion
from app.core.exportacion import responder
from app.core.reloj import LIMA
from app.modules.auditoria.public import registrar_evento
from app.modules.auth.public import Principal
from app.modules.reportes.consultas import (
    consultar_rep01, generar_rep02, generar_rep02_csv, generar_rep03,
    generar_rep03_csv, proyectar_exportacion_rep03,
)
from app.modules.reportes.schemas import (
    EspecialidadRep01, FranjaRep01, NivelRiesgoRep01, Rep01Fila, Rep01Filtros,
    Rep01Grupo, Rep01Out, Rep02Out, Rep03Out,
)


def obtener_rep01(
    db: Session, *, fecha: str, especialidad: EspecialidadRep01 | None,
    nivel_riesgo: NivelRiesgoRep01 | None,
) -> Rep01Out:
    try:
        dia = date.fromisoformat(fecha)
        siguiente = dia + timedelta(days=1)
    except (ValueError, OverflowError) as exc:
        raise Validacion("Fecha inválida", campos={"fecha": "Indique una fecha válida"}) from exc

    registros = consultar_rep01(
        db, inicio=datetime.combine(dia, time.min, tzinfo=LIMA),
        fin=datetime.combine(siguiente, time.min, tzinfo=LIMA),
        especialidad=especialidad, nivel_riesgo=nivel_riesgo,
    )
    por_grupo: dict[tuple[EspecialidadRep01, FranjaRep01], list[Rep01Fila]] = {}
    for registro in registros:
        datos = dict(registro)
        hora = datos.pop("fecha_hora_cita").astimezone(LIMA).time()
        fila = Rep01Fila(hora=hora, **datos)
        franja: FranjaRep01 = "MANANA" if hora.hour < 13 else "TARDE"
        por_grupo.setdefault((fila.especialidad, franja), []).append(fila)

    return Rep01Out(
        fecha=dia,
        filtros=Rep01Filtros(especialidad=especialidad, nivel_riesgo=nivel_riesgo),
        total=len(registros),
        grupos=[
            Rep01Grupo(especialidad=esp, franja_horaria=franja, subtotal=len(filas), filas=filas)
            for (esp, franja), filas in por_grupo.items()
        ],
    )


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


def preparar_rep03(
    db: Session, *, usuario: Principal, ip: str, formato: str,
    desde: str | None, hasta: str | None, especialidad: str | None, id_operador: int | None,
) -> Rep03Out | Response:
    reporte = generar_rep03(
        db, desde=desde, hasta=hasta, especialidad=especialidad, id_operador=id_operador,
    )
    if formato == "json":
        return reporte
    if formato == "xlsx":
        columnas, filas = proyectar_exportacion_rep03(reporte)
        archivo = responder(filas, columnas, formato, "rep-03")
    else:
        archivo = Response(
            content=generar_rep03_csv(reporte).encode("utf-8-sig"),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="rep-03.csv"'},
        )
    filtros = {
        "desde": desde or None,
        "hasta": hasta or None,
        "especialidad": especialidad.upper() if especialidad else None,
        "id_operador": id_operador,
    }
    registrar_evento(
        db, modulo="REPORTES", accion="EXPORT", entidad_afectada="rep-03",
        direccion_ip=ip, id_usuario=usuario.id_usuario,
        datos_after={"formato": formato, "filtros": {k: v for k, v in filtros.items() if v is not None}},
    )
    db.commit()
    return archivo
