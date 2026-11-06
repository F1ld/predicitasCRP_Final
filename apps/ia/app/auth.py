"""Autenticación interna del servicio de IA (Fase 5).

Valida la cabecera `X-IA-API-Key` mediante comparación en tiempo constante.
"""
from __future__ import annotations

import secrets
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import require_api_key
from app.schemas import ErrorDetail


api_key_header = APIKeyHeader(name="X-IA-API-Key", scheme_name="IAApiKey", auto_error=False)


def verificar_api_key_interna(
    x_ia_api_key: str | None = Security(api_key_header),
) -> None:
    """Verifica que la petición contenga la clave de API autorizada.

    No registra la clave en logs ni tracebacks.
    """
    expected = require_api_key()
    if not x_ia_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetail(
                codigo="NO_AUTENTICADO",
                mensaje="Cabecera X-IA-API-Key ausente o vacía",
                campos={"header": "X-IA-API-Key"},
            ).model_dump(),
        )

    # Comparación segura en tiempo constante para mitigar ataques de temporización
    if not secrets.compare_digest(x_ia_api_key.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetail(
                codigo="NO_AUTENTICADO",
                mensaje="Clave de API interna no autorizada",
                campos={"header": "X-IA-API-Key"},
            ).model_dump(),
        )
