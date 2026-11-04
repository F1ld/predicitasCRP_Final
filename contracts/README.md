# Contratos de PrediCitas

Dos estados deliberadamente distintos:

- **Actual congelado:** `backend/openapi.actual.v0.5.0.json`, copia byte a byte de fase 0. Describe la API pública existente; no corrige limitaciones ni acredita todas las respuestas de ejecución.
- **Objetivo no implementado:** schemas de `data/` y API interna de `ia/`. Son especificaciones para fases 3–7, no servicios disponibles hoy. Ninguna aplicación los consume todavía.

Los identificadores `https://predicitas.invalid/contracts/...` son IDs lógicos para resolver referencias **offline**, no URLs que se deban descargar. JSON Schema usa draft 2020-12; el OpenAPI objetivo usa 3.1.0.

Reglas humanas complementarias: [datos](data/README.md), [IA](ia/README.md) y [compatibilidad pública](backend/COMPATIBILIDAD.md). Algunos invariantes entre campos/filas y entre petición/respuesta requieren validación semántica además del schema.

Los ejemplos están en `examples/casos.json`: incluyen válidos, inválidos estructurales e inválidos semánticos. Son sintéticos y **ninguno** debe promocionarse como dataset/modelo entrenado. Los manifiestos hipotéticos usan `CONTRACT_FIXTURE`/`CANDIDATO`; otros casos prueban la forma de `LEGACY_IMPORT` y su rechazo cuando inventa linaje. Sus hashes ilustrativos no acreditan archivos reales; todo el documento declara `not_training_evidence=true`.

Verificar con `docs/migracion/fase-01/validar_contratos.py` en un entorno de herramientas aislado con `jsonschema==4.25.1` y soporte de formatos `date-time`/`uuid` instalado. No añadir esa dependencia al runtime de las aplicaciones por esta tarea.
