"""Pipeline offline explícito. Solo escribe versiones nuevas, nunca el activo."""
import hashlib
from functools import lru_cache
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
from datetime import date, datetime, time

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.config import MODEL_REGISTRY_DIR
from datasets.operational_csv import construir_csv_operacional
from datasets.synthetic import generar_citas
from datasets.temporal import LIMA
from datasets.training_rows import fila_entrenamiento
from training.evaluation import particionar, verificar_sin_data_leakage
from training.serialization import guardar_candidato
from training.trainer import entrenar


def bytes_json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def jsonl(rows):
    return b"".join(bytes_json(row) for row in rows)


def validar_version(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", value):
        raise ValueError("Versión segura de hasta 100 caracteres requerida")
    return value


def validar_fecha(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Fecha explícita con zona requerida")


def nuevo_destino(parent, identity):
    parent = Path(parent)
    if not parent.is_absolute() or not parent.is_dir():
        raise ValueError("Directorio padre absoluto existente requerido")
    target = parent.resolve() / validar_version(identity)
    code = Path(__file__).resolve().parents[1]
    registry = MODEL_REGISTRY_DIR.resolve()
    if target.is_relative_to(code) or target.is_relative_to(registry):
        raise ValueError("No escribir en código ni registry de inferencia")
    if target.exists() or target.is_symlink():
        raise FileExistsError("La versión ya existe; no se sobrescribe")
    return target


@lru_cache(maxsize=16)
def _validator(relative, contracts):
    root = Path(contracts).resolve()
    registry = Registry()
    for path in root.rglob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8-sig"))
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(path.as_uri(), resource)
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], resource)
    schema = json.loads((root / relative).read_text(encoding="utf-8-sig"))
    return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())


def validar_contrato(value, relative, contracts):
    _validator(relative, str(Path(contracts).resolve())).validate(value)


def preparar(rows, *, corte, contracts):
    if len(rows) != 1000:
        raise ValueError("Esta extracción conserva exactamente 1000 históricos")
    flat = []
    ids = set()
    for row in rows:
        validar_contrato(row, "data/training-row.v1.schema.json", contracts)
        record = {k: v for k, v in row.items() if k != "features"} | row["features"]
        if fila_entrenamiento(record, corte=corte) != row:
            raise ValueError("Fila no canónica")
        if row["id_cita_externa"] in ids:
            raise ValueError("Identificador de cita duplicado")
        ids.add(row["id_cita_externa"])
        flat.append(record)
    import numpy as np
    split = particionar(np.array([r["target_no_show"] for r in flat]))
    control = verificar_sin_data_leakage(flat, split.train, split.val, split.test)
    return flat, split, control


def generar(*, version_dataset, semilla, fecha_corte, generado_en, fuente,
            directorio, contracts, proximas):
    if fuente != "SINTETICO_GENERADO" or semilla != 42:
        raise ValueError("Solo fuente sintética explícita y semilla 42 en este bloque")
    if type(proximas) is not int or not 0 <= proximas <= 4000:
        raise ValueError("Próximas fuera de rango 0..4000")
    validar_fecha(generado_en)
    target = nuevo_destino(directorio, version_dataset)
    corte = datetime.combine(fecha_corte, time.max, tzinfo=LIMA)
    records = generar_citas(historicas=1000, proximas=proximas, semilla=semilla,
                            desde=fecha_corte, tasa_no_show=0.20, con_invalidas=False)
    rows = [fila_entrenamiento(r, corte=corte) for r in records
            if r["estado_actual"] in ("ATENDIDA", "NO_SHOW")]
    flat, split, control = preparar(rows, corte=corte, contracts=contracts)
    files = {"raw.jsonl": jsonl(rows), "seed.csv": construir_csv_operacional(records)}
    parts = {}
    for name in ("train", "val", "test"):
        selected = [rows[int(i)] for i in getattr(split, name)]
        data = jsonl(selected)
        files[name + ".jsonl"] = data
        parts[name] = {"filas": len(selected), "no_show": sum(r["target_no_show"] for r in selected),
                       "sha256": sha(data), "sha256_ids": sha(jsonl([r["id_cita_externa"] for r in selected]))}
    positive = sum(r["target_no_show"] for r in flat)
    manifest = {"version_contrato": "1.0", "version_dataset": version_dataset,
        "version_features": "pre-cita-v1", "proposito": "TRAINING_RUN", "fuente": fuente,
        "linaje_completo": True, "semilla": semilla, "fecha_corte": fecha_corte.isoformat(),
        "generado_en": generado_en.isoformat(), "sha256_raw": sha(files["raw.jsonl"]),
        "total_historicas": len(rows), "distribucion": {"atendidas": len(rows) - positive, "no_show": positive},
        "particiones": parts, "sin_interseccion_ids": True, "control_leakage": control, "es_simulacion": True}
    validar_contrato(manifest, "data/dataset-manifest.v1.schema.json", contracts)
    files["manifest.json"] = bytes_json(manifest)
    # El seed no forma parte del contrato de entrenamiento; linaje separado.
    files["seed-manifest.json"] = bytes_json({"version_dataset": version_dataset,
        "sha256": sha(files["seed.csv"]), "filas": len(records), "proximas": proximas,
        "es_simulacion": True, "fecha_corte": fecha_corte.isoformat()})
    target.mkdir(exist_ok=False)
    for name, data in files.items():
        with (target / name).open("xb") as stream:
            stream.write(data)
    return target


