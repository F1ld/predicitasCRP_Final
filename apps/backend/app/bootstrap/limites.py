"""Excepciones exhaustivas de lectura/composición, no permisos de escritura."""
LECTURAS = {
    "citas/consultas.py": {"auditoria", "ia", "intervenciones", "lista_espera"},
    "intervenciones/consultas.py": {"citas", "ia"},
    "lista_espera/consultas.py": {"auditoria"},
    "reportes/consultas.py": {"citas", "ia", "intervenciones", "lista_espera"},
    "ia/consultas.py": {"citas"},
}
COMPATIBILIDAD = {("auth/models.py", "app.modules.usuarios.models")}
