"""Tiempo técnico compartido; sin dependencias de módulos de negocio."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LIMA = ZoneInfo("America/Lima")


def ahora() -> datetime:
    """UTC a milisegundos: conserva la precisión de iat/logout/revocación."""
    momento = datetime.now(timezone.utc)
    return momento.replace(microsecond=momento.microsecond // 1000 * 1000)


def ahora_lima() -> datetime:
    return datetime.now(LIMA)


def reloj() -> datetime:
    """Dependencia FastAPI compartida; sustituible mediante dependency_overrides."""
    return ahora_lima()


def fecha_lima(momento: datetime):
    return momento.astimezone(LIMA).date()
