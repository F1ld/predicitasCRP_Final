# Fase 3 — Centralización de muestras, artefactos y salidas

**Estado: COMPLETADA (con deuda técnica D-01 a D-04) — 05/11/2026.** Implementación aplicada, revalidada con imagen oficial `predicitas-fase3-backend:validacion` (`sha256:a6e71ea3...`) y commit de código `8314479`. Punto de retorno inicial: **`a5a1f5f`**.

## Resultado y límites

- Muestras canónicas en `data/samples/importacion/`: CSV variado (40 filas) y demo (24 filas). Copiados y verificados por SHA-256, **sin modificar un byte ni sus fechas**.
- Las tres copias anteriores (raíz y backend) quedan como **compatibilidad histórica no canónica**, sin sincronización automática ni nuevos consumidores. Se actualizaron las guías activas al destino canónico. **No se borró ningún CSV.** La retirada de duplicados se difiere deliberadamente hasta revisar también consumidores externos; no impide usar la única ubicación canónica documentada.
- Los cuatro CSV exclusivos del frontend y los fixtures de `contracts/examples/` permanecen en su sitio, con hashes intactos. No se duplicaron como fixtures compartidos.
- Estructura `data/raw`, `data/processed`, `data/manifests`, `data/fixtures`, `artifacts/models`, `artifacts/reports`, `runtime/exports`, `runtime/tmp`, `runtime/test-results`. Raw/processed siguen vacíos: esta fase no prepara ni entrena datasets.
- Copia del modelo en `artifacts/models/legacy-import/modelo_predicitas_v1.joblib`, con hash idéntico y atributo Windows de solo lectura. **No se carga/promueve esa copia ni se cambia la ruta activa integrada**. No se creó `active.json`, manifiesto de promoción ni linaje inventado.
- `data/manifests/inventario-fase-03.v1.json` documenta procedencia, bytes/hashes, columnas, filas, fechas observadas, resultados esperados, copias de compatibilidad y permisos observados. Fechas/semillas originales y hashes de entrenamiento desconocidos son null. Es inventario de preservación, no certificado de entrenamiento.
- `.dockerignore` en la raíz documentado como no aplicable a los contextos oficiales `apps/*` de `compose.yaml`. Contextos oficiales siguen limitados a cada app; la imagen backend excluye `data/` legacy pero **conserva el modelo activo**. Compose no requería cambios ni montajes permanentes nuevos: las muestras se suben vía navegador/API en memoria.
- Los uploads/descargas operacionales siguen en memoria/streaming; no se activó retención, TTL, limpieza automática ni `runtime/imports`.

Guía vigente: [`data/README.md`](../../../data/README.md), [operación de archivos/resultados](../../operacion/ARCHIVOS_Y_RESULTADOS.md) y README raíz. Los informes históricos y capturas no se reescribieron.

## Cambios quirúrgicos de herramientas, no de negocio

### Exportador CLI

`apps/backend/scripts/exportar_csv.py` ahora exige **salida absoluta nueva** y **fecha de referencia explícita**. Crea padres cuando corresponde y usa apertura exclusiva `x`; rechaza sobrescritura, enlaces de destino y salidas dentro de código/muestras/modelos/backups. Dentro del repo solo permite los directorios runtime autorizados; admite destinos externos absolutos explícitos.

Se conserva generador, semilla por defecto 7, prefijo DEMO y las cuatro filas de rechazo. La salida se proyecta a las **13 columnas operacionales**: se corrige la discrepancia del CLI anterior, que escribía todas las columnas del generador (incluidas derivadas/target). Esto no cambia `CitaImportIn`, importación, etiquetas derivadas en backend ni entrenamiento. El exportador es para muestras de prueba, **no es seed ni dataset IA**.

La fecha no se deduce del día del equipo. Nuevas fechas/nombres producen otra muestra, sin alterar las muestras históricas. Se imprimen fecha, semilla y hash del archivo generado. El empaquetado `/app` y el monorepo funcionan sin depender accidentalmente del CWD ni requerir credenciales BD.

### Salidas de QA

Solo se cambia infraestructura de archivos en `apps/frontend/tests/validar_diseno.py`: toda la ejecución imperativa se aísla dentro de `main()` protegido por `if __name__ == "__main__":`; se invierte el orden validando la BD antes de crear carpetas o conectar; cero efectos colaterales al importar (CWD intacto, sin conexiones ni carpetas huérfanas). Nuevas salidas en `runtime/test-results/diseno/<id>/`, CSV por ejecución y `manifest.json` exclusivo; no se sobrescribe `ultima_validacion_diseno.json` ni fixtures/capturas históricos. La base alternativa `PREDICITAS_TEST_RESULTS_DIR` debe ser absoluta y no apuntar a código.

El helper puro `rutas_validacion.py` valida IDs/rutas y añade una guarda antes de abrir conexión: `PREDICITAS_QA_DATABASE_NAME` debe coincidir con un nombre test/qa explícito. El flujo de negocio QA no se rediseñó. **No se ejecutó/certificó el E2E visual legacy completo**; se probaron rutas, exclusividad, traversal, importación limpia y bloqueo de bases no confirmadas. La guarda no sustituye inspeccionar host/URL/volumen.

## Evidencia ejecutada

