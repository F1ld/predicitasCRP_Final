# Decisiones de arquitectura — fase 1

Fecha: 03/11/2026. Estado de estas decisiones: **definidas para la migración; implementación pendiente en las fases indicadas**. No confundir contratos objetivo con arquitectura ya desplegada. Baseline: snapshot `69c686f` y evidencia de fase 0. No se modifican reglas clínicas, modelo, datos ni endpoints por aprobar este diseño.

## ADR-001 — Componentes y repositorio

**Decisión:** monorepositorio, frontend React independiente, backend FastAPI monolítico modular, IA de inferencia independiente y PostgreSQL 16 controlado por backend. `apps/frontend`, `apps/backend`, `apps/ia`, `contracts`, `data`, `artifacts`, `runtime`, `infrastructure`, `docs` y scripts raíz tendrán las responsabilidades del plan integral.

Los módulos backend no son microservicios: llamadas en memoria y una sesión/transacción pueden abarcar varios módulos. El navegador habla solo con backend. IA habla por HTTP interno, no con BD ni con el navegador. Entrenamiento es una tarea explícita separada de inferencia, sin endpoint de entrenamiento.

Mantener Python 3.12 y Node 22 como referencias Docker; registrar diferencias del host. No actualizar frameworks en una mudanza. No añadir colas, Kubernetes o bases por módulo. `.venv`/`node_modules` se regeneran por aplicación; no compartir `PYTHONPATH` entre apps Python.

**Implementar:** fase 2 mueve solo frontend/backend; fases 5–7 extraen/conectan IA. **Retorno:** rutas/configuración previas sobre el mismo volumen y modelo, no eliminación de datos.

## ADR-002 — Propietarios de datos y contratos internos

| Área | Propietario de escritura | Contrato público interno objetivo |
|---|---|---|
| Usuarios | `usuarios` | Consultar usuario, administrar cuenta y operaciones autorizadas de identidad |
| Auth | Sesiones/bloqueo/revocación por mecanismos actuales, sin crear tabla por esta fase | Validar credenciales/token, principal autenticado `{id_usuario, rol, activo}`, dependencia de roles |
| Citas | `citas`, `historial_estados_cita` | Importar, consultar snapshot, confirmar, reprogramar, liberar, desenlace y check-in |
| IA backend | `predicciones_ia` | Solicitar inferencia vía puerto, guardar/listar predicciones y proyectar metadata |
| Intervenciones | `intervenciones` | Consentimiento, opt-out, envío/entrega/fallo y respuesta |
| Lista de espera | `lista_espera`, `cupos_liberados`, `reasignaciones` | Crear/liberar cupo, candidatos, oferta, rechazo/desistimiento, asignación humana |
| Auditoría | `auditoria_eventos` | Append de evento sin commit independiente; consulta por adaptador autorizado |
| Reportes | Ninguna tabla operativa | Consultas de lectura compuestas y exportación |

Mantener inicialmente archivos planos por módulo: router, schemas, service, repository, models, reglas. Añadir `public.py`/DTO cuando haya consumidores, no capas vacías. Usuario físico puede moverse de Auth a Usuarios solo en fase 4, actualizando imports/registro ORM sin cambiar tabla ni FK.

**Reglas de dependencia objetivo:** router propio → caso de uso propio/workflow; workflow → contratos públicos; servicio → repositorio propio/reglas; repositorio → modelos propios y core BD. Ningún módulo importa router/repositorio/modelo privado ajeno para escribir. El principal de autorización no expone `password_hash` ni objetos ORM.

Excepciones explícitas: bootstrap registra todos los modelos; Alembic inspecciona metadata completa; adaptadores de lectura de reportes/bandeja/detalle pueden hacer JOIN de solo lectura, documentados y probados. Estas excepciones no autorizan escritura transversal. Auditoría y autenticación son dependencias públicas transversales, no servicios HTTP entre módulos.

