from functools import wraps
from decimal import Decimal
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errores import Conflicto, NoEncontrado, MotorIANoDisponible, Validacion
from app.modules.auditoria.public import registrar_evento
from app.modules.auth.public import Principal as Usuario
from app.modules.ia.consultas import CitaInferencia, cita_para_inferencia, bloquear_para_inferencia
from app.modules.ia import repository
from app.modules.ia.metadata_motor import FEATURES_MODELO
from app.modules.ia.motor_integrado import MotorIntegrado
from app.modules.ia.puerto import FeaturesMotor, MotorPredictivo, ResultadoMotor
from app.modules.ia.schemas import (
    DatasetResumenOut,
    MetricasModeloOut,
    PrediccionIAOut,
    ResultadoPrediccionLoteOut,
)

ESTADOS_ELEGIBLES_PREDICCION = {"RECIBIDA", "CONFIRMADA", "REPROGRAMADA"}
LIMITE_LOTE_PUBLICO = 500


def _rollback_en_error(func):
    @wraps(func)
    def wrapped(db, *args, **kwargs):
        if db.new or db.dirty or db.deleted:
            raise Conflicto("Inferencia requiere una sesión sin cambios pendientes")
        try:
            return func(db, *args, **kwargs)
        except Exception:
            db.rollback()
            raise
    return wrapped


def _cerrar_lectura(db):
    # Casos de uso top-level: jamás confirmar escrituras ajenas para hacer HTTP.
    if db.new or db.dirty or db.deleted:
        raise Conflicto("Inferencia requiere una sesión sin cambios pendientes")
    db.rollback()


def _validar_resultado(result, features, version):
    try:
        result = ResultadoMotor.model_validate(result)
    except ValidationError:
        raise MotorIANoDisponible("Respuesta incompatible del motor IA") from None
    if result.version_modelo != version:
        raise Conflicto("La versión del motor cambió", codigo="VERSION_MODELO_INCOMPATIBLE")
    p = result.probabilidad_no_show
    level = "ALTO" if p > Decimal("0.45") else "MEDIO" if p >= Decimal("0.3") else "BAJO"
    snapshot = features.snapshot()
    if (result.features_snapshot != snapshot
            or any(type(result.features_snapshot[k]) is not type(v) for k, v in snapshot.items())
            or result.nivel_riesgo != level
            or result.umbral_aplicado != Decimal("0.450")
            or p != p.quantize(Decimal("0.001"))):
        raise MotorIANoDisponible("Respuesta incompatible del motor IA")
    return result.model_dump()


def _revalidar(db, snapshots):
    current = bloquear_para_inferencia(db, [c.id_cita for c in snapshots])
    if any(current.get(c.id_cita) != c for c in snapshots):
        raise Conflicto("La cita cambió durante la inferencia; vuelva a solicitarla")


def listar_predicciones_cita(db: Session, id_cita: int) -> list[PrediccionIAOut]:
    return [PrediccionIAOut.model_validate(p) for p in repository.listar_por_cita(db, id_cita)]


def _cita_a_dict_features(cita: CitaInferencia) -> dict:
    return {
        "especialidad": cita.especialidad,
        "tipo_paciente": cita.tipo_paciente,
        "canal_origen": cita.canal_origen,
        "franja_horaria": cita.franja_horaria,
        "dia_semana": cita.dia_semana,
        "antelacion_dias": cita.antelacion_dias,
        "inasistencias_previas": cita.inasistencias_previas,
        "asistencias_previas": cita.asistencias_previas,
        "reprogramaciones_prev": cita.reprogramaciones_prev,
    }


@_rollback_en_error
def predecir_cita(
    db: Session,
    id_cita: int,
    *,
    usuario: Usuario,
    ip: str,
    motor: MotorPredictivo | None = None,
) -> PrediccionIAOut:
    cita = cita_para_inferencia(db, id_cita)
    if cita is None:
        raise NoEncontrado(f"No existe la cita {id_cita}")
    if cita.estado_actual not in ESTADOS_ELEGIBLES_PREDICCION:
        raise Conflicto(
            f"La cita {id_cita} se encuentra en estado final '{cita.estado_actual}' y no admite inferencia operativa"
        )

    features = FeaturesMotor(**_cita_a_dict_features(cita))
    _cerrar_lectura(db)
    motor = motor or MotorIntegrado()
    version = motor.version()
    resultado_ia = _validar_resultado(motor.predecir(features, version=version), features, version)
    _revalidar(db, [cita])
    prediccion, antes = repository.guardar_o_actualizar_prediccion(
        db,
        id_cita=cita.id_cita,
        version_modelo=resultado_ia["version_modelo"],
        probabilidad_no_show=resultado_ia["probabilidad_no_show"],
        nivel_riesgo=resultado_ia["nivel_riesgo"],
        umbral_aplicado=resultado_ia["umbral_aplicado"],
        features_snapshot=resultado_ia["features_snapshot"],
        explicabilidad_resumen=resultado_ia["explicabilidad_resumen"],
    )

    registrar_evento(
        db,
        modulo="IA",
        accion="PREDICT",
        entidad_afectada="predicciones_ia",
        direccion_ip=ip,
        id_usuario=usuario.id_usuario,
        id_entidad=prediccion.id_prediccion,
        datos_before=antes,
        datos_after={
            "id_cita": cita.id_cita,
            "version_modelo": prediccion.version_modelo,
            "probabilidad_no_show": float(prediccion.probabilidad_no_show),
            "nivel_riesgo": prediccion.nivel_riesgo,
            "umbral_aplicado": float(prediccion.umbral_aplicado),
            "explicabilidad_resumen": prediccion.explicabilidad_resumen,
        },
    )
    db.commit()
    db.refresh(prediccion)
    return PrediccionIAOut.model_validate(prediccion)


