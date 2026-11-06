"""Principal sin secretos y dependencias públicas de autenticación/autorización."""
from app.modules.auth.dependencies import requiere_roles, usuario_actual
from app.modules.usuarios.public import Identidad as Principal

__all__ = ["Principal", "requiere_roles", "usuario_actual"]
