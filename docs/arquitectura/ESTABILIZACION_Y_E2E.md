# Estabilización separada y recorrido de aceptación

Fase 1 define estos trabajos; **no los implementa**. Los resultados medidos siguen siendo los de fase 0. No hay una certificación funcional nueva por validar schemas.

## Entregas de estabilización, fuera de la mudanza

| ID | Hallazgo | Decisión/resultado esperado | Gate |
|---|---|---|---|
| S-01 | Siete diagnósticos TypeScript bloquean typecheck/build/lint | Entrega mínima de typing/config: imports TS, tipo Vite/Vitest, import sin uso, mapas de estados bien tipados y no leer `observacion` de CheckInOut que backend no devuelve. No inventar campos API ni rediseñar UI | **Antes de cerrar fase 2**; preferible antes de mover archivos |
| S-02 | Suite backend no colecta `tests/ia` por cliente/reloj/simulador inexistentes | Reconciliar pruebas de motor externo con puerto/contrato objetivo; mantener cobertura de fallos/elegibilidad. No crear stub engañoso ni borrar carpeta para declarar verde | Antes de aceptar corte IA fase 7; registrar diagnóstico parcial en fase 2 |
| S-03 | Test reasignación itera JSON paginado como lista | Ajustar expectativas al contrato vigente `items`, conservando prueba completa de asignación, incompatibilidades y confirmación humana | Antes de aceptación funcional de fase 4/10 |
| S-04 | 56 fallos frontend en Detalle y citas | Clasificar expectativas obsoletas versus regresión real; comparar UI/contratos, mantener cobertura. No actualizar snapshots para ocultar funciones perdidas | Antes de cierre funcional fase 8/10; nuevos fallos bloquean fase 2 |
| S-05 | Alias `/reportes/intervenciones` pasa kwargs incompatibles; deducido estáticamente | Prueba de reproducción independiente, luego delegación correcta a caso de uso manteniendo URL/filtros/roles. No presentarlo como alias sano en pruebas de fase 2 | Antes de certificar alias/reportes fase 10 |
| S-06 | REP-03 `xlsx` es CSV con otra extensión/MIME | Generar OOXML real, verificar firma ZIP/lectura openpyxl y MIME correcto, mismos filtros/roles; entrega separada | Antes de certificar exportación Excel fase 10 |
| S-07 | Legacy de intervención omite validaciones; reglas documentales de contactos divergen de ejecución | Piloto sintético local mantiene baseline temporal. Antes de uso real, acordar/versionar endurecimiento de legacy y límite; consent/opt-out nunca se eliminan del flujo nuevo | **Bloquea cualquier uso real**, no es un detalle de carpetas |
| S-08 | Routers ofrecen/rechazan sin workflow/auditoría coherente; historial_ofertas del detalle vacío | Casos de uso con locks, estados y eventos; detalle/historial consistentes sin crear tabla arbitraria por esta fase | Fase 4; comprobar E2E oferta/rechazo/desistimiento |
| S-09 | Catch-all Detalle reintenta IA por alias ante cualquier error | Mantener endpoints; restringir fallback a incompatibilidad de ruta identificada, no 401/403/timeout/503; evitar doble petición y borrado de error original | Antes de conexión HTTP fase 7/8 |
| S-10 | DatasetResumen usa `conteo_bd or estimado`, cero real puede ser sustituido | Separar procedencia y usar fallback solo ante falta explícita; preservación de DTO y prueba de BD con cero | Corrección separada durante integración, no fase 2 |
| S-11 | Nueve advisories moderados npm; transitivos Python no fijados; Node host 24 vs referencia 22 | Revisar advisories y lock reproducible por aplicación en entrega de dependencias, probar Node 22. No ejecutar audit fix/upgrade masivo por reorganización | Antes de declarar entorno endurecido; sin bloquear inventario ya hecho |
| S-12 | Comparación de fechas calendario acepta registro posterior intradía; filtros inválidos a veces se ignoran | Conservar baseline en fase 2. Si se endurece, especificar respuesta, UI y datos afectados en entrega de reglas, con fixtures antes/después | No cambiar silenciosamente en mudanza |
| S-13 | Linaje raw del artefacto puede no estar disponible | Importar metadata legacy explícita sin hashes inventados; nueva ejecución de entrenamiento debe tener archivos/hashes y otra versión si cambia modelo | Aprobación de registry fase 6 |

Estas tareas no autorizan cambios de producción por estar descritas. Al pedir la próxima entrega se debe indicar si será estabilización mínima S-01 o fase 2 mecánica. Si se mueve primero, la fase 2 puede quedar EN CURSO, pero no COMPLETADA mientras el gate de build siga rojo.

## Qué se comprobó frente a qué solo se especifica