`core` contiene infraestructura/errores/reloj/seguridad técnica, no servicios de negocio que llamen de vuelta a módulos. El registro ORM pasa a bootstrap en fase 4; sus imports globales no se consideran una violación de negocio.

## ADR-003 — Workflows y transacciones

Un caso de uso de nivel superior abre/cierra **una** transacción. Operaciones componibles de módulos y append de auditoría usan la misma sesión: `flush` permitido, commit interno prohibido. Router sin SQL/commit. No cambiar contratos públicos para introducir esta separación.

| Workflow objetivo | Participantes | Unidad atómica |
|---|---|---|
| Importar cita/lote | Citas + Auditoría | Filas aceptadas, historiales y evento de importación según comportamiento actual |
| Responder y confirmar | Intervenciones + Citas + Auditoría | Respuesta y transición cuando la ruta/caso de uso lo exige |
| Liberación voluntaria | Intervenciones + Citas + Lista de espera + Auditoría | Respuesta/cita/cupo/eventos, sin doble historial/cupo |
| Cancelación externa con cupo | Citas + Lista de espera + Auditoría | Cancelación informada y cupo `CANCELACION_EXTERNA` |
| Reasignación humana | Lista de espera + Auditoría | Cupo, candidato, reasignación y evento; bloqueo de ambos registros |
| Guardar predicción | IA backend + Auditoría | Snapshot vigente, predicción y evento tras inferencia externa |

Reglas: adquirir locks en orden estable y corto; no sostener locks/conexiones transaccionales mientras IA responde; fallo revierte toda operación de negocio. Fallo de login/bloqueo o auditoría técnica posterior a rollback requieren una transacción propia explícita, no perderlos al responder error.

Predicción: leer snapshot → cerrar transacción de lectura → HTTP → abrir transacción corta → revalidar estado/features y versión → guardar/auditar. Si cambió la cita, responder conflicto sin persistir resultado obsoleto. No sobrescribir un resultado previo cuando la nueva llamada falla. Unicidad `(id_cita, version_modelo)` se conserva y se prueba bajo concurrencia.

## ADR-004 — Persistencia y entorno local elegidos

- **Origen aprobado:** volumen físico `predicitas-crp_pgdata`, base `predicitas`, revisión `m01_001_indices_auditoria`. Usar **el existente**, no restaurar o seedear el principal por defecto.
- Compose oficial objetivo: `compose.yaml` raíz, proyecto **`predicitas-crp`**. Mantener nombre físico de volumen explícito, no derivarlo de una carpeta nueva. En modo Existing usar volumen externo y fallar si no existe; no crear una BD vacía silenciosamente.
- Variable objetivo `PGDATA_VOLUME_NAME=predicitas-crp_pgdata`. FreshDemo debe crear explícitamente otro volumen autorizado/vacío con nombre distinto, nunca usar ese nombre para regenerar datos.
- Puerto host DB elegido: **5432** por defecto vía `DB_PUERTO_HOST`. Si está ocupado, fallar con diagnóstico y pedir configuración explícita (p. ej. 5433); no cambiarlo automáticamente. Dentro de Docker siempre `db:5432`.
- Puertos oficiales locales: UI 5173, API 8000; IA 8100 solo loopback si se publica. Las instancias temporales 5174/8001 de fase 0 no se convierten en configuración oficial.
- Servicio backend con `predicitas_app`, nunca credenciales owner. Owner solo migrador/provisión/administración. Mantener RLS, triggers y permisos; RLS actual no equivale a autorización clínica por rol.
- Preservar revisiones, tablas, FK, índices y secuencias. Mover modelos no justifica `drop/create`, squash o autogenerate con renombres físicos.
- No levantar dos escritores de stacks viejos/nuevos. Preflight, respaldo, parada controlada, arranque nuevo y comparación antes/después. No ejecutar seed en Existing.
- `.env` nativo actual apunta a otra base con rol `postgres`: es configuración histórica divergente, no fuente autoritativa. Corregir ejemplos y operación en fase 9, sin copiar esas credenciales al nuevo backend.

