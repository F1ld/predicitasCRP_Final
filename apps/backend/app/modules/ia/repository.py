from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ia.consultas import citas_operativas_sin_prediccion, conteos_dataset_bd
from app.modules.ia.models import PrediccionIA


def obtener_por_cita_y_version(db: Session, id_cita: int, version_modelo: str) -> PrediccionIA | None:
    stmt = select(PrediccionIA).where(
        PrediccionIA.id_cita == id_cita,
        PrediccionIA.version_modelo == version_modelo,
    )
    return db.scalar(stmt)


def listar_por_cita(db: Session, id_cita: int) -> list[PrediccionIA]:
    stmt = (
        select(PrediccionIA)
        .where(PrediccionIA.id_cita == id_cita)
        .order_by(PrediccionIA.fecha_hora_inferencia.desc(), PrediccionIA.id_prediccion.desc())
    )
    return list(db.scalars(stmt))


def guardar_o_actualizar_prediccion(
    db: Session,
    *,
    id_cita: int,
    version_modelo: str,
    probabilidad_no_show: Decimal,
    nivel_riesgo: str,
    umbral_aplicado: Decimal,
    features_snapshot: dict[str, Any],
    explicabilidad_resumen: str,
) -> tuple[PrediccionIA, dict[str, Any] | None]:
    existente = obtener_por_cita_y_version(db, id_cita, version_modelo)
    if existente is not None:
        antes = {
            "probabilidad_no_show": float(existente.probabilidad_no_show),
            "nivel_riesgo": existente.nivel_riesgo,
            "explicabilidad_resumen": existente.explicabilidad_resumen,
        }
        existente.probabilidad_no_show = probabilidad_no_show
        existente.nivel_riesgo = nivel_riesgo
        existente.umbral_aplicado = umbral_aplicado
        existente.features_snapshot = features_snapshot
        existente.explicabilidad_resumen = explicabilidad_resumen
        db.flush()
        return existente, antes

    nueva = PrediccionIA(
        id_cita=id_cita,
        version_modelo=version_modelo,
        probabilidad_no_show=probabilidad_no_show,
        nivel_riesgo=nivel_riesgo,
        umbral_aplicado=umbral_aplicado,
        features_snapshot=features_snapshot,
        explicabilidad_resumen=explicabilidad_resumen,
    )
    db.add(nueva)
    db.flush()
    return nueva, None
