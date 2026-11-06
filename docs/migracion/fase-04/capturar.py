"""Captura offline de API, metadata y predicciones; salida exclusiva, sin entrenar."""
import hashlib
import json
from pathlib import Path
import sys


def main():
    root = Path.cwd().parents[1]
    modelo = Path("app/modules/ia/artifacts/modelo_predicitas_v1.joblib")
    if not modelo.is_file():
        raise SystemExit("Falta el modelo preservado: no se permite entrenamiento implícito")
    before = hashlib.sha256(modelo.read_bytes()).hexdigest()
    from app.main import app
    from app.core.database import Base
    from app.modules.ia.predictor import predecir_cita_dict
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateIndex, CreateTable
    dialect = postgresql.dialect()
    ddl = []
    for table in Base.metadata.sorted_tables:
        ddl.append(str(CreateTable(table).compile(dialect=dialect)))
        ddl.extend(sorted(str(CreateIndex(index).compile(dialect=dialect)) for index in table.indexes))
    reference = json.loads((root / "docs/migracion/fase-00/ia_baseline.json").read_text())
    predictions = [predecir_cita_dict(item["features"]) for item in reference["predictions"]]
    assert hashlib.sha256(modelo.read_bytes()).hexdigest() == before
    data = {"openapi": app.openapi(), "ddl": ddl, "predictions": predictions, "model_sha256": before}
    with Path(sys.argv[1]).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")


if __name__ == "__main__":
    main()
