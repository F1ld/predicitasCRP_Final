"""Esquemas de autenticación (contratos/modulo-01.json → tipos y validaciones)."""
from pydantic import BaseModel, ConfigDict

from app.modules.usuarios.public import Clave, UsuarioOut, validar_clave  # noqa: F401


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos


class CambioClaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clave_actual: str
    clave_nueva: Clave
