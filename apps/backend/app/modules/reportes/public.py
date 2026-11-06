"""Contrato de lectura de reportes; no confirma ni exporta por sí mismo."""
from app.modules.reportes.consultas import generar_rep02, generar_rep03
from app.modules.reportes.schemas import Rep02Out, Rep03Out