@_rollback_en_error
def predecir_lote(
    db: Session,
    *,
    forzar: bool = False,
    usuario: Usuario,
    ip: str,
    motor: MotorPredictivo | None = None,
) -> ResultadoPrediccionLoteOut:
    _cerrar_lectura(db)
    motor = motor or MotorIntegrado()
    version_modelo = motor.version()
    citas = repository.citas_operativas_sin_prediccion(
        db, version_modelo, forzar=forzar, limite=LIMITE_LOTE_PUBLICO + 1)
    if len(citas) > LIMITE_LOTE_PUBLICO:
        raise Validacion(
            f"El lote supera el máximo de {LIMITE_LOTE_PUBLICO} citas elegibles",
            codigo="LOTE_IA_DEMASIADO_GRANDE",
        )
    features = [FeaturesMotor(**_cita_a_dict_features(cita)) for cita in citas]
    _cerrar_lectura(db)
    results = motor.predecir_lote(features, version=version_modelo)
    if len(results) != len(citas):
        raise MotorIANoDisponible("Lote incompleto del motor IA")
    # Validar TODO antes del primer flush. Nunca publicar un lote parcial.
    resultados = [_validar_resultado(result, f, version_modelo) for result, f in zip(results, features)]
    _revalidar(db, citas)

    predicciones_out: list[PrediccionIAOut] = []
    conteo = {"ALTO": 0, "MEDIO": 0, "BAJO": 0}

    for cita, resultado_ia in zip(citas, resultados):
        pred, _ = repository.guardar_o_actualizar_prediccion(
            db,
            id_cita=cita.id_cita,
            version_modelo=version_modelo,
            probabilidad_no_show=resultado_ia["probabilidad_no_show"],
            nivel_riesgo=resultado_ia["nivel_riesgo"],
            umbral_aplicado=resultado_ia["umbral_aplicado"],
            features_snapshot=resultado_ia["features_snapshot"],
            explicabilidad_resumen=resultado_ia["explicabilidad_resumen"],
        )
        conteo[pred.nivel_riesgo] = conteo.get(pred.nivel_riesgo, 0) + 1
        predicciones_out.append(PrediccionIAOut.model_validate(pred))

    registrar_evento(
        db,
        modulo="IA",
        accion="PREDICT",
        entidad_afectada="predicciones_ia",
        direccion_ip=ip,
        id_usuario=usuario.id_usuario,
        datos_after={
            "operacion": "PREDICT_LOTE",
            "version_modelo": version_modelo,
            "evaluadas": len(predicciones_out),
            "riesgo_alto": conteo["ALTO"],
            "riesgo_medio": conteo["MEDIO"],
            "riesgo_bajo": conteo["BAJO"],
        },
    )
    db.commit()
    return ResultadoPrediccionLoteOut(
        version_modelo=version_modelo,
        evaluadas=len(predicciones_out),
        riesgo_alto=conteo["ALTO"],
        riesgo_medio=conteo["MEDIO"],
        riesgo_bajo=conteo["BAJO"],
        predicciones=predicciones_out,
    )


def obtener_metricas_modelo(*, motor: MotorPredictivo | None = None, db: Session | None = None) -> MetricasModeloOut:
    if db is not None:
        _cerrar_lectura(db)
    return (motor or MotorIntegrado()).metricas()


def obtener_dataset_resumen(db: Session, *, motor: MotorPredictivo | None = None) -> DatasetResumenOut:
    conteos_bd = repository.conteos_dataset_bd(db)
    _cerrar_lectura(db)
    ds = (motor or MotorIntegrado()).dataset().model_dump()

    total_hist = ds["total_historicas"]
    no_show_est = round(total_hist * ds["tasa_no_show_global"])
    atendidas_est = total_hist - no_show_est

    return DatasetResumenOut(
        version_dataset=ds["version_dataset"],
        semilla=ds["semilla"],
        total_historicas=total_hist,
        atendidas_historicas=conteos_bd["atendidas_bd"] or atendidas_est,
        no_show_historicas=conteos_bd["no_show_bd"] or no_show_est,
        proximas_operativas_bd=conteos_bd["proximas_bd"],
        train_size=ds["train_size"],
        val_size=ds["val_size"],
        test_size=ds["test_size"],
        tasa_no_show_global=ds["tasa_no_show_global"],
        tasa_no_show_train=ds["tasa_no_show_train"],
        tasa_no_show_val=ds["tasa_no_show_val"],
        tasa_no_show_test=ds["tasa_no_show_test"],
        features_autorizadas=list(FEATURES_MODELO),
        control_leakage=ds["control_leakage"],
        rotulo_etico=ds["rotulo_etico"],
    )

