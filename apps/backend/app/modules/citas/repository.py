"""Compatibilidad interna: las consultas canónicas viven en consultas.py."""
from app.modules.citas.consultas import (
    ids_existentes, desenlaces_de, listar, historial_de, check_in_de,
    predicciones_de, intervenciones_de, cupo_de, ultima_oferta, reasignacion_de, medicos,
)
