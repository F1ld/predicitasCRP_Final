"""Append componible y consultas autorizadas de sesión; sin commits propios."""
from app.modules.auditoria.consultas import fallos_recientes, hay_logout_desde
from app.modules.auditoria.service import auditar, registrar_evento

__all__ = ["auditar", "registrar_evento", "fallos_recientes", "hay_logout_desde"]