| Verificación | Resultado |
|---|---|
| 33 pruebas nuevas de archivos/CLI/QA/invariantes | **33 aprobadas** (incluye test de importación limpia e invariantes de centralización/manifiesto) |
| Importación API desde CSV canónicos | **40/0** variado, **20/4** demo, BD inicialmente vacía y reloj fijo 2026-11-05 08:00 Lima |
| BOM, segunda importación y rollback | PASÓ; segunda carga no duplica; usuarios/citas/historial/auditoría se revierten limpiamente |
| OpenAPI y tres predicciones congeladas | Idénticos; modelo activo sin cambios |
| Build backend desde contexto actual | PASÓ; imagen `predicitas-fase3-backend:validacion` (`sha256:a6e71ea3...`) |
| Exportación dentro de imagen, sin red/credenciales | PASÓ; salida host explícita, segundo intento rechazado sin cambiar bytes |
| Exclusiones Docker | Datos legacy, copia registry raíz y `.env` privado ausentes; artefacto activo presente e idéntico |
| Frontend tests y typecheck/lint/build | Línea base citada: 451 aprobadas / 56 fallidas preexistentes; 0 regresiones (sin cambios en código fuente de frontend) |
| Backend diagnóstico sin `tests/ia` | 251 aprobadas / 1 fallida: 218 previas + 33 nuevas; mismos casos previos; **87,13 % cobertura app**, sin rebajar 75 % |
| Suite backend completa | Conserva error previo de colección por `app.modules.ia.cliente` inexistente (S-02); no se presenta como suite verde |
| Integridad y clon limpio | 444 originales examinados, únicamente cambios previstos; clon limpio en directorio temporal verificado con todas las muestras y manifiestos presentes |

## Deuda técnica aceptada de fase 3

- **D-01 (Retiro de CSVs legacy):** Las copias en la raíz y `apps/backend/data/` se mantienen transitoriamente por compatibilidad; su eliminación queda programada para las Fases 6 y 7 al migrar importers y extraer IA. Responsable: Arquitectura de Datos.
- **D-02 (Mensaje informativo `+4` en CLI):** Conteo cableado en mensaje de salida de `exportar_csv.py`; no afecta lógica de generación/importación ni contrato operacional.
- **D-03 (Ubicación de `rutas_validacion.py`):** Helper auxiliar mantenido en `apps/frontend/tests/` hasta la armonización de herramientas de prueba en Fase 10.
- **D-04 (Ausencia de pin en `coverage`):** Versión de paquete `coverage` sin pin fijo en backend (7.17.0 vs 7.17.2), produciendo pequeñas variaciones decimales en cobertura sin comprometer el umbral exigido (≥ 75 %).

No se arreglaron defectos previos ni actualizaron snapshots para ocultarlos. Las primeras comprobaciones se conservaron; tras añadir la guarda extra de QA se repitieron unitarias, regresión y build como `*_final`, sin sobrescribir resultados anteriores.

## Aislamiento, recursos y confirmaciones

- Se inició únicamente PostgreSQL **nuevo**, volumen `predicitas-fase3-…-test-pgdata`, red privada sin puertos, contraseñas aleatorias privadas y base `predicitas_fase3_test`. La guarda del runner exige ese nombre y host de fase 3 antes de la prueba de importación.
- Se aplicó el historial Alembic existente exclusivamente a esa base vacía de pruebas. No se creó ninguna revisión nueva ni se ejecutó seed.
- Ninguno de los tres volúmenes originales se montó en el laboratorio ni tuvo escritores activos; no se arrancó el principal ni se restauraron/fusionaron datos. Los tres `.env` originales conservan bytes exactos.
- El servidor nuevo quedó **detenido**, contenedor/red/volumen conservados. Recursos preexistentes intactos; no se borraron volúmenes ni backups.
- No surgió necesidad de ejecutar acciones críticas/de alto riesgo. Retirar copias, sustituir/promover el modelo, reentrenar, cambiar reglas/esquema/credenciales o intervenir el principal queda fuera de esta autorización y requiere revisión/confirmación previa.

## Evidencias, respaldos y retorno

- `preparacion.json`: commit, hashes previos y ZIP privado nuevo con ACL restringida; también se revalidó el ZIP de cierre de fase 2.
- `copias.json`: fuente/destino/hash y conservación de originales.
- `validacion_*.json`: comandos/checks y códigos de salida. `*_final` es la revalidación del código definitivo.
- `importacion_canonica.json`: pruebas API, validación real, duplicados/BOM y rollback; sin tokens/passwords.
- `imagen_y_mounts_final.json`: empaquetado, exclusiones, exportación no-root y rechazo de sobrescritura.
- `verificacion_final.json`: hashes, equivalencia de casos de tests previos, 31 pruebas nuevas, cobertura, guards/ignore y volúmenes no usados.
- `runtime/test-results/fase-03/`: logs, JUnit y cobertura crudos ignorados en Git. Sus hashes se registran y se incluyen en respaldo privado de cierre, no en frontend público.
- `respaldo_cierre.json`: ZIP privado adicional de código/archivos resultantes y evidencias crudas, con hash y CRC. Los respaldos siguen en el mismo equipo; se recomienda una copia externa cifrada independiente.

No ejecutar scripts de preparación/centralización como bootstrap sobre una entrega ya aplicada: rechazan destinos/evidencias existentes. Los comandos operativos reales están en `data/README.md`. No existe todavía el pipeline/bootstrap objetivo de fases 6/9.

**Retorno:** conservar cualquier trabajo posterior; usar `a5a1f5f`, el ZIP previo y manifiestos para revertir solo herramientas/referencias/ignore de esta entrega. Las fuentes CSV y el artefacto activo siguen en sus rutas previas y respaldadas; no hace falta restaurar BD. No eliminar las únicas muestras ni usar `reset --hard`, `down -v` o limpieza recursiva. Las nuevas copias pueden permanecer preservadas sin conectarlas a inferencia.

**Continuación:** fase 4 — límites internos y transacciones backend, en entrega separada. Esta fase 3 no la implementa ni autoriza cambios de esquema/negocio implícitos.
