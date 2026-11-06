"""Comparación experimental offline en procesos desechables, nunca promoción.

Modo referencia ejecuta el método legacy sin modificar su fuente: inyecta solo
los registros explícitos y el reloj. Ambos modos escriben en /tmp nuevo.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch, Mock

import joblib
import numpy as np

NOW = datetime(2026, 11, 6, 8, tzinfo=timezone.utc)


def digest(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def main():
    mode, destination = sys.argv[1:]
    target = Path(destination)
    assert not target.exists()
    records = json.load(sys.stdin)
    assert len(records) == 1000
    with tempfile.TemporaryDirectory(prefix="training-a-", dir="/tmp") as temp:
        if mode == "reference":
            from app.modules.ia import predictor as legacy
            active_path = legacy.RUTA_ARTEFACTO
            before = hashlib.sha256(active_path.read_bytes()).hexdigest()
            clock = Mock(wraps=datetime)
            clock.now.return_value = NOW
            candidate = Path(temp) / "reference-only.joblib"
            with patch.object(legacy, "cargar_citas_historicas", return_value=records), patch.object(legacy, "datetime", clock):
                artifact = legacy.entrenar_y_serializar_modelo(ruta_salida=candidate)
            matrix, features = legacy._construir_matriz(records)
            y = np.array([int(r["target_no_show"]) for r in records])
            tr, other, _, y_other = legacy.train_test_split(np.arange(len(records)), y,
                test_size=0.30, stratify=y, random_state=42)
            val, test, _, _ = legacy.train_test_split(other, y_other, test_size=0.50, stratify=y_other, random_state=42)
            splits = (tr, val, test)
            normalized_rows = [legacy._derivar_features_fila({**r, "tipo_paciente": r["tipo_paciente"].lower(),
                "canal_origen": r["canal_origen"].lower()}) for r in records[:10]]
            registry_unchanged = True  # Referencia solo existe en este proceso aislado.
        elif mode == "candidate":
            from app.config import MODEL_PATH
            from app.core.model_registry import registry
            from training.preprocessing import construir_matriz, derivar_features_fila
            from training.trainer import entrenar
            from training.serialization import guardar_candidato
            active_path = MODEL_PATH
            before = hashlib.sha256(active_path.read_bytes()).hexdigest()
            assert registry.load_model()
            active_state = registry._state
            result = entrenar(records, version_modelo="QA_A_CANDIDATE", version_dataset="QA_A_LEGACY_FIXTURE", fecha_entrenamiento=NOW)
            artifact = result.artefacto
            candidate = guardar_candidato(result, directorio_nuevo=Path(temp) / "candidate-new")
            matrix, features = construir_matriz(records)
            splits = (result.particiones.train, result.particiones.val, result.particiones.test)
            normalized_rows = [derivar_features_fila({**r, "tipo_paciente": r["tipo_paciente"].lower(),
                "canal_origen": r["canal_origen"].lower()}) for r in records[:10]]
            registry_unchanged = registry._state is active_state and registry.version_modelo == "LightGBM_v1.0.0"
            assert registry_unchanged
        else:
            raise ValueError("Modo no autorizado")

        loaded = joblib.load(candidate)  # Archivo creado por este mismo proceso.
        learned = {}
        for key in ("pipeline", "pipeline_baseline"):
            pipeline = artifact[key]
            assert np.array_equal(pipeline.predict_proba(matrix), loaded[key].predict_proba(matrix))
            prep = pipeline.named_steps["prep"]
            num = prep.named_transformers_["num"]
            cat = prep.named_transformers_["cat"]
            learned[key] = {
                "clf_params": pipeline.named_steps["clf"].get_params(deep=False),
                "probabilities_sha256": digest(pipeline.predict_proba(matrix)),
                "transformed_sha256": digest(prep.transform(matrix)),
                "numeric_statistics": num.named_steps["imputer"].statistics_.tolist(),
                "scaler_mean": num.named_steps["scaler"].mean_.tolist(),
                "scaler_scale": num.named_steps["scaler"].scale_.tolist(),
                "categories": [list(c) for c in cat.named_steps["ohe"].categories_],
            }
        original_model_version = artifact["version_modelo"]
        original_dataset_version = artifact["dataset_info"]["version_dataset"]
        metadata = {k: v for k, v in artifact.items() if k not in ("pipeline", "pipeline_baseline")}
        # Únicas diferencias de identidad previstas para no reutilizar versión activa.
        metadata["version_modelo"] = "<candidate-identity>"
        metadata["dataset_info"] = {**metadata["dataset_info"], "version_dataset": "<explicit-dataset-identity>"}
        assert hashlib.sha256(active_path.read_bytes()).hexdigest() == before
        report = {"mode": mode, "model_version": original_model_version, "dataset_version": original_dataset_version,
            "comparison": {"metadata": metadata, "learned": learned,
                "features": features, "normalization_cases": normalized_rows,
                "splits": [{"rows": len(s), "indices_sha256": digest(np.asarray(s, dtype=np.int64))} for s in splits]},
            "proof": {"serialization_roundtrip": True, "active_model_unchanged": True,
                "registry_not_promoted": registry_unchanged, "temporary_candidate_only": True}}
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(f"Entrenamiento offline {mode}: completado en scratch, sin promoción")


if __name__ == "__main__":
    main()
