# 7B — cableado conservador del puerto (EN VALIDACIÓN)

Subentrega de la fase 7, no fase nueva. Autorizada por el usuario con exigencia
de preservar el sistema. Retorno Git `3700c5f`; se conserva el trabajo 7A previo
sin commit. No se realiza ningún commit automático de esta entrega.

## Alcance

- Servicios de predicción individual/lote, alias Citas y metadata consumen el
  puerto. Routers mantienen roles, métodos, rutas y esquemas públicos.
- `IA_MOTOR=integrado` por defecto. `IA_MOTOR=http` es opt-in explícito; usa
  `IA_URL` y `IA_API_KEY`, sin JWT de usuario ni fallback silencioso.
- Lifespan FastAPI crea/cierra un único cliente por aplicación. No consulta IA
  al arrancar: una IA caída no impide `/health` ni las operaciones no predictivas.
- Métricas y dataset remotos se validan y normalizan al formato público vigente.
  El rótulo interno validado RF-056 se presenta con el rótulo histórico
  RF-056 / RN16 de métricas/dataset; no se cambian esquemas ni contratos.
  Se conservan las 11 features públicas, incluidas las dos derivadas.
- Predicción: snapshot backend → fin de lectura → llamada al motor → locks por
  PK y revalidación → persistencia/auditoría en una transacción corta. El lote
  valida todas las respuestas antes de escribir; un fallo revierte todo.
- Serialización de escrituras por cita con `FOR UPDATE`; no altera el índice
  existente `(id_cita, version_modelo)`. No se borran predicciones previas ante
  fallo. Se conservan los códigos 503/409 de 7A y formato de error vigente.

## Configuración (solo para activación explícita futura)

| Variable | Por defecto |
|---|---|
| `IA_MOTOR` | `integrado` |
| `IA_URL` | `http://ia:8100` (existente) |
| `IA_API_KEY` | Sin clave por defecto |
| `IA_CONNECT_SEGUNDOS` | 2 |
| `IA_READ_SEGUNDOS` | 15 |
| `IA_WRITE_SEGUNDOS` | 5 |
| `IA_POOL_SEGUNDOS` | 2 |
| `IA_PRESUPUESTO_SEGUNDOS` | 60 |

Los plazos deben ser positivos y finitos. Se conservan los ajustes antiguos
`IA_TIMEOUT_SEGUNDOS`/`IA_CORTE_MEDIO` por compatibilidad, pero el adaptador v1
usa los plazos separados y umbrales congelados del contrato, no esos ajustes.
No se edita `.env` ni Compose; el stack existente no recibe activación HTTP.
Estas variables deben entregarse explícitamente al proceso que se quiera probar.

## Pruebas previstas y límites

```powershell
python -B docs/migracion/fase-07/test_motor_7a.py
python -B docs/migracion/fase-07/test_metadata_7b.py
python -B docs/migracion/fase-07/validar_7b.py --nombre <nombre-nuevo>
```

El runner construye una imagen backend nueva, crea red interna/volumen/BD
**nuevos**, ejecuta migraciones solo allí y usa el rol app para las pruebas.
IA real usa imagen E por ID, modelo RO y clave efímera. No publica puertos ni
arranca Compose. Credenciales locales en Temp con ACL restringida, no evidencia
pública. Solo detiene sus dos contenedores; preserva red/volumen y evidencia.

Pruebas focales: dobles del puerto en ambos routers, lote/forzar, fallos y
rollback tras flush, snapshot obsoleto, metadata, startup sin IA y cierre del
cliente; HTTP IA real con persistencia/auditoría y paridad de metadata legacy.
Pruebas independientes: doble petición concurrente, cambios confirmados desde
otra sesión y observación del rollback desde otra conexión.

No se retira predictor/generador ni dependencias ML. La cobertura de metadata
training incluye validación sintética del contrato, no promoción/despliegue de
una release nueva. No se certifican suite completa, navegador ni corte final.
La colección conserva los problemas históricos que se reporten en evidencia;
no se corrigen ni se ocultan por excluirlos del diagnóstico empaquetado.

Los servicios de inferencia son casos de uso top-level con sesión propia de
petición, no operaciones componibles dentro de otra transacción de negocio.
Se rechazan cambios ORM pendientes antes de iniciar la operación; no se deben
invocar con escrituras ajenas ya flusheadas sin confirmar. La lectura se cierra
con rollback (no con commit de cambios ajenos). Los DTOs de identidad/snapshot
no dependen de la sesión ORM después de ese cierre.

Pendientes de fase 7: retirada tras paridad/regresión ampliadas, medición del
límite de lote público, trazabilidad frontend-backend-IA y revisión explícita
de errores 502/504 sugeridos por el plan. No se cambian códigos públicos en este
bloque conservador sin una revisión de sus consumidores UI.

## Cierre de validación (08/11/2026)

Ejecución aceptada `7b-20261108-01` sobre `4832f36`, con imagen backend nueva,
PostgreSQL nuevo en red interna e IA real. Pasaron 5 pruebas unitarias de
metadata, 19 del puerto, 15 focales y 354 de regresión empaquetada. Los
controles independientes observaron una sola predicción ante dos solicitudes
para la misma fila, el rechazo ante cambios de datos o cierre de cita desde
otra sesión y el rollback tras flush.

La colección completa registró dos errores históricos: falta
`app.modules.ia.cliente` en `tests/ia` y el verificador de evidencia de fase 3
falla en la imagen empaquetada. El resumen identifica las exclusiones de la
regresión. El runner emitió una etiqueta histórica de baseline que se conserva
por separado del commit efectivamente probado.

El runner verificó los hashes de los archivos protegidos y el conjunto de
contenedores activos. Se detuvieron los contenedores del laboratorio y se
preservaron sus recursos. El motor integrado sigue por defecto. La fase 7
continúa abierta para la paridad y regresión ampliadas previas al retiro.

[Resumen de evidencia](evidencia/7b-20261108-01/resumen.json).
