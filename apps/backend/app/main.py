"""Punto de entrada de la API PrediCitas CRP.

- Los routers principales y modulares se registran de forma explícita y estructurada.
- Todos los errores salen con la forma {"error": {"codigo", "mensaje", "campos"}} (D-017).
- Cabeceras de seguridad en cada respuesta (app/core/manejadores.py).
"""
from contextlib import asynccontextmanager
import logging
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import app.bootstrap.models  # noqa: F401  (registra todos los modelos)
from app.core import manejadores
from app.core.config import get_settings
from app.core.database import engine
from app.core.trazabilidad import CABECERA_SOLICITUD, id_solicitud
from app.modules.auth.router import router as auth_router
from app.modules.citas.router import router as citas_router
from app.modules.ia.router import router as ia_router
from app.modules.intervenciones.router import router as intervenciones_router
from app.modules.lista_espera.router import router as lista_espera_router
from app.modules.reportes.router import router as reportes_router
from app.modules.panel.router import router as panel_router
from app.modules.usuarios.router import router as usuarios_router
from app.modules.ia.dependencias import crear_motor

@asynccontextmanager
async def lifespan(app: FastAPI):
    motor = crear_motor()
    app.state.motor_ia = motor
    try:
        yield
    finally:
        motor.close()
        del app.state.motor_ia


app = FastAPI(title="PrediCitas CRP API", version="0.5.0", lifespan=lifespan)

logger = logging.getLogger("uvicorn.error.predicitas.backend")


@app.middleware("http")
async def trazar_solicitud(request: Request, call_next):
    identificador = uuid4().hex
    token = id_solicitud.set(identificador)
    inicio = monotonic()
    try:
        response = await call_next(request)
        response.headers[CABECERA_SOLICITUD] = identificador
        return response
    finally:
        id_solicitud.reset(token)
        logger.info("solicitud=%s duracion_ms=%.1f", identificador, (monotonic() - inicio) * 1000)


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().lista_cors_origenes,
    allow_credentials=False,  # el token viaja en el header Authorization, no en cookies
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[CABECERA_SOLICITUD],
)
manejadores.instalar(app)

# Montaje limpio y ordenado de routers
app.include_router(auth_router)
app.include_router(citas_router)
app.include_router(usuarios_router)
app.include_router(ia_router)
app.include_router(intervenciones_router)
app.include_router(lista_espera_router)
app.include_router(reportes_router)
app.include_router(panel_router)


@app.get("/health", tags=["sistema"])
def health():
    return {"estado": "ok"}


@app.get("/health/ready", tags=["sistema"], responses={503: {"description": "PostgreSQL no disponible"}})
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"estado": "no_disponible"})
    return {"estado": "ok"}
