"""CSV operacional canónico de 13 columnas, no formato de entrenamiento.

Target/variables derivadas nunca son autoritativos en este CSV. None -> celda
vacía -> omitido al leer, igual al parser HTTP existente. No reemplaza ese parser.
"""
import csv
import io
from pathlib import Path

COLUMNAS = (
    "id_cita_externa", "paciente_anon_id", "sede", "especialidad", "medico", "fecha_hora_cita",
    "fecha_registro_cita", "tipo_paciente", "canal_origen", "inasistencias_previas",
    "reprogramaciones_prev", "asistencias_previas", "estado_actual",
)
MAX_FILAS = 5000
MAX_BYTES = 2 * 1024 * 1024
CODE_ROOT = Path(__file__).resolve().parents[1]


def proyectar_operacional(registro):
    if any(not registro.get(k) for k in COLUMNAS[:9]):
        raise ValueError("Faltan datos básicos del CSV operacional")
    return {key: registro.get(key) for key in COLUMNAS}


def construir_csv_operacional(registros) -> bytes:
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=COLUMNAS, lineterminator="\n")
    writer.writeheader()
    count = 0
    for count, row in enumerate(registros, start=1):
        if count > MAX_FILAS:
            raise ValueError("El CSV supera 5000 filas")
        writer.writerow(proyectar_operacional(row))
    if count == 0:
        raise ValueError("El CSV debe contener filas")
    data = text.getvalue().encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ValueError("El CSV supera 2 MiB")
    return data


def guardar_csv_operacional(registros, *, ruta_nueva: Path) -> Path:
    path = Path(ruta_nueva)
    if not path.is_absolute() or path.suffix.lower() != ".csv" or path.is_symlink():
        raise ValueError("Destino CSV absoluto, nuevo y no simbólico requerido")
    if path.resolve().is_relative_to(CODE_ROOT):
        raise ValueError("No escribir CSV dentro del código IA")
    data = construir_csv_operacional(registros)
    with path.open("xb") as stream:
        stream.write(data)
    return path


def leer_csv_operacional(ruta: Path) -> list[dict[str, str]]:
    with Path(ruta).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("El CSV supera 2 MiB")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    if reader.fieldnames != list(COLUMNAS):
        raise ValueError("Cabecera no canónica")
    rows = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("Número de columnas inconsistente")
        rows.append({k: v for k, v in row.items() if v != ""})
        if len(rows) > MAX_FILAS:
            raise ValueError("El CSV supera 5000 filas")
    if not rows:
        raise ValueError("El CSV debe contener filas")
    return rows
