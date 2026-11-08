"""Carga un artefacto interno confiable por hash y compatibilidad aprobados.

Joblib permite ejecutar código: el manifiesto versionado es parte del software
de confianza (legacy incluido o release fijada por hash administrativo), no un
archivo suministrado por una solicitud o por el modelo.
"""
from dataclasses import dataclass
import hashlib
from importlib.metadata import version
import io
import logging
from pathlib import Path
import sys
from typing import Literal

import joblib
from lightgbm import LGBMClassifier
from pydantic import Field
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from app.config import FEATURES_AUTORIZADAS, MANIFEST_PATH, MODEL_PATH, ROTULO_ETICO, APPROVAL_SHA256
from app.core.features import (
    FEATURES_ENTRADA_MODELO, CATEGORIAS_ESPECIALIDADES, CATEGORIAS_TIPOS_PACIENTE,
    CATEGORIAS_CANALES_ORIGEN, CATEGORIAS_FRANJAS_CITA, CATEGORIAS_DIAS_SEMANA,
)
from app.core.inference import ejecutar_inferencia_individual
from app.metadata import ClosedModel, DatasetLegacy, DatasetTraining, MetricasModelo
from app.schemas import FeaturesPreCita, ModelMetadata, Umbrales

logger = logging.getLogger("predicitas.ia.registry")


class Smoke(ClosedModel):
    features: FeaturesPreCita
    probabilidad_no_show: float
    nivel_riesgo: Literal["BAJO", "MEDIO", "ALTO"]
    explicabilidad_resumen: str


class Approval(ClosedModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    version_modelo: str
    version_features: Literal["pre-cita-v1"]
    python_major_minor: str
    libraries: dict[str, str]
    provenance: str
    dataset: DatasetLegacy | DatasetTraining
    smoke: Smoke


@dataclass(frozen=True)
class LoadedModel:
    pipeline: Pipeline
    metadata: ModelMetadata
    metrics: MetricasModelo
    dataset: DatasetLegacy | DatasetTraining


class ModelRegistry:
    def __init__(self):
        self._state: LoadedModel | None = None

    @property
    def is_ready(self):
        return self._state is not None

    @property
    def version_modelo(self):
        return self._state.metadata.version_modelo if self._state else None

    @property
    def pipeline(self):
        return self._state.pipeline if self._state else None

    def load_model(self, path: Path | None = None, *, manifest_path: Path = MANIFEST_PATH,
                   approval_sha256: str = APPROVAL_SHA256) -> bool:
        # Solo startup; sin endpoint de reload. Fallo -> no ready, nunca estado parcial.
        self._state = None
        try:
            approval_bytes = manifest_path.read_bytes()
            if approval_sha256 and hashlib.sha256(approval_bytes).hexdigest() != approval_sha256:
                raise ValueError("Aprobación no confiable")
            approval = Approval.model_validate_json(approval_bytes)
            if approval.python_major_minor != f"{sys.version_info.major}.{sys.version_info.minor}":
                raise ValueError("Python incompatible")
            if set(approval.libraries) != {"joblib", "lightgbm", "numpy", "scikit-learn", "scipy"}:
                raise ValueError("Compatibilidad de librerías incompleta")
            if any(version(name) != expected for name, expected in approval.libraries.items()):
                raise ValueError("Librerías incompatibles")
            # Leer una vez: validar y deserializar los mismos bytes (sin TOCTOU).
            content = (path or MODEL_PATH).read_bytes()
            if hashlib.sha256(content).hexdigest() != approval.sha256:
                raise ValueError("Hash no aprobado")
            artifact = joblib.load(io.BytesIO(content))
            if not isinstance(artifact, dict):
                raise ValueError("Formato incompatible")
            pipeline = artifact["pipeline"]
            if not isinstance(pipeline, Pipeline) or list(pipeline.named_steps) != ["prep", "clf"]:
                raise ValueError("Pipeline incompatible")
            if not isinstance(pipeline.named_steps["prep"], ColumnTransformer) or not isinstance(pipeline.named_steps["clf"], LGBMClassifier):
                raise ValueError("Clases incompatibles")
            if artifact["features_entrada"] != FEATURES_ENTRADA_MODELO or pipeline.n_features_in_ != 11:
                raise ValueError("Features incompatibles")
            encoder = pipeline.named_steps["prep"].named_transformers_["cat"].named_steps["ohe"]
            expected_categories = [CATEGORIAS_ESPECIALIDADES, CATEGORIAS_TIPOS_PACIENTE,
                CATEGORIAS_CANALES_ORIGEN, CATEGORIAS_FRANJAS_CITA, CATEGORIAS_DIAS_SEMANA]
            if [list(c) for c in encoder.categories_] != expected_categories:
                raise ValueError("Categorías incompatibles")
            if artifact["version_modelo"] != approval.version_modelo:
                raise ValueError("Versión incompatible")
            thresholds = Umbrales(medio=artifact["umbral_medio"], alto=artifact["umbral_alto"])
            ds = artifact["dataset_info"]
            dataset = approval.dataset
            if ds["version_dataset"] != dataset.version_dataset or ds["control_leakage"] != dataset.control_leakage.model_dump():
                raise ValueError("Metadata dataset incompatible")
            if ds["total_historicas"] != dataset.total_historicas or artifact["semilla"] != dataset.semilla:
                raise ValueError("Conteos incompatibles")
            if round(ds["total_historicas"] * ds["tasa_no_show_global"]) != dataset.distribucion.no_show:
                raise ValueError("Distribución incompatible")
            for name in ("train", "val", "test"):
                split = getattr(dataset.particiones, name)
                if ds[f"{name}_size"] != split.filas or round(split.filas * ds[f"tasa_no_show_{name}"]) != split.no_show:
                    raise ValueError("Partición incompatible")
            fields = ("algoritmo", "semilla", "fecha_entrenamiento", "es_simulacion", "metricas_test",
                "metricas_val", "metricas_baseline_test", "auditoria_equidad", "importancia_global_variables")
            metrics = MetricasModelo(version_modelo=approval.version_modelo, rotulo_etico=ROTULO_ETICO,
                umbral_medio=thresholds.medio, umbral_alto=thresholds.alto,
                cumple_meta_f1_82=artifact["metricas_test"]["f1_score"] >= 0.82,
                **{k: artifact[k] for k in fields})
            prob, level, _, explanation = ejecutar_inferencia_individual(pipeline, approval.smoke.features)
            if (prob, level, explanation) != (approval.smoke.probabilidad_no_show, approval.smoke.nivel_riesgo, approval.smoke.explicabilidad_resumen):
                raise ValueError("Smoke de inferencia incompatible")
            metadata = ModelMetadata(version_modelo=approval.version_modelo, version_dataset=dataset.version_dataset,
                umbrales=thresholds, features_autorizadas=FEATURES_AUTORIZADAS)
            self._state = LoadedModel(pipeline, metadata, metrics, dataset)
            return True
        except Exception as exc:
            # No revelar contenido del artefacto, rutas o secretos en el log.
            logger.error("Modelo no disponible (%s)", type(exc).__name__)
            return False

    def version_matches(self, requested_version):
        return self.is_ready and self.version_modelo == requested_version

    def _require(self):
        if self._state is None:
            raise RuntimeError("Modelo no cargado")
        return self._state

    def get_metadata(self):
        return self._require().metadata.model_copy(deep=True)

    def get_metrics_payload(self):
        return self._require().metrics.model_dump(mode="json")

    def get_dataset_manifest(self):
        return self._require().dataset.model_dump(mode="json")


registry = ModelRegistry()
