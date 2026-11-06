"""Compatibilidad histórica. El reloj vigente se inyecta en app.core.reloj."""
from app.core import reloj


def ahora():
    return reloj.ahora()
