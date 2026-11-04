# Fase 0 — Inventario, respaldos y línea base

**Estado: COMPLETADA en alcance de fase 0.** Ver [cierre técnico](CIERRE_FASE_0.md). La aplicación conserva fallos previos documentados; esto no autoriza saltar los contratos y validaciones de fase 1 para empezar a mover archivos.

Fecha de ejecución: 3 de noviembre de 2026, zona local de Windows `-05:00`. Identificador: `predicitas-fase0-20261103-2200` (etiqueta de la ejecución, no hora exacta de todas las operaciones).

## 1. Qué se retomó y qué se preservó

El agente anterior creó un repositorio raíz y el snapshot `69c686f21fd1938dc76d679f4c6b33270f10a6d7`. Al retomar, Git estaba limpio, no había repositorios internos ni worktrees adicionales y el plan seguía marcando fase 0 pendiente. No había una bitácora de ejecución ni respaldos verificables en el directorio temporal aprobado.

Se conservó ese snapshot sin hacer commits, resets, borrados o cambios de historial. Se añadieron exclusivamente estas evidencias/helpers y se actualizó el plan. **No se modificaron código funcional, CSV, modelo, `.env`, Compose, dependencias, migraciones o pruebas originales.**

Docker Desktop estaba apagado; se solicitó su inicio. No había contenedores del proyecto en ejecución ni listeners originales en 5173/8000/8100/5432/5433 al inspeccionar. Se trabajó sobre copias aisladas, no se levantó el Compose original ni se ejecutó su seed.

## 2. Inventario y diferencia entre bases

| Volumen original | Citas | Usuarios | Predicciones | Historial | Auditoría | Lista de espera |
|---|---:|---:|---:|---:|---:|---:|
| `predicitas-crp_pgdata` | 1.122 | 4 | 4 | 2.143 | 57 | 2 |
| `predicitas-backend_pgdata` | 422 | 3 | 0 | 760 | 38 | 0 |
| `predicitas-guia-qa_qa_pgdata` | 1.080 | 3 | 0 | 2.080 | 3 | 0 |

Las tres tienen revisión `m01_001_indices_auditoria`, nueve tablas de negocio y base `predicitas`. Se conservaron las tres: no se fusionaron ni se asumió que fueran intercambiables. Intervenciones, cupos y reasignaciones tienen cero filas en las tres al capturar la línea base.

**Decisión confirmada por el usuario el 03/11/2026:** conservar `predicitas-crp_pgdata` como principal. Corresponde al Compose raíz y contiene más operación, incluyendo predicciones. Los otros dos permanecen respaldados y no se fusionan. La autorización queda registrada en `decision_bd_principal.json`; no se deduce únicamente del número de filas.

Hallazgo adicional: `backend-predicitas/.env` apunta a `127.0.0.1:5432/predicitas_crp` con rol `postgres`, distinto del Compose. No se encontró servicio PostgreSQL nativo ni instalación habitual en Program Files, ni listener nativo en 5432/5433. Esa configuración puede estar desactualizada; no se cambió. Es una razón adicional para confirmar el origen definitivo.

### Entorno comprobado

- Git 2.54.0.windows.1; un repositorio raíz, rama `master` y un worktree.
- Docker cliente/servidor 29.5.2; Compose v5.1.4.
- Python del host 3.14; Python de la imagen backend usada en pruebas 3.12.16.
- Node del host v24.16.0; npm 12.2.0. El Dockerfile frontend prescribe Node 22: esta línea base nativa no sustituye una validación posterior bajo Node 22.
- Imagen backend existente `predicitas-crp-backend:latest`, ID observado `37b6761b59ce`. Las pruebas montaron **el código actual del host en solo lectura**, no el código antiguo incluido en esa imagen.
- Todas las dependencias fijadas en `requirements.txt` coinciden con el entorno instalado de esa imagen; ver `ia_baseline.json`. El archivo de requirements contiene BOM UTF-8, considerado al comparar.
- `npm ci` del lockfile actual funcionó en una copia temporal, sin modificar `package-lock.json` original.
- El primer intento de resolución limpia terminó por timeout de red. En la continuación se completó una **instalación real en un venv nuevo**: 54 versiones fijadas coinciden, exit code 0 y `pip check` correcto. Los resultados iniciales se conservan como evidencia histórica; ver `instalacion_limpia_backend.json` y `instalacion_limpia_validacion.json`.
- `backend-predicitas/Skills/` y `frontend-predicitas/Skills/` existen y contienen cero elementos.

## 3. Respaldos privados y recuperación comprobada

### Ubicación duradera fuera de OneDrive y Temp

