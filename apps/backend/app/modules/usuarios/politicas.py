"""Política existente de contraseña compartida por alta y cambio de clave."""
from typing import Annotated

from pydantic import AfterValidator

CLAVE_MIN, CLAVE_MAX = 8, 128


def validar_clave(clave: str) -> str:
    """8..128 caracteres, al menos una letra y un número (F-03)."""
    if not CLAVE_MIN <= len(clave) <= CLAVE_MAX:
        raise ValueError(f"Debe tener entre {CLAVE_MIN} y {CLAVE_MAX} caracteres")
    if not any(c.isalpha() for c in clave) or not any(c.isdigit() for c in clave):
        raise ValueError("Debe incluir al menos una letra y un número")
    return clave


Clave = Annotated[str, AfterValidator(validar_clave)]
