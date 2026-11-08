"""Puerto integrado transitorio, estable hasta extracción IA; no expone ORM."""
from app.modules.ia.service import predecir_cita, listar_predicciones_cita
from app.modules.ia.schemas import PrediccionIAOut
from app.modules.ia.dependencias import obtener_motor
from app.modules.ia.puerto import MotorPredictivo
