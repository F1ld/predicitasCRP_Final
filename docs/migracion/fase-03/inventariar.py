"""Inventario de bytes reales; no simula manifiestos de entrenamiento/promoción."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = ROOT / "data/manifests/inventario-fase-03.v1.json"
    if target.exists():
        raise SystemExit("Inventario ya existe; no sobrescribir evidencia")
    copy_data = json.loads((HERE / "copias.json").read_text(encoding="utf-8"))
    validation = json.loads((ROOT / "runtime/test-results/fase-03/importacion_canonica.json").read_text(encoding="utf-8"))
    files = []
    for item in copy_data["copies"]:
        source, dest = ROOT / item["source"], ROOT / item["destination"]
        assert sha(source) == sha(dest) == item["sha256"]
        record = {**item, "bytes": dest.stat().st_size, "original_generation_date": None, "original_seed": None, "original_reference_date": None}
        if dest.suffix == ".csv":
            with dest.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                record["columns"] = reader.fieldnames
                rows = list(reader)
            record.update({"type": "OPERATIONAL_SYNTHETIC_SAMPLE", "rows": len(rows), "appointment_date_min": min(r["fecha_hora_cita"] for r in rows), "appointment_date_max": max(r["fecha_hora_cita"] for r in rows), "synthetic": True, "canonical": True, "versioned_in_git": True, "validation": next(r for r in validation["samples"] if r["archivo"] == dest.name)})
        else:
            observed = dest.stat()
            readonly = bool(observed.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY) if hasattr(observed, "st_file_attributes") else not bool(observed.st_mode & stat.S_IWUSR)
            assert readonly
            record.update({"type": "LEGACY_PRESERVATION_COPY", "active_serving_source": item["source"], "copy_is_active": False, "loaded_or_promoted": False, "versioned_in_git": False, "readonly_attribute_observed": readonly, "mode_observed": oct(observed.st_mode), "raw_dataset_sha256": None, "split_hashes": None, "complete_training_lineage": False, "trust_origin": "Artefacto interno local conservado y respaldado desde fase 0; no upload externo"})
        files.append(record)
    exclusive = []
    for path in sorted((ROOT / "apps/frontend/tests/fixtures").glob("*.csv")):
        exclusive.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "owner": "frontend", "moved": False})
    aliases = []
    for name, canonical in (("citas_para_importar_variado.csv", "data/samples/importacion/citas_para_importar_variado.csv"), ("apps/backend/data/citas_para_importar_variado.csv", "data/samples/importacion/citas_para_importar_variado.csv"), ("apps/backend/data/citas_demo.csv", "data/samples/importacion/citas_demo.csv")):
        assert sha(ROOT / name) == sha(ROOT / canonical)
        aliases.append({"path": name, "canonical": canonical, "sha256": sha(ROOT / name), "status": "PRESERVED_COMPATIBILITY_COPY_NO_AUTO_SYNC"})
    data = {"format": "predicitas.file_inventory/v1", "recorded_utc": datetime.now(timezone.utc).isoformat(), "purpose": "Inventario de preservación y muestras, no manifiesto aprobado de dataset/modelo", "reference_clock_for_import_validation": validation["reference_clock"], "files": files, "frontend_exclusive_fixtures": exclusive, "compatibility_copies": aliases, "unchanged_contract_fixtures": "contracts/examples/", "unknown_metadata_policy": "null: no inferir fecha/semilla/linaje original de valores por defecto actuales", "raw_or_processed_dataset_created": False}
    with target.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print("Inventario creado: dos muestras, snapshot legacy no promovido y cuatro fixtures exclusivos.")


if __name__ == "__main__":
    main()
