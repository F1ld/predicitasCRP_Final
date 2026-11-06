"""Compatibilidad histórica: la tabla usuarios pertenece al módulo Usuarios.

No define otra clase ni otra tabla. Nuevos consumidores deben usar el contrato
de identidad; solo bootstrap/tests/provisión importan el modelo de Usuarios.
"""
from app.modules.usuarios.models import Usuario  # noqa: F401
