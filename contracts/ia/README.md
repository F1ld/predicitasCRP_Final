# IA interna v1 — contrato objetivo para fases 5–7

`openapi.objetivo.v1.json` y schemas son una especificación **no implementada**. El backend actual sigue usando LightGBM en su propio proceso. La vieja prueba `tests/ia` hace referencia a otro simulador/contrato y no se declara compatible por compartir prefijo `/v1`.

## Endpoints, autenticación y versiones

Health live/ready sin clave y sin detalles sensibles; `/v1/model`, `/v1/metrics`, `/v1/dataset`, `/v1/predict`, `/v1/predict-batch` exigen `X-IA-API-Key`. Comparación segura de la clave, no registrar header. Clave ausente/inválida→401 interno, no invalida JWT del usuario en el backend.

Contrato `version_contrato="1.0"`, features `pre-cita-v1`, versión de modelo fijada por petición y manifiesto. UUID de solicitud y `id_item` opacos, no ID/nombre/teléfono de paciente. Backend mantiene mapping local hacia citas; IA no persiste nada. HTTP con Content-Type JSON y body ≤256 KiB.

Sin modelo compatible listo→503; pedido de versión distinta del activo→409; features/lote inválidos→422; exceso de bytes→413; inesperado→500 sin traceback. El body de error común está especificado, pero su código debe coincidir con el status de OpenAPI (no cualquier enum en cualquier error).

## Predicción y bordes

Modelo produce raw; preservar `round(max(0,min(1,raw)),3)` del pipeline actual Python. Clasificar el **valor redondeado**: 0/0.299 BAJO, 0.300 y 0.450 MEDIO, 0.451/1 ALTO. No devolver NaN/Infinity. Empates de redondeo siguen Python del entorno acreditado; no cambiar a redondeo decimal half-up sin nueva versión/paridad.

Manifiesto es fuente única de cortes; el perfil v1 de extracción los restringe a 0.300/0.450. Esquemas y manifest deben coincidir. `IA_CORTE_MEDIO` no puede competir con ese perfil; validar igualdad o deprecar en fase 7. Schema no entrena ni calibra.

Respuesta devuelve features efectivas y explicación ≤255 caracteres. Backend valida tipos, rangos, fórmulas, versión, correlación, snapshot idéntico a entradas crudas y coherencia nivel/probabilidad. No se incluye `target`, estado o datos de contacto en ninguna entrada.

El contrato interno usa número JSON; al adaptar a API pública se conservan strings Decimal de PrediccionIAOut y floats de la proyección Citas actual. No añadir campos obligatorios a consumidores existentes.

## Lotes y errores públicos

- Lote interno: 1..100 elementos, IDs únicos, todos válidos o error. No admite respuestas parciales exitosas.
- Respuesta debe cubrir exactamente los IDs pedidos; puede reordenarlos, backend correlaciona por ID, no por índice.
- La versión y UUID global coinciden en todos los resultados. Metadatos se consultan antes y se fija versión; cambio de activo a mitad devuelve conflicto, no mezcla modelos.
- Backend fragmenta el lote público conservando su selección actual (RECIBIDA; `forzar` preservado), calcula todo fuera de transacción larga y guarda todo al final en transacción corta tras revalidar snapshots. Mantener atomicidad; no introducir jobs ni un límite de cantidad pública nuevo sin contrato aprobado.
- Defaults operativos definidos en ADR-007: connect 1 s, read/write 5 s, pool 1 s, presupuesto público total 60 s; sin retry automático. Probar/medir en fase 7 y permitir configuración sin cambiar semántica.
- Repetir solicitud no promete una deduplicación de auditoría que hoy no existe. La correlación no es una llave de idempotencia persistente.

| Situación integración | Backend futuro hacia frontend |
|---|---|
| IA desconectada/modelo no listo | 503 MOTOR_IA_NO_DISPONIBLE |
| Timeout | 504 IA_TIMEOUT |
| Respuesta/versión inválida o clave interna rechazada | 502 IA_RESPUESTA_INVALIDA, detalle técnico solo en log seguro |
| Cita cambió durante inferencia | 409 PREDICCION_DESACTUALIZADA |

No guardar BAJO/0 como fallback, no borrar predicción anterior y no cancelar/liberar citas. Login/consulta/atención siguen operativos con IA caída. El catch-all frontend que reintenta por alias se debe revisar antes de este corte: puede duplicar llamadas o disfrazar 401/timeout, y los roles del alias no coinciden.

## Metadata, dataset y artefactos

- `/v1/model`: versión activa, features autorizadas, dataset, cortes y rótulo, sin rutas de disco/credenciales.
- `/v1/metrics`: payload compatible con MetricasModeloOut del snapshot backend; se obtiene de artefacto/reportes, sin conexión DB.
- `/v1/dataset`: manifiesto de entrenamiento o legacy explícito; nunca conteos operativos. Backend obtiene esos conteos de PostgreSQL y proyecta DatasetResumenOut. No usar `or` para sustituir un conteo real de cero por una estimación en una corrección futura.
- `active-model.v1.schema.json`: puntero de promoción atómica a manifiesto aprobado. El schema comprueba forma; proceso de fase 6 verifica ruta confinada, SHA-256 real, procedencia y compatibilidad antes de cargar Joblib.
- Serving solo lee; entrenamiento CLI escribe candidatos y métricas, sin endpoint HTTP. No existe aún un CLI nuevo en esta entrega.
- Legacy con linaje incompleto se mantiene explícito y solo puede aprobarse para piloto sintético tras paridad; un fixture nunca puede ser aprobado como modelo real. No convertir hashes desconocidos en ceros fingiendo evidencia.

Pruebas de contrato: los fixtures verifican forma y algunos invariantes. No certifican rendimiento, servicio HTTP, seguridad de red, calidad clínica ni promoción de archivos reales.
