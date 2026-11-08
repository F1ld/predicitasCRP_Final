"""Selección explícita y lifecycle del puerto. Startup nunca contacta IA."""
from fastapi import Request

from app.core.config import get_settings
from app.core.errores import MotorIANoDisponible
from app.modules.ia.motor_integrado import MotorIntegrado
from app.modules.ia.puerto import MotorPredictivo


def crear_motor(settings=None) -> MotorPredictivo:
    settings = settings or get_settings()
    if settings.ia_motor == "integrado":
        return MotorIntegrado()
    from app.modules.ia.motor_http import MotorHTTP
    return MotorHTTP(settings.ia_url, settings.ia_api_key or "", connect=settings.ia_connect_segundos,
        read=settings.ia_read_segundos, write=settings.ia_write_segundos,
        pool=settings.ia_pool_segundos, presupuesto=settings.ia_presupuesto_segundos)


def obtener_motor(request: Request) -> MotorPredictivo:
    motor = getattr(request.app.state, "motor_ia", None)
    if motor is not None:
        return motor
    # Compatibilidad TestClient/consumidores sin lifespan, solo modo integrado.
    if get_settings().ia_motor == "integrado":
        return MotorIntegrado()
    raise MotorIANoDisponible("Lifecycle del cliente IA no iniciado")