## ADR-005 — Datos, CSV y linaje

CSV operacional y dataset IA son contratos distintos; `target_no_show` nunca entra como feature. Ejemplos pequeños sintéticos en `data/samples/importacion`; fixtures compartidos en `data/fixtures`; snapshots versionados en `data/raw`; particiones en `data/processed`; manifiestos en `data/manifests`. Esas rutas se crean/migran en fase 3, no ahora.

Backend es la fuente de verdad operacional en PostgreSQL. IA recibe features o archivos explícitos exportados/autorizados, no DSN ni modelos ORM. Generador sintético único en IA a partir de fase 6; seed backend consume CSV explícito, sin importar código IA.

Para extracción conservar inicialmente 1.000 históricos, semilla 42, split estratificado 70/15/15 y modelo observado. Meta 5.000, cambios de split temporal/paciente, nuevas features o nuevos datos son entregas distintas con versión y evaluación nuevas. El control de partición por ID no prueba generalización a pacientes desconocidos: no afirmarlo sin evaluación específica.

Una fuente explícita por ejecución, fecha de referencia y hashes. No fallback BD→sintéticos ante error. Solo datos sintéticos/seudonimizados en este piloto; no incorporar datos reales ni activar canales de mensajería reales por reorganizar archivos.

Uploads/descargas siguen en memoria por defecto. No retención nueva implícita; si se habilita, IDs seguros, TTL y limpieza acotada. PostgreSQL fuera de bind mounts de OneDrive. Dumps/.env/globals nunca en contratos o frontend público.

## ADR-006 — Artefactos y promoción

Registry objetivo `artifacts/models/<version_modelo>/` con `modelo.joblib`, `manifest.json`, `metrics.json` y referencia al manifiesto de dataset. `active.json` apunta a versión y hash del manifiesto; se publica mediante reemplazo atómico en el mismo filesystem. Montar el directorio padre, no un archivo sujeto a rename.

Pipeline escribe candidatos; serving lee RO y solo carga `APROBADO` + (`TRAINING_RUN` o importación legacy expresamente aprobada), rutas confinadas al registry y hashes/dependencias compatibles. Un hash prueba integridad, no confianza: `joblib.load` solo sobre artefactos internos de origen aprobado; no upload remoto arbitrario. Los fixtures de contrato nunca son elegibles para promover.

Conservar activo, anterior y candidato. Cargar/verificar completamente antes de cambiar activo; reinicio controlado como mecanismo inicial, no recarga concurrente compleja. Peticiones fijan versión; si cambia activo entre metadata e inferencia, 409 controlado y el backend no mezcla versiones. No entrenar en startup ni petición.

Preservar bytes/hash del modelo de fase 0 en primera extracción si es compatible. Reentrenar exige nueva versión. Ni siquiera un mismo nombre de algoritmo permite reutilizar `version_modelo` para bytes/features/umbrales diferentes. Métricas actuales pertenecen a ese artefacto y dataset, no a datos clínicos reales.

No inventar hashes del dataset original: si no se recuperan sus archivos, importar el modelo como `LEGACY_IMPORT`, `linaje_completo=false`, con hashes raw/splits nulos y metadata original identificada como tal. Sí calcular hashes reales del modelo, nuevo manifiesto y reporte recuperado. Aprobar ese legacy solo para continuar el piloto sintético, tras paridad, compatibilidad y revisión explícitas en fase 6; no presentarlo como entrenamiento nuevo reproducido. Nuevos entrenamientos usan `TRAINING_RUN`, linaje completo y hashes reales. Si no puede aprobarse el legacy, detener corte IA; no reentrenar y reemplazarlo silenciosamente.

## ADR-007 — IA HTTP, precisión y resiliencia

API objetivo y ejemplos en `contracts/ia/`. `X-IA-API-Key` solo backend↔IA; nunca JWT de usuario ni clave `VITE_*`. Healthchecks sin secretos. Backend puede iniciar/listo para operación sin IA; estado de inferencia se informa aparte.