def validar_dataset(dataset, *, contracts):
    dataset = Path(dataset)
    manifest_bytes = (dataset / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    validar_contrato(manifest, "data/dataset-manifest.v1.schema.json", contracts)
    if manifest["fuente"] != "SINTETICO_GENERADO" or manifest["proposito"] != "TRAINING_RUN":
        raise ValueError("Fuente o propósito no implementados en este bloque")
    raw = (dataset / "raw.jsonl").read_bytes()
    if sha(raw) != manifest["sha256_raw"]:
        raise ValueError("Hash raw incorrecto")
    rows = [json.loads(line) for line in raw.splitlines()]
    corte = datetime.combine(date.fromisoformat(manifest["fecha_corte"]), time.max, tzinfo=LIMA)
    flat, split, control = preparar(rows, corte=corte, contracts=contracts)
    positive = sum(r["target_no_show"] for r in rows)
    if (manifest["total_historicas"] != len(rows) or manifest["control_leakage"] != control
            or manifest["distribucion"] != {"atendidas": len(rows) - positive, "no_show": positive}):
        raise ValueError("Conteos/control inconsistentes")
    for name in ("train", "val", "test"):
        selected = [rows[int(i)] for i in getattr(split, name)]
        data = (dataset / (name + ".jsonl")).read_bytes()
        expected = {"filas": len(selected), "no_show": sum(r["target_no_show"] for r in selected),
                    "sha256": sha(data), "sha256_ids": sha(jsonl([r["id_cita_externa"] for r in selected]))}
        if data != jsonl(selected) or manifest["particiones"][name] != expected:
            raise ValueError("Partición alterada o inconsistente")
    return flat, manifest, manifest_bytes


def entrenar_candidato(*, dataset, version_modelo, fecha, directorio, contracts):
    validar_fecha(fecha)
    target = nuevo_destino(directorio, version_modelo)
    rows, dataset_manifest, dataset_bytes = validar_dataset(dataset, contracts=contracts)
    result = entrenar(rows, version_modelo=version_modelo,
        version_dataset=dataset_manifest["version_dataset"], fecha_entrenamiento=fecha)
    artifact = result.artefacto
    metrics = {k: artifact[k] for k in ("metricas_val", "metricas_test", "metricas_baseline_test",
                                      "auditoria_equidad", "importancia_global_variables")}
    metrics_bytes = bytes_json(metrics)
    dependencies = {k: version(k) for k in ("lightgbm", "scikit-learn", "numpy", "joblib", "scipy")}
    dependencies["python"] = platform.python_version()
    path = guardar_candidato(result, directorio_nuevo=target)
    manifest = {"version_contrato": "1.0", "version_modelo": version_modelo,
        "version_features": "pre-cita-v1", "version_dataset": dataset_manifest["version_dataset"],
        "proposito": "TRAINING_RUN", "linaje_completo": True, "estado": "CANDIDATO",
        "algoritmo": "LightGBM", "entrenado_en": artifact["fecha_entrenamiento"],
        "artifact": {"relative_path": version_modelo + "/candidate.joblib", "sha256": sha(path.read_bytes())},
        "dataset_manifest_sha256": sha(dataset_bytes), "metrics_sha256": sha(metrics_bytes),
        "dependencias": dependencies, "umbrales": {"medio": 0.3, "alto": 0.45},
        "metricas_test": {key: artifact["metricas_test"][key]
            for key in ("f1_score", "precision", "recall", "roc_auc", "pr_auc")}, "es_simulacion": True}
    validar_contrato(manifest, "ia/model-manifest.v1.schema.json", contracts)
    for name, data in (("dataset-manifest.json", dataset_bytes), ("metrics.json", metrics_bytes),
                       ("manifest.json", bytes_json(manifest))):
        with (target / name).open("xb") as stream:
            stream.write(data)
    return target
