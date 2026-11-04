# Fase 1 — Contratos y decisiones de arquitectura

**Estado: COMPLETADA en alcance documental/de contratos.** Fecha: 03/11/2026. No se ejecutó fase 2 ni se corrigió lógica existente.

## Resultado

- Ocho ADRs definen arquitectura, propietarios/transacciones, almacenamiento, datos, IA, registry y compatibilidad.
- Volumen principal existente `predicitas-crp_pgdata`, base `predicitas`, proyecto Compose `predicitas-crp`, puerto host DB 5432 configurable explícitamente. No restore/seed por defecto; FreshDemo separado y autorizado.
- Snapshot público **byte a byte idéntico** a fase 0, inventario completo de **55 operaciones** contrastado con código y roles declarados.
- Inventario AST de **15 rutas frontend de módulos**, una ruta test-only y menús; **21 archivos legacy sin alcance estático desde entrada/ranuras**, sin eliminarlos.
- Mapa de **74 imports cruzados**, **90 sitios db.*** y **27 commits**; diferenciados lectura, escritura y composición. Incluye import local del alias IA en Citas.
- **12 JSON Schemas** draft 2020-12, OpenAPI IA objetivo 3.1, CSV operacional/dataset/features/snapshots/manifiestos/puntero activo y **60 ejemplos** válidos/negativos. No se creó un dataset ni un artefacto.
- Contratos diferencian números internos IA y Decimal string público, límites/bordes, correlación, batch atómico, errores y metadata sin BD.
- Importación legacy del modelo expresa linaje desconocido con null, nunca hashes/fechas inventados; sigue requiriendo aprobación y paridad en fase 6.
- Entrega separada de estabilización y recorrido E2E definidos. Los fallos de fase 0 siguen abiertos, no se maquillan con contratos nuevos.

## Índice de entregables

| Entregable | Ubicación |
|---|---|
| Decisiones y diagramas | `docs/arquitectura/DECISIONES.md` |
| Rutas/roles/consumidores | `docs/arquitectura/RUTAS_Y_CONSUMIDORES.md` |
| Dependencias y escrituras | `docs/arquitectura/MAPA_DEPENDENCIAS_Y_ESCRITURAS.md` |
| Estabilización S-01..S-13 y E2E | `docs/arquitectura/ESTABILIZACION_Y_E2E.md` |
| API pública congelada y política | `contracts/backend/` |
| Schemas/datos/IA y ejemplos sintéticos | `contracts/data/`, `contracts/ia/`, `contracts/examples/` |
| Endpoints, métodos, roles, cuerpos/query/respuestas | `endpoints_actuales.json`, `ENDPOINTS_ACTUALES.md` |
| Imports y sitios db con archivo/línea/función | `dependencias_y_persistencia.json` |
| UI rutas/menú/alcance de imports | `frontend_rutas_menu_alcance.json` |
| Literales frontend candidatos | `referencias_frontend.json` (no afirmar que todos son llamadas HTTP) |
| Validación actual de schemas/fixtures | `validacion_contratos.json` |
| Contraste con validadores/backend actual | `validacion_contra_backend_actual.json` |
| Integridad de la entrega | `verificacion_entrega.json` |

La primera iteración de 55 casos y la intermedia de 59 quedan en `historico/`; no son fixtures vigentes ni se validan contra schemas posteriores. Durante revisión se añadió representación honesta de legacy y corte desconocido. La referencia vigente es `contracts/examples/casos.json` y su reporte final.

## Validaciones realizadas y límites

