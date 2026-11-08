"""Adaptador temporal por defecto; imports ML solo al invocar operaciones."""
from app.core.errores import Conflicto
from app.modules.ia.puerto import FeaturesMotor, ResultadoMotor
from app.modules.ia.metadata_motor import DatosDatasetMotor
from app.modules.ia.schemas import MetricasModeloOut


class MotorIntegrado:
    def version(self) -> str:
        from app.modules.ia.predictor import obtener_artefacto_modelo
        return obtener_artefacto_modelo()["version_modelo"]

    def predecir(self, features: FeaturesMotor, *, version: str) -> ResultadoMotor:
        from app.modules.ia.predictor import predecir_cita_dict
        if self.version() != version:
            raise Conflicto("La versión del motor cambió", codigo="VERSION_MODELO_INCOMPATIBLE")
        result = ResultadoMotor.model_validate(predecir_cita_dict(features.model_dump()))
        if result.version_modelo != version:
            raise Conflicto("La versión del motor cambió", codigo="VERSION_MODELO_INCOMPATIBLE")
        return result

    def predecir_lote(self, features: list[FeaturesMotor], *, version: str) -> list[ResultadoMotor]:
        return [self.predecir(item, version=version) for item in features]

    def close(self) -> None:
        pass

    def metricas(self) -> MetricasModeloOut:
        from app.modules.ia.predictor import obtener_artefacto_modelo
        artifact = obtener_artefacto_modelo()
        fields = set(MetricasModeloOut.model_fields) - {"cumple_meta_f1_82"}
        return MetricasModeloOut(**{k: artifact[k] for k in fields},
            cumple_meta_f1_82=bool(artifact["metricas_test"]["f1_score"] >= 0.82))

    def dataset(self) -> DatosDatasetMotor:
        from app.modules.ia.predictor import obtener_artefacto_modelo
        artifact = obtener_artefacto_modelo()
        return DatosDatasetMotor(**artifact["dataset_info"], rotulo_etico=artifact["rotulo_etico"])
