"""Generación canónica de muestras (NO seed): conserva cuatro filas inválidas.

CLI trasladado desde backend; parámetros y CSV de 13 columnas preservados.
La generación es manual, offline, sin BD/modelo ni import de backend.
"""
import argparse
import csv
from datetime import date
import hashlib
import io
from pathlib import Path

from datasets.synthetic import generar_citas
from datasets.operational_csv import COLUMNAS

APP_DIR = Path(__file__).resolve().parents[1]
RAIZ = APP_DIR.parent.parent if APP_DIR.parent.name == "apps" else None


def resolver_salida(salida):
    if not salida.is_absolute():
        raise ValueError("--salida debe ser una ruta absoluta, no dependiente del CWD")
    if salida.is_symlink():
        raise ValueError("El destino no puede ser un enlace simbólico")
    destino = salida.resolve()
    if destino.suffix.lower() != ".csv":
        raise ValueError("--salida debe terminar en .csv")
    if destino.is_relative_to(APP_DIR):
        raise ValueError("El exportador no escribe dentro del código IA")
    if RAIZ is not None and destino.is_relative_to(RAIZ) and not any(
        destino.is_relative_to(RAIZ / "runtime" / carpeta)
        for carpeta in ("exports", "tmp", "test-results")
    ):
        raise ValueError("Dentro del repositorio, usar runtime/exports, runtime/tmp o runtime/test-results")
    if destino.exists():
        raise FileExistsError(f"El destino ya existe; elegir otro nombre: {destino}")
    return destino


def exportar_csv(salida, *, filas, semilla, fecha_referencia):
    if filas < 1:
        raise ValueError("--filas debe ser mayor que cero")
    destino = resolver_salida(salida)
    registros = generar_citas(historicas=0, proximas=filas, semilla=semilla,
                              prefijo="DEMO", desde=fecha_referencia)
    contenido = io.StringIO(newline="")
    escritor = csv.DictWriter(contenido, fieldnames=COLUMNAS, extrasaction="ignore")
    escritor.writeheader()
    escritor.writerows(registros)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("x", newline="", encoding="utf-8") as archivo:
        archivo.write(contenido.getvalue())
    return destino


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filas", type=int, default=20)
    parser.add_argument("--semilla", type=int, default=7)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--fecha-referencia", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    try:
        destino = exportar_csv(args.salida, filas=args.filas, semilla=args.semilla, fecha_referencia=args.fecha_referencia)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"{args.filas + 4} filas (4 de rechazo intencional) en {destino}; "
          f"referencia={args.fecha_referencia.isoformat()}; semilla={args.semilla}; SHA-256={hashlib.sha256(destino.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
