"""Datos de identidad públicos en memoria; nunca contienen secretos ni estado ORM."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Identidad:
    id_usuario: int
    nombre_completo: str
    correo_institucional: str
    rol: str
    activo: bool
    creado_en: datetime
    actualizado_en: datetime | None