`C:\Users\arami\AppData\Local\PrediCitasBackups\fase0-20261103-2200`

El manifiesto `respaldo_duradero.json` registra 11 archivos de respaldo verificados por SHA-256, aproximadamente 172 MB:

- ZIP completo del proyecto previo a esta ejecución, con `.git`, CSV, modelo y `.env`.
- Inventario privado de archivos/hashes.
- Tres archivos TAR físicos de los volúmenes originales.
- Tres dumps PostgreSQL custom (`crp.dump`, `backend.dump`, `qa.dump`).
- Tres respaldos globals con roles y hashes de passwords, de acceso privado.

Al finalizar se conserva también `evidencias_fase0.zip`, con este directorio de evidencias y el plan actualizado, más su hash en un archivo lateral. Una segunda copia de ese ZIP sin secretos queda bajo `backups/` del proyecto.

Se deshabilitó herencia de permisos en el directorio y se concedió acceso al usuario actual y SYSTEM. **ACL no equivale a cifrado:** los dumps y ZIP deben tratarse como secretos y no enviarse al repositorio ni compartirse sin protección.

Hay además un staging privado en:

`C:\Users\arami\AppData\Local\Temp\opencode\predicitas-fase0-20261103-2200`

Incluye logs completos, copias de trabajo, configuración/credenciales aleatorias de los entornos de pruebas y copias de los respaldos. No depender de Temp como respaldo permanente.

La copia secundaria dentro del proyecto es `backups/predicitas-fase0-20261103-2200/proyecto_sin_secretos.zip`: incluye código, datos sintéticos y modelo, **no `.env` ni `.git`**. Está ignorada por Git. Los directorios `Skills` vacíos se verificaron en el origen, pero ZIP/Git no deben usarse como garantía de conservarlos: hay que recrearlos al preparar el entorno.

Todas las ubicaciones siguen en el mismo equipo; para protección frente a pérdida del disco se recomienda una copia cifrada externa independiente. No se configuró almacenamiento remoto ni se transfirieron respaldos a terceros.

### Método de copia, sin escribir en originales

1. Verificar ausencia de contenedores escritores sobre cada volumen.
2. Montar cada original como **solo lectura** en un contenedor puntual sin red y serializarlo con TAR, conservando permisos.
3. Restaurar cada TAR en un volumen **nuevo**, con prefijo `predicitas-fase0-20261103-2200-*`.
4. Iniciar PostgreSQL solo en esas copias para leer catálogo y generar dumps/globals.
5. Crear una cuarta instancia de PostgreSQL vacía y aislada; restaurar globals y `crp.dump` mediante `pg_restore --create --exit-on-error`.
6. Comparar nueve conteos y fingerprints de contenido, Alembic, columnas, secuencias, índices, constraints, triggers, grants y políticas RLS.

**Resultado:** restauración lógica de `crp.dump` y roles comprobada, sin diferencias funcionales del catálogo ni del contenido. PostgreSQL reescribió 15 expresiones CHECK convirtiendo casts de arrays varchar→text a casts por literal; se documentaron ambas formas y se normalizó únicamente esa transformación equivalente para comparar. No se ignoraron diferencias arbitrarias; ver `restore_verificado.json`.

Los dumps de Backend y QA se generaron y verificaron por hash; sus copias físicas se iniciaron y consultaron. **No se afirma que sus dumps lógicos hayan sido restaurados individualmente.** Si se elige cualquiera como principal, repetir la prueba de restauración de su dump antes de cerrar fase 0.

La instancia restaurada se usó después como laboratorio: se crearon otra BD vacía para pytest y credenciales aleatorias solo allí. Los cambios y secuencias de laboratorio no se confunden con el snapshot de recuperación previo.

## 4. Línea base funcional: resultados reales

