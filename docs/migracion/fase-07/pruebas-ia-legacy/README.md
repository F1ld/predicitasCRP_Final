# Pruebas históricas del cliente IA anterior a v1

Se conservan los archivos originales para consulta. La suite activa usa el
puerto predictivo de fase 7 y el contrato interno v1. Las pruebas históricas
importaban `app.modules.ia.cliente`, que ya no existe. También prescribían
éxito parcial para lotes, mientras que el contrato vigente exige atomicidad.

La cobertura vigente se reparte entre `apps/backend/tests/test_motor_7b.py`,
`apps/backend/tests/test_ia_endpoints.py`, `docs/migracion/fase-07/test_motor_7a.py`
y las pruebas del servicio `apps/ia/tests`.
