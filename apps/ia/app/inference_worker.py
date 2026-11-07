"""Worker privado de inferencia: sin HTTP, BD, entrenamiento ni escritura.

Protocolo: una línea JSON por solicitud y una por respuesta. El modelo se carga
una sola vez y se valida antes de atender. Un error de una solicitud responde
`status=error` para que el proceso padre descarte este worker y no publique
resultados parciales; no se reintenta ni se continúa con estado contaminado.
"""
from __future__ import annotations

import json
import sys

MAX_INPUT_BYTES = 512 * 1024


def _respond(payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    sys.stdout.buffer.write(data.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def _predict(model, request: dict) -> dict:
    version = request["version_modelo"]
    rows = request["features"]
    if not isinstance(version, str) or not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError("Solicitud interna inválida")
    if not model.version_matches(version):
        raise ValueError("Modelo incompatible")
    from app.core.inference import ejecutar_inferencia_individual
    from app.schemas import FeaturesPreCita
    items = []
    for row in rows:
        prob, level, snapshot, explanation = ejecutar_inferencia_individual(
            model.pipeline, FeaturesPreCita(**row)
        )
        items.append({
            "probabilidad_no_show": prob,
            "nivel_riesgo": level,
            "features_snapshot": snapshot.model_dump(mode="json"),
            "explicabilidad_resumen": explanation,
        })
    return {"status": "ok", "version_modelo": model.version_modelo, "items": items}


def main() -> int:
    from app.core.model_registry import ModelRegistry

    model = ModelRegistry()
    if not model.load_model():
        return 2
    for line in sys.stdin.buffer:
        if len(line) > MAX_INPUT_BYTES:
            _respond({"status": "error"})
            return 3
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Solicitud no es objeto")
            action = request.get("action")
            if action == "ping":
                _respond({"status": "ok", "version_modelo": model.version_modelo})
            elif action == "predict":
                _respond(_predict(model, request))
            else:
                raise ValueError("Acción no autorizada")
        except Exception:
            # Sin trazas ni datos en stdout/stderr; el padre descarta el worker.
            _respond({"status": "error"})
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
