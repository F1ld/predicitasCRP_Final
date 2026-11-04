"""Genera fixtures de contrato sinteticos, sin entrenar ni consultar BD."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main():
    source = json.loads((ROOT / "docs/migracion/fase-00/ia_baseline.json").read_text(encoding="utf-8"))
    features = source["predictions"][0]["features"]
    prediction = source["predictions"][0]["prediction"]
    request = {"version_contrato": "1.0", "id_solicitud": "10000000-0000-4000-8000-000000000001", "version_modelo": "LightGBM_v1.0.0", "version_features": "pre-cita-v1", "features": features}
    response = {"version_contrato": "1.0", "id_solicitud": request["id_solicitud"], "version_modelo": request["version_modelo"], "version_features": "pre-cita-v1", "probabilidad_no_show": float(prediction["probabilidad_no_show"]), "nivel_riesgo": prediction["nivel_riesgo"], "umbrales": {"medio": 0.3, "alto": 0.45}, "features_snapshot": prediction["features_snapshot"], "explicabilidad_resumen": prediction["explicabilidad_resumen"], "es_simulacion": True, "rotulo_etico": "Resultado simulado — Dataset sintético acreditado (RF-056)"}
    cases = []
    def add(name, schema, data, valid=True, semantic_valid=True, context=None):
        row = {"id": name, "schema": schema, "schema_valid": valid, "semantic_valid": semantic_valid, "data": copy.deepcopy(data)}
        if context is not None: row["context"] = copy.deepcopy(context)
        cases.append(row)
    def changed(value, **changes):
        return {**copy.deepcopy(value), **changes}
    add("features-validas", "data/features.v1.schema.json", features)
    add("features-target-prohibido", "data/features.v1.schema.json", changed(features, target_no_show=1), False)
    add("features-sin-nulos", "data/features.v1.schema.json", changed(features, asistencias_previas=None), False)
    add("features-contador-negativo", "data/features.v1.schema.json", changed(features, inasistencias_previas=-1), False)
    add("features-domingo", "data/features.v1.schema.json", changed(features, dia_semana="DOMINGO"), False)
    add("features-no-coaccion-string", "data/features.v1.schema.json", changed(features, antelacion_dias="32"), False)
    add("features-no-bool-como-int", "data/features.v1.schema.json", changed(features, antelacion_dias=True), False)
    add("prediccion-request-valido", "ia/predict-request.v1.schema.json", request)
    add("prediccion-request-uuid-invalido", "ia/predict-request.v1.schema.json", changed(request, id_solicitud="paciente-123"), False)
    add("prediccion-request-version-invalida", "ia/predict-request.v1.schema.json", changed(request, version_contrato="2.0"), False)
    add("prediccion-response-valida", "ia/predict-response.v1.schema.json", response, context=request)
    add("prediccion-score-fuera-rango", "ia/predict-response.v1.schema.json", changed(response, probabilidad_no_show=1.2), False)
    add("prediccion-score-string-interno", "ia/predict-response.v1.schema.json", changed(response, probabilidad_no_show="0.999"), False)
    add("prediccion-exceso-decimales", "ia/predict-response.v1.schema.json", changed(response, probabilidad_no_show=0.9991), False)
    add("prediccion-nivel-inconsistente", "ia/predict-response.v1.schema.json", changed(response, probabilidad_no_show=0.3, nivel_riesgo="ALTO"), False)
    add("prediccion-explicacion-larga", "ia/predict-response.v1.schema.json", changed(response, explicabilidad_resumen="x" * 256), False)
    add("prediccion-id-no-corresponde", "ia/predict-response.v1.schema.json", changed(response, id_solicitud="10000000-0000-4000-8000-000000000002"), semantic_valid=False, context=request)
    add("prediccion-modelo-no-corresponde", "ia/predict-response.v1.schema.json", changed(response, version_modelo="otro_modelo"), semantic_valid=False, context=request)
    snap = changed(response["features_snapshot"], tasa_no_show_previa=0.1)
    add("prediccion-formula-derivada-invalida", "ia/predict-response.v1.schema.json", changed(response, features_snapshot=snap), semantic_valid=False, context=request)
    for score, risk in ((0, "BAJO"), (0.299, "BAJO"), (0.3, "MEDIO"), (0.45, "MEDIO"), (0.451, "ALTO"), (1, "ALTO")):
        add(f"borde-{score}-{risk}", "ia/predict-response.v1.schema.json", changed(response, probabilidad_no_show=score, nivel_riesgo=risk), context=request)
    batch = {key: value for key, value in request.items() if key != "features"}
    batch["items"] = [{"id_item": "item-1", "features": features}, {"id_item": "item-2", "features": source["predictions"][1]["features"]}]
    add("batch-valido", "ia/batch-request.v1.schema.json", batch)
    add("batch-vacio", "ia/batch-request.v1.schema.json", changed(batch, items=[]), False)
    add("batch-mas-100", "ia/batch-request.v1.schema.json", changed(batch, items=[{"id_item": f"item-{i}", "features": features} for i in range(101)]), False)
    add("batch-ids-duplicados", "ia/batch-request.v1.schema.json", changed(batch, items=[batch["items"][0], batch["items"][0]]), semantic_valid=False)
    second = source["predictions"][1]["prediction"]
    second_response = changed(response, probabilidad_no_show=float(second["probabilidad_no_show"]), nivel_riesgo=second["nivel_riesgo"], features_snapshot=second["features_snapshot"], explicabilidad_resumen=second["explicabilidad_resumen"])
    batch_response = {"version_contrato": "1.0", "id_solicitud": request["id_solicitud"], "version_modelo": request["version_modelo"], "items": [{"id_item": "item-1", "resultado": response}, {"id_item": "item-2", "resultado": second_response}]}
    add("batch-response-valida", "ia/batch-response.v1.schema.json", batch_response, context=batch)
    add("batch-response-incompleta", "ia/batch-response.v1.schema.json", changed(batch_response, items=[batch_response["items"][0]]), semantic_valid=False, context=batch)
    add("batch-response-extra", "ia/batch-response.v1.schema.json", changed(batch_response, items=[*batch_response["items"], {"id_item": "item-3", "resultado": response}]), semantic_valid=False, context=batch)
    row = {"id_cita_externa": "CIT-CON-001", "paciente_anon_id": "PAC-CON-001", "sede": "SAN_ISIDRO", "especialidad": "PEDIATRIA", "medico": "Medico sintetico", "fecha_hora_cita": "2026-11-09T09:00:00-05:00", "fecha_registro_cita": "2026-11-01T09:00:00-05:00", "tipo_paciente": "NUEVO", "canal_origen": "WEB", "inasistencias_previas": None, "asistencias_previas": None, "reprogramaciones_prev": 0, "estado_actual": "RECIBIDA"}
    add("import-normalizado-valido", "data/cita-import-normalizada.v1.schema.json", row)
    add("import-extra-ignorado", "data/cita-import-normalizada.v1.schema.json", changed(row, columna_extra="ignorada"))
    add("import-sede-invalida", "data/cita-import-normalizada.v1.schema.json", changed(row, sede="MIRAFLORES"), False)
    add("import-liberada-prohibida", "data/cita-import-normalizada.v1.schema.json", changed(row, estado_actual="LIBERADA"), False)
    add("import-domingo-semantico", "data/cita-import-normalizada.v1.schema.json", changed(row, fecha_hora_cita="2026-11-08T09:00:00-05:00"), semantic_valid=False)
    add("import-desenlace-futuro", "data/cita-import-normalizada.v1.schema.json", changed(row, estado_actual="NO_SHOW"), semantic_valid=False)
    add("import-fechas-invertidas", "data/cita-import-normalizada.v1.schema.json", changed(row, fecha_registro_cita="2026-11-10T09:00:00-05:00"), semantic_valid=False)
    add("import-inversion-misma-fecha-legacy", "data/cita-import-normalizada.v1.schema.json", changed(row, fecha_registro_cita="2026-11-09T10:00:00-05:00"))
    training = {"id_cita_externa": "CIT-SIM-CON001", "paciente_anon_id": "PAC-SIM-CON001", "fecha_hora_cita": "2026-10-30T15:00:00-05:00", "fecha_registro_cita": "2026-09-28T09:00:00-05:00", "estado_actual": "NO_SHOW", "target_no_show": 1, "features": features}
    add("training-valido", "data/training-row.v1.schema.json", training)
    add("training-target-incoherente", "data/training-row.v1.schema.json", changed(training, target_no_show=0), False)
    add("training-sin-desenlace", "data/training-row.v1.schema.json", changed(training, estado_actual="RECIBIDA"), False)
    add("training-features-incoherentes", "data/training-row.v1.schema.json", changed(training, features=changed(features, antelacion_dias=1)), semantic_valid=False)
    def split(size, no_show, digit): return {"filas": size, "no_show": no_show, "sha256": digit * 64, "sha256_ids": digit * 64}
    dataset = {"version_contrato": "1.0", "version_dataset": "CONTRACT_FIXTURE_DATASET", "version_features": "pre-cita-v1", "proposito": "CONTRACT_FIXTURE", "fuente": "SINTETICO_GENERADO", "semilla": 42, "fecha_corte": "2026-11-03", "generado_en": "2026-11-03T13:00:00Z", "sha256_raw": "a" * 64, "total_historicas": 1000, "distribucion": {"atendidas": 795, "no_show": 205}, "particiones": {"train": split(700, 144, "b"), "val": split(150, 31, "c"), "test": split(150, 30, "d")}, "sin_interseccion_ids": True, "control_leakage": source["dataset_info"]["control_leakage"], "es_simulacion": True}
    dataset["linaje_completo"] = True
    add("dataset-manifest-ejemplo", "data/dataset-manifest.v1.schema.json", dataset)
    add("dataset-pocos-historicos", "data/dataset-manifest.v1.schema.json", changed(dataset, total_historicas=999), False)
    add("dataset-conteos-incoherentes", "data/dataset-manifest.v1.schema.json", changed(dataset, distribucion={"atendidas": 800, "no_show": 205}), semantic_valid=False)
    invalid_split = copy.deepcopy(dataset)
    invalid_split["particiones"]["train"]["filas"] = 699
    add("dataset-splits-incoherentes", "data/dataset-manifest.v1.schema.json", invalid_split, semantic_valid=False)
    manifest = {"version_contrato": "1.0", "version_modelo": "CONTRACT_FIXTURE_MODEL", "version_features": "pre-cita-v1", "version_dataset": dataset["version_dataset"], "proposito": "CONTRACT_FIXTURE", "estado": "CANDIDATO", "algoritmo": "LightGBM", "entrenado_en": "2026-11-03T13:00:00Z", "artifact": {"relative_path": "CONTRACT_FIXTURE_MODEL/modelo.joblib", "sha256": "e" * 64}, "dataset_manifest_sha256": "f" * 64, "metrics_sha256": "1" * 64, "dependencias": {"python": "3.12.16", "lightgbm": "4.7.0", "scikit-learn": "1.9.1", "numpy": "2.5.4", "joblib": "1.6.0"}, "umbrales": {"medio": 0.3, "alto": 0.45}, "metricas_test": {key: source["metricas_test"][key] for key in ("f1_score", "precision", "recall", "roc_auc", "pr_auc")}, "es_simulacion": True}
    manifest["linaje_completo"] = True
    add("model-manifest-ejemplo", "ia/model-manifest.v1.schema.json", manifest)
    add("model-fixture-no-promocionable", "ia/model-manifest.v1.schema.json", changed(manifest, estado="APROBADO"), False)
    add("model-path-traversal", "ia/model-manifest.v1.schema.json", changed(manifest, artifact={"relative_path": "../modelo.joblib", "sha256": "e" * 64}), False)
    add("active-pointer-valido", "ia/active-model.v1.schema.json", {"version_modelo": "LightGBM_v1.0.0", "manifest_sha256": "2" * 64})
    add("active-pointer-invalido", "ia/active-model.v1.schema.json", {"version_modelo": "../modelo", "manifest_sha256": "2" * 64}, False)
    add("error-valido", "ia/error.v1.schema.json", {"error": {"codigo": "MODELO_NO_DISPONIBLE", "mensaje": "Modelo no disponible", "campos": {}}})
    add("error-sin-envelope", "ia/error.v1.schema.json", {"detail": "error"}, False)
    legacy = changed(dataset, version_dataset="CONTRACT_LEGACY_EXAMPLE", proposito="LEGACY_IMPORT", fuente="LEGACY_METADATA_ONLY", linaje_completo=False, fecha_corte=None, sha256_raw=None)
    for value in legacy["particiones"].values(): value.update(sha256=None, sha256_ids=None)
    add("dataset-legacy-honesto", "data/dataset-manifest.v1.schema.json", legacy)
    add("dataset-legacy-no-inventar-hash", "data/dataset-manifest.v1.schema.json", changed(legacy, sha256_raw="a" * 64), False)
    add("dataset-training-exige-linaje", "data/dataset-manifest.v1.schema.json", changed(legacy, proposito="TRAINING_RUN"), False)
    add("dataset-training-exige-corte", "data/dataset-manifest.v1.schema.json", changed(dataset, proposito="TRAINING_RUN", fecha_corte=None), False)
    add("model-legacy-explicito", "ia/model-manifest.v1.schema.json", changed(manifest, proposito="LEGACY_IMPORT", linaje_completo=False))
    target = ROOT / "contracts/examples/casos.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream: json.dump({"reference_now": "2026-11-03T08:00:00-05:00", "all_data_synthetic": True, "not_training_evidence": True, "cases": cases}, stream, ensure_ascii=False, indent=2)
    print(f"Generados {len(cases)} ejemplos; no se creo dataset ni artefacto IA.")


if __name__ == "__main__": main()
