"""Aplicación FastAPI autónoma del servicio de IA (Fase 5).

No depende de base de datos PostgreSQL ni de módulos de `apps/backend`.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import threading
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth import verificar_api_key_interna
from app.config import COMPUTE_TIMEOUT_SECONDS, require_api_key
from app.body_limit import MaxBodySizeMiddleware
from app.metadata import DatasetManifest, MetricasModelo
from app.execution import IsolatedExecutor, CapacityUnavailable, ComputationExpired, WorkerFailed
from app.core.model_registry import registry
from app.schemas import (
    BatchItemResponse,
    BatchRequest,
    BatchResponse,
    ErrorDetail,
    ErrorResponse,
    LiveStatus,
    ModelMetadata,
    PredictRequest,
    PredictResponse,
    ReadyStatus,
)

logger = logging.getLogger("predicitas.ia.app")
_executor: IsolatedExecutor | None = None
_executor_lock = threading.Lock()


def get_executor() -> IsolatedExecutor:
    """Crea el ejecutor de forma diferida y segura entre hilos."""
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = IsolatedExecutor(timeout=COMPUTE_TIMEOUT_SECONDS)
        return _executor


def close_executor() -> None:
    global _executor
    with _executor_lock:
        current, _executor = _executor, None
    if current is not None:
        current.close()


def ejecutar_aislado(version: str, features: list) -> list[dict]:
    try:
        result = get_executor().run({
            "action": "predict",
            "version_modelo": version,
            "features": [f.model_dump(mode="json") for f in features],
        })
    except (CapacityUnavailable, ComputationExpired, WorkerFailed) as exc:
        # Contrato 503 existente; el motivo distingue saturación, plazo o worker.
        reason = {
            CapacityUnavailable: "CAPACIDAD_OCUPADA",
            ComputationExpired: "PLAZO_AGOTADO",
            WorkerFailed: "WORKER_FALLIDO",
        }[type(exc)]
        raise HTTPException(status_code=503, detail=ErrorDetail(codigo="MODELO_NO_DISPONIBLE",
            mensaje="Inferencia temporalmente no disponible", campos={"motivo": reason}).model_dump()) from None
    items = result.get("items") if isinstance(result, dict) else None
    if not isinstance(items, list) or len(items) != len(features):
        raise HTTPException(status_code=503, detail=ErrorDetail(codigo="MODELO_NO_DISPONIBLE",
            mensaje="Respuesta del proceso de inferencia incompatible").model_dump())
    return items


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cargar el modelo en memoria durante el inicio del servicio
    require_api_key()
    ready = registry.load_model()
    if ready:
        try:
            get_executor().warm()
        except Exception as exc:
            close_executor()
            logger.error("Aislamiento de inferencia no disponible (%s)", type(exc).__name__)
            raise RuntimeError("Aislamiento de inferencia no disponible") from None
    try:
        yield
    finally:
        close_executor()


app = FastAPI(
    title="PrediCitas IA — Servicio Autónomo",
    version="1.0.0",
    description="Servicio interno de inferencia y explicabilidad (Fase 5)",
    lifespan=lifespan,
    responses={code: {"model": ErrorResponse} for code in (401, 409, 413, 422, 503, 500)},
)


# ==============================================================================
# Middleware de límite de tamaño de payload (256 KiB)
# ==============================================================================


app.add_middleware(MaxBodySizeMiddleware)


# ==============================================================================
# Manejadores de excepciones estandarizados (error.v1.schema.json)
# ==============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "codigo" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    # Mapeo por defecto según código de estado
    codigo_map = {
        status.HTTP_401_UNAUTHORIZED: "NO_AUTENTICADO",
        status.HTTP_409_CONFLICT: "VERSION_MODELO_INCOMPATIBLE",
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "SOLICITUD_DEMASIADO_GRANDE",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDACION",
        status.HTTP_503_SERVICE_UNAVAILABLE: "MODELO_NO_DISPONIBLE",
    }
    codigo = codigo_map.get(exc.status_code, "ERROR_INTERNO")
    err = ErrorResponse(
        error=ErrorDetail(
            codigo=codigo,  # type: ignore[arg-type]
            mensaje=str(exc.detail) if exc.detail else "Error en la petición",
            campos={},
        )
    )
    return JSONResponse(status_code=exc.status_code, content=err.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    campos = {}
    for err in exc.errors():
        loc = ".".join(str(item) for item in err["loc"] if item != "body")
        campos[loc or "body"] = err["msg"]

    err = ErrorResponse(
        error=ErrorDetail(
            codigo="VALIDACION",
            mensaje="Parámetros de entrada o formato de datos inválido",
            campos=campos,
        )
    )
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=err.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Error no controlado en runtime de IA (%s)", type(exc).__name__)
    err = ErrorResponse(
        error=ErrorDetail(
            codigo="ERROR_INTERNO",
            mensaje="Error interno en el servicio de inferencia",
            campos={},
        )
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=err.model_dump())


# ==============================================================================
# Endpoints de Health (sin autenticación requerida)
# ==============================================================================


@app.get("/health/live", response_model=LiveStatus, tags=["Health"])
def health_live() -> LiveStatus:
    """Indica que el proceso del servidor HTTP está activo."""
    return LiveStatus(estado="vivo")


@app.get("/health/ready", response_model=ReadyStatus, tags=["Health"])
def health_ready() -> ReadyStatus:
    """Indica si el modelo predictivo fue cargado correctamente y está listo para inferencia."""
    if not registry.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetail(
                codigo="MODELO_NO_DISPONIBLE",
                mensaje="El artefacto del modelo LightGBM no está cargado o no se encuentra disponible",
            ).model_dump(),
        )
    return ReadyStatus(estado="listo")


# ==============================================================================
# Endpoints v1 (requieren X-IA-API-Key)
# ==============================================================================


@app.get(
    "/v1/model",
    response_model=ModelMetadata,
    dependencies=[Depends(verificar_api_key_interna)],
    tags=["Metadata"],
)
def get_model_metadata() -> ModelMetadata:
    """Retorna los metadatos y configuración del modelo actualmente activo."""
    if not registry.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetail(
                codigo="MODELO_NO_DISPONIBLE",
                mensaje="El modelo predictivo no está listo",
            ).model_dump(),
        )
    return registry.get_metadata()


@app.get(
    "/v1/metrics",
    response_model=MetricasModelo,
    dependencies=[Depends(verificar_api_key_interna)],
    tags=["Metadata"],
)
def get_model_metrics() -> dict[str, Any]:
    """Retorna las métricas de evaluación del modelo activo (compatible con MetricasModeloOut)."""
    if not registry.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetail(
                codigo="MODELO_NO_DISPONIBLE",
                mensaje="El modelo predictivo no está listo",
            ).model_dump(),
        )
    return registry.get_metrics_payload()


@app.get(
    "/v1/dataset",
    response_model=DatasetManifest,
    dependencies=[Depends(verificar_api_key_interna)],
    tags=["Metadata"],
)
def get_dataset_metadata() -> dict[str, Any]:
    """Retorna el manifiesto de datos de entrenamiento/importación del modelo activo."""
    if not registry.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetail(
                codigo="MODELO_NO_DISPONIBLE",
                mensaje="El modelo predictivo no está listo",
            ).model_dump(),
        )
    return registry.get_dataset_manifest()


@app.post(
    "/v1/predict",
    response_model=PredictResponse,
    dependencies=[Depends(verificar_api_key_interna)],
    tags=["Inference"],
)
def predict_individual(solicitud: PredictRequest) -> PredictResponse:
    """Ejecuta inferencia individual sobre features pre-cita."""
    if not registry.is_ready or registry.pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetail(
                codigo="MODELO_NO_DISPONIBLE",
                mensaje="El modelo predictivo no está listo para atender inferencias",
            ).model_dump(),
        )

    if not registry.version_matches(solicitud.version_modelo):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorDetail(
                codigo="VERSION_MODELO_INCOMPATIBLE",
                mensaje=(
                    f"Versión solicitada '{solicitud.version_modelo}' no coincide "
                    f"con la versión activa '{registry.version_modelo}'"
                ),
                campos={"version_solicitada": solicitud.version_modelo, "version_activa": str(registry.version_modelo)},
            ).model_dump(),
        )

    result = ejecutar_aislado(solicitud.version_modelo, [solicitud.features])[0]

    return PredictResponse(
        version_contrato="1.0",
        id_solicitud=solicitud.id_solicitud,
        version_modelo=str(registry.version_modelo),
        version_features=solicitud.version_features,
        **result,
    )


@app.post(
    "/v1/predict-batch",
    response_model=BatchResponse,
    dependencies=[Depends(verificar_api_key_interna)],
    tags=["Inference"],
)
def predict_batch(solicitud: BatchRequest) -> BatchResponse:
    """Ejecuta inferencia por lote (1..100 elementos) de forma atómica."""
    if not registry.is_ready or registry.pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetail(
                codigo="MODELO_NO_DISPONIBLE",
                mensaje="El modelo predictivo no está listo para atender inferencias",
            ).model_dump(),
        )

    if not registry.version_matches(solicitud.version_modelo):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorDetail(
                codigo="VERSION_MODELO_INCOMPATIBLE",
                mensaje=(
                    f"Versión solicitada '{solicitud.version_modelo}' no coincide "
                    f"con la versión activa '{registry.version_modelo}'"
                ),
                campos={"version_solicitada": solicitud.version_modelo, "version_activa": str(registry.version_modelo)},
            ).model_dump(),
        )

    resultados: list[BatchItemResponse] = []
    computed = ejecutar_aislado(solicitud.version_modelo, [item.features for item in solicitud.items])
    for item, result in zip(solicitud.items, computed):
        pred = PredictResponse(
            version_contrato="1.0",
            id_solicitud=solicitud.id_solicitud,
            version_modelo=str(registry.version_modelo),
            version_features=solicitud.version_features,
            **result,
        )
        resultados.append(BatchItemResponse(id_item=item.id_item, resultado=pred))

    return BatchResponse(
        version_contrato="1.0",
        id_solicitud=solicitud.id_solicitud,
        version_modelo=str(registry.version_modelo),
        items=resultados,
    )
