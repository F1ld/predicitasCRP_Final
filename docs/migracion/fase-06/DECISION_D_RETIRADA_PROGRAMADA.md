# Decisión aprobada — cierre D como retirada programada

**Fecha: 07/11/2026. Aprobación explícita del usuario** a la propuesta de
migrar exportador/pruebas, conservar temporalmente el generador para el predictor
integrado y su reexport, validar/documentar esa excepción y después pasar a E.

**Actualización:** las cinco migraciones ya se implementaron y validaron;
[D completada como retirada programada](MIGRACIONES_D.md). La decisión se
mantiene: no eliminar físicamente antes de fase 7 y no iniciar 7 antes de E y
del cierre de fase 6. El estado «tras registrar la decisión» de abajo es histórico.

## Decisión

- El cierre de D en fase 6 se evaluará como **retirada programada**, no como
  eliminación física total del generador legacy.
- Se permite conservar temporalmente únicamente los usos del predictor integrado
  y su reexport en `citas.public` hasta sustituirlos con paridad y regresión en 7.
- La implementación duplicada permanece congelada por hash; no se autoriza
  introducir divergencias, consumidores nuevos ni fallback en la nueva IA.
- El exportador y los cuatro consumidores de pruebas/QA deben migrar primero
  a generación canónica IA y datos explícitos. La excepción no los incluye.
- El cierre requiere evidencia de que esa migración preserva contratos de datos,
  casos inválidos, rendimiento y cobertura. No basta actualizar la política.
- La eliminación física se hará en fase 7 después de retirar consumidores y
  comprobar los gates originales. Esta aprobación **no autoriza borrarla ahora**.

## Secuencia obligatoria antes de fase 7

1. Completar las cinco migraciones pendientes de D:
   - `apps/backend/scripts/exportar_csv.py`.
   - `apps/backend/tests/citas/test_citas.py`.
   - `apps/backend/tests/citas/test_m02_contrato.py` (mantener caso de 5000 filas).
   - `apps/backend/tests/test_ia_predictor.py` (fixture explícito, sin sustituir aún el motor).
   - `apps/frontend/tests/validar_diseno.py` (mantener flujos UI/API y filas de rechazo).
2. Revisar política e inventario tras las migraciones: solo las dos excepciones
   aprobadas pueden quedar. Registrar regresiones y cerrar D como programado.
3. Ejecutar **E** en aislamiento: generar → validar → entrenar → promover →
   importar seed → comprobar serving; repetición, rollback y camino existente
   preservado, con evidencias y límites reales.
4. Cerrar fase 6 solo si sus criterios se cumplen. **Fase 7 permanece PENDIENTE**
   hasta entonces; esta actualización no la inicia ni sustituye sus pruebas.

## Estado tras registrar la decisión (histórico, previo a las migraciones)

El bloqueo conceptual de secuencia quedó resuelto, pero **D sigue EN CURSO**:
persisten las cinco migraciones y E no se ha ejecutado. No se cambia el estado de
ningún requisito a completado por la aprobación administrativa.

La guarda `--exigir-cierre-programado` devuelve 2 mientras falte una migración;
`--exigir-retiro` sigue devolviendo 2 mientras haya dependencias. Son condiciones
esperadas, no errores del sistema. La política separa ambas aprobaciones para
evitar que aprobar una excepción temporal habilite eliminar código.

La fuente snapshot BD sigue deshabilitada; habilitarla requeriría exportación
autorizada y trazabilidad. No se incorporan datos reales ni credenciales BD a IA.
No se toca BD existente, esquema, claves, modelo activo ni conexión del backend.

Validación de esta actualización: [evidencia D-02](evidencia/bloque-d-20261107-02/resumen.json),
19/19 autopruebas y comprobaciones A/B/C intactas. No equivale a ejecutar las
migraciones o E ni a una regresión nueva completa de backend/frontend.
