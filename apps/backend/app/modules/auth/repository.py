"""Puente histórico de consultas; las identidades son DTO sin hashes ni ORM."""
from app.modules.auditoria.public import fallos_recientes, hay_logout_desde  # noqa: F401
from app.modules.usuarios.public import por_correo, por_id  # noqa: F401
