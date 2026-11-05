"""Exporta una muestra operacional sintética, sin consultar BD ni entrenar.

Requiere --salida absoluta y --fecha-referencia YYYY-MM-DD. Mantiene las cuatro
filas de rechazo intencionales del generador; NO es un seed ni dataset IA.
Nunca sobrescribe un archivo ni escribe dentro del código/muestras canónicas.
"""
import argparse
import csv
from datetime import date
import hashlib
import io
from pathlib import Path

from app.modules.citas.synthetic import generar_citas

APP_DIR = Path(__file__).resolve().parents[1]
RAIZ = APP_DIR.parent.parent if APP_DIR.parent.name == "apps" else None
COLUMNAS = (
    "id_cita_externa", "paciente_anon_id", "sede", "especialidad", "medico",
    "fecha_hora_cita", "fecha_registro_cita", "tipo_paciente", "canal_origen",
    "inasistencias_previas", "reprogramaciones_prev", "asistencias_previas", "estado_actual",
)


def resolver_salida(salida: Path) -> Path:
    if not salida.is_absolute():
        raise ValueError("--salida debe ser una ruta absoluta, no dependiente del CWD")
    if salida.is_symlink():
        raise ValueError("El destino no puede ser un enlace simbólico")
    destino = salida.resolve()
    if destino.suffix.lower() != ".csv":
        raise ValueError("--salida debe terminar en .csv")
    if destino.is_relative_to(APP_DIR):
        raise ValueError("El exportador no escribe dentro del código backend")
    if RAIZ is not None and destino.is_relative_to(RAIZ) and not any(
        destino.is_relative_to(RAIZ / "runtime" / carpeta)
        for carpeta in ("exports", "tmp", "test-results")
    ):
        raise ValueError("Dentro del repositorio, usar runtime/exports, runtime/tmp o runtime/test-results")
    if destino.exists():
        raise FileExistsError(f"El destino ya existe; elegir otro nombre: {destino}")
    return destino


def exportar_csv(salida: Path, *, filas: int, semilla: int, fecha_referencia: date) -> Path:
    if filas < 1:
        raise ValueError("--filas debe ser mayor que cero")
    destino = resolver_salida(salida)
    registros = generar_citas(
        historicas=0, proximas=filas, semilla=semilla, prefijo="DEMO", desde=fecha_referencia,
    )
    # Proyección del contrato operacional, sin features derivadas ni etiqueta IA.
    contenido = io.StringIO(newline="")
    escritor = csv.DictWriter(contenido, fieldnames=COLUMNAS, extrasaction="ignore")
    escritor.writeheader()
    escritor.writerows(registros)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("x", newline="", encoding="utf-8") as archivo:
        archivo.write(contenido.getvalue())
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filas", type=int, default=20)
    parser.add_argument("--semilla", type=int, default=7)
    parser.add_argument("--salida", type=Path, required=True, help="CSV nuevo en ruta absoluta")
    parser.add_argument("--fecha-referencia", type=date.fromisoformat, required=True, help="Fecha reproducible YYYY-MM-DD")
    args = parser.parse_args()
    try:
        destino = exportar_csv(args.salida, filas=args.filas, semilla=args.semilla, fecha_referencia=args.fecha_referencia)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    digest = hashlib.sha256(destino.read_bytes()).hexdigest()
    print(f"{args.filas + 4} filas (4 de rechazo intencional) en {destino}; "
          f"referencia={args.fecha_referencia.isoformat()}; semilla={args.semilla}; SHA-256={digest}")


if __name__ == "__main__":
    main()
