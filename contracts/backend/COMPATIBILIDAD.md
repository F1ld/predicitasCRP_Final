# API pública actual: política de conservación

Fuente congelada: `openapi.actual.v0.5.0.json`, SHA-256 y procedencia en `procedencia.json`. **55 operaciones** contrastadas con decoradores AST; inventario detallado con roles, bodies, parámetros y respuestas en `docs/migracion/fase-01/endpoints_actuales.json` y tabla legible `ENDPOINTS_ACTUALES.md`.

OpenAPI no codifica por sí solo el RBAC por rol ni todos los casos de error/descarga; se complementa con código y documentos. `/docs`, `/redoc`, `/openapi.json` y redirect Swagger son rutas técnicas de FastAPI fuera del conteo. `/health` público devuelve solo `{"estado":"ok"}`, no prueba actualmente conexión BD.

## Garantías a conservar en fase 2

- Login `application/x-www-form-urlencoded`, campos `username` y `password`; TokenOut con Bearer y expiración. JWT en `Authorization`, sesión frontend en `sessionStorage`, no migrar a cookies.
- Renovación, logout y cambio/restablecimiento de claves mantienen revocación/bloqueo. No copiar passwords reales a fixtures.
- Upload `multipart/form-data`, campo **`archivo`**; no establecer manualmente boundary desde UI. 2 MiB y 5.000 filas, UTF-8/BOM. Errores de validación por fila no convierten un fallo de SQL en éxito parcial garantizado.
- Mantener `limite`, `desplazamiento`, `total`, `items`, filtros y valores por defecto por ruta; no sustituir por page/page_size ni lista plana.
- Conservar 200/201/204 reales por endpoint (algunos POST legados devuelven 200). Snapshot guarda status declarados, no asumir REST idealizado.
- Error común `error.codigo`, `error.mensaje`, `error.campos`; 401 con `WWW-Authenticate: Bearer`. `campos` puede tener contenido en errores de negocio específicos, no solo VALIDACION.
- Check-in recibe `observacion`, pero DTO actual retorna solo `fecha_hora_check_in` e `id_usuario`; observación se audita. No añadirla por corregir un tipo frontend en fase 2.
- `/ia/*` PrediccionIAOut usa Decimal serializado a string, `es_simulacion` y rótulo. Detalle de Citas usa otro DTO con floats, `resultado_simulado` y `ya_existia`. Conservar ambos mapeos, no unificar por nombre parecido.
- Predicción individual admite tres estados activos; lote solo `RECIBIDA`, sin filtro de fecha efectivo. `forzar` permite recalcular ya existentes. Resumen de dataset hoy mezcla metadata y BD con fallback `or` a estimados; es deuda documentada, no garantía de conteo exacto.

## Alias que NO son intercambiables sin adaptación

| Rutas | Diferencia actual a preservar/documentar |
|---|---|
| `POST /ia/predecir/{id_cita}` y `POST /citas/{id_cita}/prediccion` | Mismo servicio, pero primera A/R/T y segunda A/R; alias Citas sin response_model declarado |
| `GET /cupos` y `/cupos-liberados` | Ambas paginadas; límites por defecto 20 y 50. Con `estado_cupo=None` llega sin filtro real aunque una descripción diga DISPONIBLE por defecto |
| `GET /cupos/{id}/candidatos` y `/cupos-liberados/{id}/candidatos` | Primera lista de candidatos, segunda `{cupo,total_compatibles,candidatos}` |
| `POST /intervenciones` y `/citas/{id}/intervenciones` | Nueva: consentimiento/catálogo/elegibilidad y 201. Legacy: omite esas validaciones, cambia PENDIENTE a ENVIADA y responde 200 |
| `POST /intervenciones/{id}/respuesta` y `PATCH /intervenciones/{id}` | POST registra respuesta sin cambiar cita; PATCH legado sí cambia cita y desactiva validación de transición de respuesta |
| `GET /reportes/rep-02` y `/reportes/intervenciones` | Alias actual pasa `_` a una función que espera `usuario` y omite `request`: incompatibilidad estática a corregir separadamente, no alias operativo certificado |
| `GET /reportes/rep-03` y `/reportes/reasignaciones` | Alias invoca misma función; preservar formato/filtros. `xlsx` actual NO es archivo OOXML real, ver descargas |

## Descargas y formularios

| Endpoint | Solicitud | Respuesta actual | Objetivo de estabilización, no aplicado |
|---|---|---|---|
| `/reportes/rep-02` | GET `formato=json/csv/xlsx`, filtros desde/hasta/especialidad/canal/riesgo | JSON, CSV BOM `text/csv` o Excel real vía `openpyxl`; nombre de responder; exportación audita | Mantener y comprobar bytes/MIME/filename |
| `/reportes/rep-03` | GET `formato=json/csv/xlsx`, filtros desde/hasta/especialidad/id_operador | JSON o bytes CSV con BOM; si xlsx cambia extensión y MIME a `application/vnd.ms-excel`, pero sigue siendo CSV | Corregir entrega separada a OOXML real con MIME `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, sin vender CSV como Excel |
| `/auth/login` | Form URL encoded | JSON TokenOut | Sin cambios |
| `/citas/importar` | Multipart `archivo` | JSON ResultadoImportacionOut | Sin cambios |
| `/usuarios/{id}/restablecer-acceso` | POST autenticado Admin | ClaveTemporalOut, clave una vez | Nunca almacenar respuesta en logs/evidencia pública |

El OpenAPI actual declara JSON en rutas que retornan `Response` para descargas; registrar la limitación, no regenerar baseline. El transporte frontend de blobs debe conservar Bearer, errores, protección de 401 tardío, nombre seguro y formatos; no pasarlo por una función que siempre interpreta JSON.

## Versiones y cambios

Cambios de ruta/verbo, quitar campos, volver obligatorio un opcional, cambiar roles, defaults, tipos string↔number, side effects o validaciones legacy son incompatibilidades salvo corrección explícitamente registrada. Para una corrección acotada conservar ruta cuando sea seguro, añadir prueba nueva y no atribuirla al movimiento. Retirada/endurecimiento de legacy necesita política de transición aprobada antes de aplicarse.

La API interna IA sí nace con v1, pero **no** convierte la API pública a `/api/v1`. Los errores IA nuevos se incorporan en fase 7 con pruebas del adaptador/UI; no están activos ahora.

En fase 7, `POST /ia/predecir-lote` admite hasta 500 citas elegibles para la
versión consultada. Si hay más, devuelve 422 `LOTE_IA_DEMASIADO_GRANDE` antes
de enviar fragmentos de inferencia o guardar predicciones. Con `forzar=true`
también cuentan las citas elegibles con predicción previa. Se mantiene 503
`MOTOR_IA_NO_DISPONIBLE` cuando falla el motor.
