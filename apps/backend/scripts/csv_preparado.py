"""Lectura stdlib de fixtures/muestras explícitos; no genera, no conecta a BD."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re

COLUMNAS = (
    "id_cita_externa", "paciente_anon_id", "sede", "especialidad", "medico",
    "fecha_hora_cita", "fecha_registro_cita", "tipo_paciente", "canal_origen",
    "inasistencias_previas", "reprogramaciones_prev", "asistencias_previas", "estado_actual",
)


def leer_preparado(directorio, nombre=None, *, params=None):
    root = Path(directorio)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("Fuente absoluta existente sin enlace requerida")
    meta = root / "manifest.json"
    if meta.is_symlink() or meta.stat().st_size > 64 * 1024:
        raise ValueError("Manifiesto inválido")
    manifest = json.loads(meta.read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or manifest.get("es_simulacion") is not True:
        raise ValueError("Solo fixtures sintéticos v1")
    entries = manifest["files"]
    if nombre is None:
        found = [key for key, value in entries.items() if value["params"] == params]
        if len(found) != 1:
            raise ValueError("No hay una muestra preparada inequívoca para esos parámetros; genere en IA")
        nombre = found[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", nombre):
        raise ValueError("Nombre de escenario inválido")
    entry = entries[nombre]
    path = root / (nombre + ".csv")
    if path.is_symlink():
        raise ValueError("CSV enlazado no permitido")
    with path.open("rb") as stream:
        data = stream.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("Tamaño o hash de CSV incorrecto")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames != list(COLUMNAS):
        raise ValueError("Cabecera no canónica")
    rows = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("Columnas inconsistentes")
        rows.append({k: v for k, v in row.items() if v != ""})
        if len(rows) > 5000:
            raise ValueError("Más de 5000 filas")
    if not rows or len(rows) != entry["rows"]:
        raise ValueError("Conteo inconsistente")
    return rows, data, entry["params"]