1. Schemas con `Draft202012Validator.check_schema`, referencias locales offline y formatos fecha/UUID. Ejemplos positivos y negativos con invariantes de fórmulas, IDs/modelo/snapshot, bordes, clases/particiones y fechas. Los errores esperados cuentan como comprobación correcta, no como servicios que fallen.
2. Integridad de OpenAPI/refs/operationId/responses; no se ejecutó un validador formal completo de OpenAPI. El contrato público se comparó además con `app.openapi()` del backend actual en contenedor sin red, código/contratos RO.
3. Ocho casos de fila operacional contrastados con `validar_fila` real. CSV válido: 2/0; mixto: 1/3 mediante validación pura y duplicados locales. Sin BD/persistencia ni duplicados ya existentes en PostgreSQL.
4. Inspección de firmas confirma que el alias de REP-02 es incompatible y el de REP-03 sí enlaza sus argumentos. **No se ejecutó HTTP ni se declara probado el reporte completo.**
5. AST frontend con TypeScript de la copia de laboratorio: no ejecuta componentes ni certifica reachability dinámica/externa. Fixture de ranura ya es test-only en código actual.
6. Integridad de archivos originales, snapshot y Skills; revisión de secretos largos y enlaces relativos en entregables. No constituye un escaneo de seguridad exhaustivo.

**No se consultó/montó el volumen principal, entrenó, cargó Joblib, cambió `.env`, instaló dependencias dentro de apps, ejecutó migraciones, seed o nueva suite funcional.** El entorno `jsonschema[format]==4.25.1` existe solo en Temp como herramienta. El contenedor de contraste usa la imagen baseline existente y `network=none`, sin DSN operativo.

## Reproducción

Desde la raíz, con entorno de herramientas separado:

```powershell
$tools = Join-Path $env:LOCALAPPDATA 'Temp\opencode\predicitas-fase1-tools'
& "$tools\Scripts\python.exe" docs/migracion/fase-01/validar_contratos.py --output docs/migracion/fase-01/validacion_repetida.json
```

El entorno de herramientas requiere `jsonschema[format]==4.25.1` y tzdata, no son requisitos nuevos del backend. Se niega a sobrescribir evidencia existente. Para revalidar usar nombre nuevo. Si se pierden herramientas temporales, recrear venv aislado, no editar requirements de aplicaciones.

`inventariar_contratos.py`, `preparar_ejemplos.py`, `inventario_frontend.cjs` y `contrastar_backend_actual.py` generan evidencia nueva con protección de sobrescritura; no reejecutarlos encima de la evidencia congelada. `validar_contratos.py` es el chequeo repetible de solo lectura salvo su reporte. El validador no descarga los IDs `predicitas.invalid`.

## Criterios y paso siguiente

- [x] Decisiones y contratos definidos, sin decisiones críticas de especificación pendientes para comenzar la migración mecánica.
- [x] Ejemplos positivos/negativos, permisos y consumidores documentados.
- [x] Separación inequívoca entre API actual, objetivo no implementado y fallos conocidos.
- [x] Sin cambios funcionales ni movimientos de aplicaciones.
- [x] Pruebas documentales y de integridad con evidencia; no se afirma suite funcional verde.

**Gate importante:** S-01 (TypeScript/build) debe resolverse en entrega independiente antes de cerrar fase 2; preferible hacerlo antes de mover. Esta fase 1 no autoriza arreglos mezclados ni saltar a IA externa. Se recomienda solicitar la estabilización mínima S-01 y después la fase 2, con diffs separados.

Respaldo/punto de retorno: snapshot `69c686f` y backups privados de fase 0 para aplicaciones/BD intactas; ZIP adicional de esta entrega en almacenamiento privado duradero, con manifiesto separado. Mantener cambios locales revisables sin commits automáticos.

El ZIP adicional de fase 1 se conserva en `%LOCALAPPDATA%\PrediCitasBackups\fase1-20261103-2306\evidencias_y_contratos_fase1.zip`, con copia sin secretos en `backups/fase1-20261103-2306/`. Hash y tamaño en `respaldo_fase1.json`. No sustituye dumps/roles/modelo respaldados en fase 0; todos siguen en el mismo equipo, por lo que se recomienda copia cifrada externa independiente.