Perfil de extracción v1: nueve features crudas obligatorias, sin nulos; IA calcula las dos derivadas. Manifest es fuente única de umbrales; v1 fija medio 0.300 y alto 0.450. Redondear como pipeline actual Python (`round(clamp(raw,0,1),3)`) **antes** de clasificar: BAJO `<0.300`, MEDIO `0.300..0.450`, ALTO `>0.450`. No reclasificar usando raw ni otro corte del `.env`. Cambio de umbrales/perfil incompatible requiere nueva versión de modelo/contrato, no cambiar constantes por configuración silenciosa.

HTTP interno usa números JSON; API pública conserva tipos actuales, incluidos Decimal serializados como string en `/ia/*` frente a float en detalle de citas. El adaptador convierte, no cambia DTOs públicos.

Lote interno: 1..100 items, JSON ≤256 KiB, IDs opacos únicos; todo válido o error. Chunk backend sin introducir un nuevo límite de cantidad público por la mudanza. Preservar selección actual: lote considera **solo RECIBIDA**, individual acepta RECIBIDA/CONFIRMADA/REPROGRAMADA. No añadir filtro de futuro que hoy no aplica el repositorio aunque su comentario diga «próximas».

Timeouts iniciales objetivo: conexión 1 s, lectura/escritura 5 s, pool 1 s, presupuesto total público 60 s incluyendo metadata/chunks; cero reintentos automáticos. Son parámetros operativos a medir en fase 7; cambiar valores no permite mezclar versiones ni hacer commits parciales. Si no se cumple presupuesto, error controlado antes de persistir, no convertir a jobs sin nuevo contrato.

Guardar lote público en una transacción final corta y atómica, sin transacción abierta entre chunks; fijar versión desde metadata y validar cobertura exacta de IDs. Error → ninguna predicción nueva de esa ejecución. Solicitud UUID sirve para correlación, no promete idempotencia persistente; hoy repetir puede producir otra auditoría aunque actualice la misma fila.

Backend: desconexión/modelo ausente 503 `MOTOR_IA_NO_DISPONIBLE`; timeout 504 `IA_TIMEOUT`; respuesta inválida/versionado incoherente 502 `IA_RESPUESTA_INVALIDA`; cita modificada 409 `PREDICCION_DESACTUALIZADA`. Clave interna inválida es problema de integración, no 401 al usuario autenticado. Mantener envelope público `{error:{codigo,mensaje,campos}}`; 401 de sesión sigue invalidando sesión real, no por fallo IA.

## ADR-008 — Compatibilidad, seguridad y estabilización

La fase 2 es mecánica. Mantener URLs, verbos, roles, JSON, alias no equivalentes, formularios, cookies/headers actuales, semántica de fechas y paginación. No regenerar OpenAPI para ocultar diferencias. Corregir contratos antiguos requiere ticket/prueba independiente; corregir implementación requiere entrega explícita, no una mudanza encubierta.

Rutas legacy de intervenciones eluden consentimiento/elegibilidad/catálogo; no se consideran equivalentes a las nuevas. Se documentan solo como compatibilidad temporal del piloto **sintético local**; impiden declarar uso real seguro. Su endurecimiento debe acordarse/versionarse, no mantener el bypass como política deseada ni activarlo en entorno real.

Plantillas actuales contienen placeholder; no afirmar mensajes reales aprobados. Límite actual es una intervención no fallida y hasta dos intentos totales si fallan; un comentario de «recordatorio adicional» no sustituye el código que se ejecuta. Mantener esta baseline hasta revisión separada de requisitos. Silencio nunca libera/cancela.

La lista completa de deudas y gates está en `ESTABILIZACION_Y_E2E.md`. Cerrar fase 1 significa decisiones y contratos comprobados, no que esas correcciones estén implementadas o todos los tests pasen.
