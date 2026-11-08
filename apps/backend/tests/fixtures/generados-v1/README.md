# Fixtures sintéticos explícitos de backend

Generados por `apps/ia/datasets/qa_bundle.py`; parámetros, conteos y hashes en
`manifest.json`. No contienen pacientes reales. No son un seed operacional.

- `citas`: 40 válidas + 4 rechazos intencionales.
- `rendimiento`: 5000 históricos para el test de listado, no entrenamiento IA.
- `predictor`: 1000 históricos + 80 próximos para comprobación de coherencia.
- `muestra*`: ejemplos de exportación con cuatro inválidas intencionales.

CSV de 13 columnas, UTF-8/CRLF; no modificar manualmente. Los valores derivados y
target los calcula el backend cuando corresponda. No importar el generador desde
los tests: preparar datos explícitos en el entorno aislado IA y revisar paridad.
