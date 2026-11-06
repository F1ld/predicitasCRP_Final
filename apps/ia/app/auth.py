"""Autenticación interna del servicio de IA (Fase 5).

Valida la cabecera `X-IA-API-Key` mediante comparación en tiempo constante.
"""
from __future__ import annotations

import secrets
from fastapi import Header, HTTPException, status

from app.config import IA_API_KEY
from app.schemas import ErrorDetail


def verificar_api_key_interna(
    x_ia_api_key: str | None = Header(None, alias="X-IA-API-Key"),
) -> None:
    """Verifica que la petición contenga la clave de API autorizada.

    No registra la clave en logs ni tracebacks.
    """
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
    if not secrets.compare_digest(x_ia_api_key.encode("utf-8"), IA_API_KEY.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetail(
                codigo="NO_AUTENTICADO",
                mensaje="Clave de API interna no autorizada",
                campos={"header": "X-IA-API-Key"},
            ).model_dump(),
        )