- Fase 0 comprobó recuperación de CRP, integridad originales, instalación, smoke por roles y navegación Recepción. Backend completo bloqueado; diagnóstico 218/1 y 87,12% cobertura. Frontend 451/56, sin build aprobado.
- Fase 1 valida contratos/fixtures e inventarios estáticos, no ejecuta toda la suite ni el recorrido multímódulo completo.
- El servicio IA externo, healthchecks nuevos, registry, pipeline y bootstrap objetivo aún no existen. Su fallo/success no puede presentarse como prueba pasada.
- Hay código de reportes REP-02/03, métricas IA y auditoría persistida; no hay pantalla modular IA dedicada, `/panel`, REP-01 o endpoint dedicado de consulta REP-05 en los routers registrados. No crear esas funcionalidades como requisito implícito de mover carpetas.
- Las plantillas tienen contenido placeholder y los canales son simulados. No se envió ni se probará mensajería real como parte de esta migración.

## Recorrido E2E a ejecutar posteriormente, en entorno aislado

Referencia temporal controlada en Lima y usuarios desechables por rol. No usar principal para pruebas de escritura ni fechas fijas antiguas como si siempre fueran futuras.

1. **Arranque/adopción:** preflight confirma `predicitas-crp_pgdata` o copia explícita, migrador en head sin cambios inesperados, no seed por defecto. Comparar conteos/IDs/constraints y revisión antes/después.
2. **Sesión/RBAC:** login de tres roles, renovación/logout/expiración/inactivo/bloqueo. Sin token→401, rol incorrecto→403; menú oculto no sustituye permiso HTTP. Probar sesión nueva ante 401 atrasado.
3. **Incorporación:** importar CSV válido/mixto en BD de prueba, BOM/celdas vacías/duplicados/límites; verificar aceptación/rechazo parcial, estado, target e historial. Registrar manualmente cita externa y comprobar unicidad.
4. **Seguimiento:** filtros/paginación, detalle y trazabilidad; transiciones legales/ilegales, reprogramación y aumento de contador. Check-in solo día/estado válido; no permite NO_SHOW tras llegada. Observación persiste según auditoría, no atribuirla al DTO que no la devuelve.
5. **IA:** individual para estados elegibles y lote de RECIBIDA con/sin forzar; fixtures congelados dan probabilidades/niveles comparables; snapshot/versión/explicación y evento guardados. Cita cambia durante HTTP→conflicto sin resultado obsoleto.
6. **Intervención nueva:** cita futura de riesgo MEDIO/ALTO, consentimiento true, plantilla/canal válidos, límites/opt-out. PENDIENTE→ENVIADA→ENTREGADA→respuesta según canal; confirmar cita por operación explícita. SIN_RESPUESTA no modifica cita ni crea cupo.
7. **Liberación:** respuesta voluntaria y operador liberan cita/cupo una sola vez; probar doble envío concurrente y rollback después de flush. Cancelación externa con `liberar_cupo` es otro origen, no decisión automática de IA.
8. **Reasignación:** alta/listado candidato, especialidad/franja compatibles, prioridad numérica/exacta/FIFO; oferta→rechazo/desistimiento/liberación según caso de uso, luego confirmación humana. Dos asignaciones simultáneas dejan una sola efectiva, no doble cupo ocupado.
9. **Reportes:** filtros/roles y JSON/CSV/Excel reales, nombre seguro y mismos datos; aliases verificados tras su corrección explícita. Probar auditabilidad de exportaciones y no exponer claves temporales.
10. **Resiliencia IA:** parar solo servicio IA de prueba: login, lectura, confirmación y atención siguen; 503/504/502 apropiados, predicción previa intacta y sin score ficticio. Volver IA y predecir sin resetear BD.
11. **Reinicio/retorno:** reiniciar stack, verificar persistencia/volumen; rollback de artefacto y recuperación aislada sin `down -v`. Detener laboratorios y guardar evidencia sin secretos.

Cada paso requiere evidencia y estado PASÓ/FALLÓ/NO EJECUTADO, no un checkbox heredado del diseño. E2E no significa probar todas las rutas legacy como si tuvieran las mismas validaciones: esas diferencias tienen pruebas de caracterización propias.

## Gate de fase 2

- Contratos y decisiones de fase 1 congelados, respaldo disponible y principal confirmado.
- Sin movimiento en esta entrega. Fase 2 tendrá diff mecánico separado de S-01 u otra corrección.
- Preservar lista de fallos conocidos; no introducir errores nuevos en importación/arranque/smoke, conteos, rutas, contratos o permisos.
- Build/typecheck/lint deben completar para cerrar fase 2; si falla el mismo baseline, registrar bloqueada/en curso y solicitar entrega S-01, no dar por satisfecho el criterio.
- Sin schema DB nuevo, sin reentrenar y sin extraer IA en fase 2. Revisiones Alembic/modelo/CSV/Skills intactos.
- Si contratos o datos difieren de baseline por trabajo paralelo, detener mudanza y revisar; no descartar trabajo del usuario.
