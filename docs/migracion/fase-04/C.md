# Bloque C — Routers, ofertas y estabilización S-03/S-08

## Criterios y decisiones congelados antes de validar

Baseline explícito: `6da1c49` (entrega B.1). Implementación y pruebas registradas antes de validar; resultados en commit separado. No se inicia D ni fase 5.

1. Routers sin imports de modelos/repositorios, SQL, `db.get`, commits ni mutaciones ORM. Mantener rutas, operationIds, esquemas, roles y formatos HTTP. Consultas y paginación pasan a servicios sin rediseñar sus reglas de fecha (S-12 sigue pendiente).
2. S-08: mover oferta/rechazo/desistimiento a casos de uso propios, con locks cupo → candidato y un solo commit. Validar estados, especialidad/franja y no reemplazar una oferta vigente ni asignar simultáneamente dos ofertas abiertas al mismo candidato. La certificación de carreras concurrentes sigue en D.
3. Registrar `OFERTAR`, `RECHAZAR`, `DESISTIR` y cierre por `REASIGNADO` en auditoría existente, sin tabla nueva. Cada cierre referencia el ID exacto de su oferta. Proyectar `oferta_vigente` e `historial_ofertas` sin modificar bitácora ni datos históricos.
4. El endpoint histórico `/ofertas/desistimiento` representa cierre por `SIN_RESPUESTA`, no baja global del candidato. Rechazo/sin respuesta devuelven cupo a DISPONIBLE y candidato CONTACTADO a ACTIVO; no reactivar ASIGNADO/DESISTIDO. La baja global continúa por PATCH de lista de espera. Los JSON/URLs existentes no cambian; no se añaden alias frontend de otra fase.
5. Si EN_OFERTA legacy no tiene evento con candidato identificable, no adivinar identidad ni fabricar historial: su cierre automático responde 409 `OFERTA_NO_REGISTRADA` y requiere revisión. Reasignación humana explícita sin oferta registrada conserva el camino existente. No ejecutar reparación masiva.
6. Una oferta trazable se reasigna al candidato ofertado, con confirmación humana; cierre y evento de asignación comparten transacción. La reasignación directa desde DISPONIBLE sigue admitida, con el matching existente.
7. S-03: corregir lectura del objeto paginado (`items`) y mantener prueba completa de matching, prioridades, franja, confirmación humana y doble asignación. La expectativa antigua 422 también era incorrecta: caracterizar el **400 SOLICITUD_INVALIDA** vigente para confirmación falsa, sin cambiar el servicio y comprobando ausencia de escrituras. Fijar reloj de la prueba.
8. REP-02: trasladar validación/auditoría/commit al caso de uso, mantener serialización HTTP. Corregir el forwarding del alias `/reportes/intervenciones` (S-05), reproduciendo primero su TypeError en baseline; pruebas de igualdad JSON/CSV/OOXML y permisos. No corregir S-06 (REP-03 xlsx) ni cambiar IA/modelo.
9. PostgreSQL nuevo aislado: recorridos de ofertas/cierres/asignación, permisos, casos negativos y rollback tras flush de estados/eventos; comprobar oferta/cierre/exportación desde conexiones independientes. Preservar .env, CSV, modelos, dependencias y revisiones. No arrancar el stack principal ni laboratorios previos.
10. OpenAPI/DDL/modelo/predicciones idénticos. Diagnóstico sin tests/ia debe pasar: el único cambio permitido entre casos anteriores es S-03 failure → passed; todos los nuevos aprobados. Suite completa conserva S-02 de colección y no se declara verde. Cobertura ≥75 %, frontend no reejecutado.

## Ejecución

La imagen de dependencias de fase 3 se usa por su ID inmutable con fuentes RO. No equivale al nuevo build empaquetado final de fase 4 (D).

```powershell
python -B docs/migracion/fase-04/validar.py preparar --scope C --baseline-ref 6da1c49 --run-id bloque-c-20261106-01
python -B docs/migracion/fase-04/validar.py baseline --run-id bloque-c-20261106-01
python -B docs/migracion/fase-04/validar.py actual --run-id bloque-c-20261106-01
python -B docs/migracion/fase-04/validar.py detener --run-id bloque-c-20261106-01
python -B docs/migracion/fase-04/validar.py resumen --run-id bloque-c-20261106-01
python -B docs/migracion/fase-04/publicar.py --run-id bloque-c-20261106-01
```

Nuevo run-id ante fallo; nunca sobrescribir evidencia. Detener solo el laboratorio identificado por su JSON, incluso si una prueba falla. Conservar volúmenes y datos QA sintéticos. No ejecutar seed, limpieza ni restauración del principal.

`caracterizar_baseline_c.py` reproduce S-05 y el rechazo 400 sin conectar a BD; `probar_rollback_c.py` comprueba desde otra conexión los efectos de fallos tras flush. El error de acceso inicial al motor Docker no fue una ejecución de pytest. El usuario autorizó iniciar Docker; se comprobó que todos los contenedores anteriores permanecían detenidos.

La verificación pública de integridad, sin repetir suites ni requerir secretos, es:

```powershell
python -B docs/migracion/fase-04/publicar.py --run-id bloque-c-20261106-01 --verify-only
```