| Comprobación | Resultado |
|---|---|
| Suite backend completa | **Bloqueada en colección**: `tests/ia/conftest.py:15` importa `app.modules.ia.cliente`, inexistente |
| Diagnóstico backend excluyendo solo `tests/ia` | **218 aprobadas, 1 fallida**, 219 ejecutadas; cobertura **87,12%** |
| Fallo backend ejecutado | `tests/test_reasignacion.py:52`: el test itera el JSON como lista, pero la respuesta actual es un objeto paginado; `TypeError: string indices must be integers, not 'str'` |
| Migraciones desde BD vacía aislada | Las tres revisiones se aplican hasta `m01_001_indices_auditoria` |
| `npm ci` frontend | Correcto, 264 paquetes instalados |
| Typecheck frontend | Falla con siete diagnósticos TypeScript |
| Lint frontend | Bloqueado por su paso inicial de TypeScript; no se declara que ESLint haya completado |
| Build frontend | Bloqueado por TypeScript; no se obtuvo build aprobado |
| Vitest frontend | **451 aprobadas, 56 fallidas**, 507 pruebas en 27 archivos; dos archivos con fallos |
| Cobertura frontend | No se produjo reporte al fallar Vitest; umbral no acreditado |
| npm audit | Nueve vulnerabilidades moderadas; cero altas/críticas; no se aplicó `audit fix` |
| Modelo IA existente | Carga y predice sin entrenar; hash sin cambios; versión `LightGBM_v1.0.0` |
| Smoke API, tres roles | Login, `/auth/me`, bandeja, catálogos, métricas y dataset-resumen responden 200 |
| API sin sesión | `/health` responde 200 y `/citas` responde 401 |
| Navegador real, Recepción | Login con usuario desechable y carga de bandeja `/citas`, **1.122 citas** |
| Capturas de pantalla | No obtenidas por ventana no visible; el usuario aceptó expresamente evidencia funcional alternativa, sin validación visual completa |

### Fallos frontend a conservar como baseline, sin arreglar en esta fase

1. `src/main.tsx:5`: import con extensión `.tsx` sin habilitar `allowImportingTsExtensions`.
2. `src/modulos/citas/Detalle.tsx:371,374`: `observacion` ausente del tipo `CheckInOut`.
3. `src/modulos/intervenciones/Intervenciones.tsx:3`: import `Pagina` sin uso.
4. `src/modulos/lista-espera/Cupos.tsx:75`: indexación de mapa de estados con `any`.
5. `src/modulos/lista-espera/ListaEspera.tsx:186`: indexación de mapa de estados con `any`.
6. `vite.config.ts:8`: propiedad `test` incompatible con el tipo de configuración importado.

Los siete diagnósticos proceden de seis ubicaciones/causas, porque `observacion` se referencia dos veces. Los 56 fallos Vitest están en `src/modulos/citas/Detalle.test.tsx` y `src/modulos/citas/citas.test.tsx`. Ver detalle verificable en `resultados_baseline.json`.

La exclusión `--ignore=tests/ia` se usó **solo como diagnóstico adicional**. No se eliminó esa carpeta, no se cambió la configuración de pytest y no se considera la suite completa aprobada.

Los tests se conectaron a `predicitas_fase0_test`, creada vacía en el servidor restaurado. Nunca se usó para pytest la BD original ni se confió en el `.env` de desarrollo. Las imágenes montaron aplicaciones RO; frontend corrió desde una copia temporal con su propio `node_modules`.

### API y navegador

`capturar_api.py` guardó OpenAPI y ejemplos sin JWT/passwords, usando usuarios de prueba dentro de una transacción externa revertida. Esto acredita un smoke de lectura/autenticación, **no** la totalidad de contratos/RBAC ni todas las operaciones de escritura.

Para el navegador se creó otro usuario desechable exclusivamente en la copia restaurada. Frontend temporal en loopback 5174, API temporal en loopback 8001. La red Docker `internal` inicialmente impedía publicar la API en host; se añadió conexión bridge solo a la API aislada. Se verificó CORS correcto y carga final de la bandeja. No se atribuye ese incidente de preparación a un defecto del proyecto.

No se cambiaron contraseñas de usuarios originales. En la continuación se confirmó por comparación de hash, únicamente en la copia restaurada, que las tres cuentas históricas están activas y coinciden con la clave de seed configurada en el Compose original. La clave y los hashes no se duplican en el informe. Para navegar se siguieron usando cuentas desechables en una copia.

## 5. Garantías verificadas y cierre del laboratorio

- Se compararon **302 archivos originales** contra el inventario inicial: cero cambios, excluyendo solo metadata Git y el plan que se actualiza intencionadamente.
- Los tres TAR recalculados desde los volúmenes originales RO coinciden exactamente con sus hashes iniciales. No solo coinciden sus conteos: los originales permanecieron intactos.
- El modelo conserva SHA-256 `89297942F603DC040C9954D534AE6DAE97590203F0345925C12FC4E0A90E9074`.
- Se cerró la pestaña de auditoría y se detuvo el proceso Vite temporal, comprobando su ruta antes de detenerlo.
- Se detuvieron únicamente los cinco contenedores nombrados `predicitas-fase0-20261103-2200-*` creados para esta ejecución. No se borraron contenedores/volúmenes ni se tocaron recursos de otros proyectos.
- Quedan los tres volúmenes clonados y el volumen restaurado para reproducir el análisis; están aislados y sus contenedores detenidos. Docker Desktop quedó encendido.
- Una instancia de otro nombre apareció durante la sesión: se dejó intacta. No interpretar `docker ps` global como inventario exclusivo del proyecto.

