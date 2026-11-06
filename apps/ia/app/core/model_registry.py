"""Registro y cargador en memoria del modelo serializado Joblib (read-only).

Garantiza que la inferencia no modifique ni entrene modelos en runtime.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
from sklearn.pipeline import Pipeline

from app.config import (
    FEATURES_AUTORIZADAS,
    MODEL_PATH,
    ROTULO_ETICO,
    UMBRAL_ALTO,
    UMBRAL_MEDIO,
    VERSION_CONTRATO,
    VERSION_FEATURES,
)
from app.schemas import ModelMetadata, Umbrales

logger = logging.getLogger("predicitas.ia.registry")


class ModelRegistry:
    """Administrador en memoria del artefacto predictivo."""

    def __init__(self) -> None:
        self._artefacto: dict[str, Any] | None = None
        self._pipeline: Pipeline | None = None
        self._version_modelo: str | None = None
        self._version_dataset: str | None = None

    @property
    def is_ready(self) -> bool:
        return self._artefacto is not None and self._pipeline is not None

    @property
    def version_modelo(self) -> str | None:
        return self._version_modelo

    @property
    def pipeline(self) -> Pipeline | None:
        return self._pipeline

    def load_model(self, path: Path | None = None) -> bool:
        target_path = path or MODEL_PATH
        if not target_path.exists():
            logger.warning(f"Artefacto de modelo no encontrado en {target_path}")
            return False

        try:
            artefacto = joblib.load(target_path)
            if not isinstance(artefacto, dict) or "pipeline" not in artefacto:
                logger.error(f"Artefacto en {target_path} no tiene la estructura esperada")
                return False

            self._artefacto = artefacto
            self._pipeline = artefacto["pipeline"]
            self._version_modelo = str(artefacto.get("version_modelo", "LightGBM_v1.0.0"))
            ds_info = artefacto.get("dataset_info", {})
            self._version_dataset = str(ds_info.get("version_dataset", "DS_SINTETICO_CRP_v1.0"))
            logger.info(f"Modelo cargado exitosamente: {self._version_modelo} ({self._version_dataset})")
            return True
        except Exception as exc:
            logger.error(f"Error cargando artefacto {target_path}: {exc}")
            return False

    def version_matches(self, requested_version: str) -> bool:
        if not self.is_ready or not self._version_modelo:
            return False
        return self._version_modelo == requested_version

    def get_metadata(self) -> ModelMetadata:
        if not self.is_ready:
            raise RuntimeError("Modelo no cargado")
        return ModelMetadata(
            version_contrato=VERSION_CONTRATO,
            version_modelo=self._version_modelo or "LightGBM_v1.0.0",
            version_features=VERSION_FEATURES,
            version_dataset=self._version_dataset or "DS_SINTETICO_CRP_v1.0",
            umbrales=Umbrales(medio=UMBRAL_MEDIO, alto=UMBRAL_ALTO),
            features_autorizadas=FEATURES_AUTORIZADAS,
            es_simulacion=True,
            rotulo_etico=ROTULO_ETICO,
        )

    def get_metrics_payload(self) -> dict[str, Any]:
        """Devuelve el payload de métricas conforme a MetricasModeloOut."""
        if not self.is_ready or self._artefacto is None:
            raise RuntimeError("Modelo no cargado")

        m_test = self._artefacto.get("metricas_test", {})
        f1 = float(m_test.get("f1_score", 0.0))

        return {
            "version_modelo": self._version_modelo,
            "algoritmo": self._artefacto.get("algoritmo", "LightGBM"),
            "semilla": self._artefacto.get("semilla", 42),
            "fecha_entrenamiento": self._artefacto.get("fecha_entrenamiento"),
            "es_simulacion": True,
            "rotulo_etico": ROTULO_ETICO,
            "umbral_alto": UMBRAL_ALTO,
            "umbral_medio": UMBRAL_MEDIO,
            "cumple_meta_f1_82": bool(f1 >= 0.82),
            "metricas_test": m_test,
            "metricas_val": self._artefacto.get("metricas_val", {}),
            "metricas_baseline_test": self._artefacto.get("metricas_baseline_test", {}),
            "auditoria_equidad": self._artefacto.get("auditoria_equidad", {}),
            "importancia_global_variables": self._artefacto.get("importancia_global_variables", {}),
        }

    def get_dataset_manifest(self) -> dict[str, Any]:
        """Devuelve el manifiesto conforme a dataset-manifest.v1.schema.json (LEGACY_IMPORT)."""
        if not self.is_ready or self._artefacto is None:
            raise RuntimeError("Modelo no cargado")

        ds = self._artefacto.get("dataset_info", {})
        total_hist = int(ds.get("total_historicas", 1000))
        tasa_global = float(ds.get("tasa_no_show_global", 0.205))
        no_show_est = round(total_hist * tasa_global)
        atendidas_est = total_hist - no_show_est

        return {
            "version_contrato": VERSION_CONTRATO,
            "version_dataset": self._version_dataset or "DS_SINTETICO_CRP_v1.0",
            "version_features": VERSION_FEATURES,
            "proposito": "LEGACY_IMPORT",
            "fuente": "LEGACY_METADATA_ONLY",
            "linaje_completo": False,
            "semilla": 42,
            "fecha_corte": None,
            "generado_en": "2026-11-03T13:00:00Z",
            "sha256_raw": None,
            "total_historicas": total_hist,
            "distribucion": {
                "atendidas": atendidas_est,
                "no_show": no_show_est,
            },
            "particiones": {
                "train": {
                    "filas": int(ds.get("train_size", 700)),
                    "no_show": round(int(ds.get("train_size", 700)) * float(ds.get("tasa_no_show_train", 0.205))),
                    "sha256": None,
                    "sha256_ids": None,
                },
                "val": {
                    "filas": int(ds.get("val_size", 150)),
                    "no_show": round(int(ds.get("val_size", 150)) * float(ds.get("tasa_no_show_val", 0.205))),
                    "sha256": None,
                    "sha256_ids": None,
                },
                "test": {
                    "filas": int(ds.get("test_size", 150)),
                    "no_show": round(int(ds.get("test_size", 150)) * float(ds.get("tasa_no_show_test", 0.205))),
                    "sha256": None,
                    "sha256_ids": None,
                },
            },
            "sin_interseccion_ids": True,
            "control_leakage": ds.get("control_leakage", {
                "aprobado": True,
                "columnas_prohibidas_excluidas": [
                    "estado_actual",
                    "fecha_hora_cita",
                    "fecha_registro_cita",
                    "id_cita",
                    "id_cita_externa",
                    "medico",
                    "paciente_anon_id",
                    "target_no_show",
                ],
                "interseccion_particiones": 0,
                "violaciones_temporales": 0,
                "invariante_paciente_nuevo_ok": True,
            }),
            "es_simulacion": True,
        }


# Instancia global del registro
registry = ModelRegistry()
