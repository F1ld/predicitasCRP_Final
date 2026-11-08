"""Exporta una muestra YA PREPARADA explícita, sin consultar BD ni generar.

Requiere --salida absoluta y --fecha-referencia YYYY-MM-DD. Mantiene las cuatro
filas de rechazo intencionales del generador; NO es un seed ni dataset IA.
La generación se trasladó a IA: python -m datasets.exportar_csv.
Este adaptador exige --fuente (bundle IA con manifiesto); no genera por fallback.
"""
import argparse
from datetime import date
import hashlib
import os
from pathlib import Path

from scripts.csv_preparado import COLUMNAS, leer_preparado

APP_DIR = Path(__file__).resolve().parents[1]
RAIZ = APP_DIR.parent.parent if APP_DIR.parent.name == "apps" else None


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


def exportar_csv(salida: Path, *, filas: int, semilla: int, fecha_referencia: date, fuente: Path | None = None) -> Path:
    if filas < 1:
        raise ValueError("--filas debe ser mayor que cero")
    destino = resolver_salida(salida)
    fuente = fuente or os.environ.get("PREDICITAS_EXPORT_FIXTURES_DIR")
    if not fuente:
        raise ValueError("--fuente requerida; generar muestras en el entorno IA con datasets.exportar_csv o datasets.qa_bundle")
    _, contenido, _ = leer_preparado(fuente, params=dict(historicas=0, proximas=filas,
        semilla=semilla, prefijo="DEMO", con_invalidas=True, desde=fecha_referencia.isoformat()))
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("xb") as archivo:
        archivo.write(contenido)
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filas", type=int, default=20)
    parser.add_argument("--semilla", type=int, default=7)
    parser.add_argument("--fuente", type=Path, help="Bundle sintético preparado explícitamente en IA")
    parser.add_argument("--salida", type=Path, required=True, help="CSV nuevo en ruta absoluta")
    parser.add_argument("--fecha-referencia", type=date.fromisoformat, required=True, help="Fecha reproducible YYYY-MM-DD")
    args = parser.parse_args()
    try:
        destino = exportar_csv(args.salida, filas=args.filas, semilla=args.semilla, fecha_referencia=args.fecha_referencia, fuente=args.fuente)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    digest = hashlib.sha256(destino.read_bytes()).hexdigest()
    print(f"{args.filas + 4} filas (4 de rechazo intencional) en {destino}; "
          f"referencia={args.fecha_referencia.isoformat()}; semilla={args.semilla}; SHA-256={digest}")


if __name__ == "__main__":
    main()