## 6. Evidencias y herramientas

| Archivo | Contenido |
|---|---|
| `inventario_archivos.json` | Archivos originales y hashes; los `.env` solo figuran como privados |
| `respaldo_archivos.json` | ZIPs iniciales y su verificación; su advertencia de Temp describe la primera etapa, superada por respaldo duradero |
| `respaldo_duradero.json` | Ubicación definitiva y hashes de las 11 copias |
| `inventario_entorno.json` | Entorno, keys de `.env` y conexiones con passwords redactadas |
| `postgresql_nativo.json` | Inspección del posible servidor nativo |
| `volumenes_respaldados.json` | Originales RO, clones, tamaños y hashes TAR |
| `bd_crp_baseline.json`, `bd_backend_baseline.json`, `bd_qa_baseline.json` | Catálogo, conteos y fingerprints de las tres bases |
| `dumps_privados.json` | Manifiesto de dumps/globals, sin contenido privado |
| `restore_verificado.json` | Comparación documentada de recuperación de CRP |
| `openapi_baseline.json` | Contrato público actual completo |
| `api_smoke_baseline.json` | Respuestas del smoke por rol sin credenciales |
| `ia_baseline.json` | Tres fixtures/predicciones, métricas y versiones instaladas |
| `backend_coleccion_junit.xml` | Error de colección de la suite completa |
| `backend_diagnostico_junit.xml`, `backend_diagnostico_coverage.json` | Diagnóstico parcial y cobertura |
| `frontend_resultados.json`, `frontend_auditoria_resumen.json` | Exit codes y vulnerabilidades sin arreglos automáticos |
| `resultados_baseline.json` | Resumen consolidado de pruebas y límites de la validación |
| `originales_verificados.json` | Verificación de archivos y bytes de volúmenes originales |
| `cierre_servicios.json` | Recursos de laboratorio detenidos y preservados |
| `decision_bd_principal.json` | Confirmación del usuario del volumen principal |
| `decision_evidencia_visual.json`, `navegador_snapshot_extractos.md` | Aceptación de alternativa visual y extractos observados |
| `instalacion_limpia_backend.json`, `instalacion_limpia_validacion.json` | Instalación real en venv nuevo y 54 versiones comprobadas |
| `credenciales_demo_verificadas.json` | Cuentas demo verificadas sin publicar passwords/hashes |
| `originales_verificados_cierre.json`, `respaldo_revalidado_continuacion.json` | Revalidación final de archivos, volúmenes y respaldos |
| `cierre_servicios_continuacion.json`, `CIERRE_FASE_0.md` | Cierre de la continuación y límites del alcance completado |

Los scripts `.py`, `.ps1` y `catalogo.sql` de esta carpeta son **herramientas/evidencias de fase 0, no componentes del backend**. Tienen guardas de origen, nombres explícitos y se niegan a sobrescribir evidencias. Algunos nombres de recursos están fijados a esta ejecución para evitar operar accidentalmente sobre otro entorno. No reejecutarlos ciegamente ni sustituir nombres de originales sin revisar todo el procedimiento.

Logs completos y configuraciones aleatorias de laboratorio permanecen en staging privado. No se publican dumps, `.env`, JWT o hashes de passwords.

## 7. Cierre de pendientes de fase 0

- [x] **Confirmación del usuario:** se conserva como principal `predicitas-crp_pgdata` con 1.122 citas. No fusionar ni retirar las otras bases.
- [x] Instalación limpia backend completada en venv aislado; 54 versiones fijadas comprobadas y `pip check` correcto.
- [x] Usuario aceptó explícitamente evidencia funcional alternativa; no se declara captura ni revisión visual completa.
- [x] Línea base archivada con fallos conocidos; su estabilización se planifica separadamente en fase 1, sin declarar aprobación funcional ni corregirlos durante movimientos.
- [x] Credenciales demo históricas verificadas localmente por hash en una copia; sin publicar/cambiar passwords. Navegación con cuentas de laboratorio.

**No saltar a fase 2.** La base ya está confirmada y la línea base congelada con sus fallos. Corresponde fase 1 documental/de contratos y decidir allí la estabilización necesaria.

### Próxima acción concreta

Iniciar fase 1 cuando se solicite. Antes de retomar, leer `CIERRE_FASE_0.md`, los resultados históricos y la evidencia de continuación; comprobar respaldos y no sustituir la BD principal por clones de laboratorio. Los fallos previos no se consideran resueltos.
