"""Exporta OpenAPI/DDL sin conectar a PostgreSQL (para comparar dos imágenes)."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, "/app")

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.main import app
from app.core.database import Base


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nombre", required=True, choices=["antes", "despues"])
    args = parser.parse_args()
    ddl = []
    for table in Base.metadata.sorted_tables:
        ddl.append(str(CreateTable(table).compile(dialect=postgresql.dialect())))
        ddl.extend(str(CreateIndex(index).compile(dialect=postgresql.dialect())) for index in sorted(table.indexes, key=lambda i: i.name))
    payload = dict(openapi=app.openapi(), ddl=ddl)
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    Path(f"/results/contrato-{args.nombre}.json").write_bytes(data)
    print(json.dumps(dict(nombre=args.nombre, sha256=hashlib.sha256(data).hexdigest(),
        rutas=len(payload["openapi"]["paths"]), tablas=len(Base.metadata.tables),
        imports_ml=[name for name in ("numpy", "joblib", "sklearn", "lightgbm") if name in sys.modules])))


if __name__ == "__main__":
    main()
