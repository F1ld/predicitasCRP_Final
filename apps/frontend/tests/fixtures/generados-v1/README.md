# Fixtures sintéticos explícitos de diseño

Generados por `apps/ia/datasets/qa_bundle.py`; `manifest.json` conserva parámetros,
conteos y SHA-256. Solo QA, sin pacientes reales; fechas históricas congeladas.

- `ux45`: 45 filas válidas + 4 de rechazo intencional.
- `uxapi20` y `uxweb20`: 20 válidas + 4 rechazadas cada uno.

El runner cambia únicamente los prefijos de IDs para evitar colisiones entre
ejecuciones. Los CSV son UTF-8/CRLF, de 13 columnas, sin features/target extra;
no editarlos manualmente ni usarlos como seed de un entorno operacional.
