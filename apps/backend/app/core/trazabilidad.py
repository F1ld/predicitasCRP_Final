"""Identificador opaco compartido por la peticion y sus llamadas a IA."""
from contextvars import ContextVar

CABECERA_SOLICITUD = "X-Request-ID"
id_solicitud: ContextVar[str | None] = ContextVar("id_solicitud", default=None)
