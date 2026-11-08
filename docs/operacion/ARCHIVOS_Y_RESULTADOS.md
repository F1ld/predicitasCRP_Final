# Archivos, modelo legacy y resultados locales — fase 3

## Modelo activo frente a copia de preservación

- La inferencia integrada **sigue leyendo** `apps/backend/app/modules/ia/artifacts/modelo_predicitas_v1.joblib`.
- `artifacts/models/legacy-import/modelo_predicitas_v1.joblib` es una copia byte a byte del artefacto local confiable ya respaldado. Tiene atributo de solo lectura en Windows; eso evita escrituras accidentales, **no acredita aislamiento de seguridad**.
- No se carga esa copia, no se promueve, no se crea `active.json`, no se cambia versión ni se reentrena. El hash prueba integridad, no confianza de un Joblib arbitrario. No admitir modelos externos.
- Origen, hashes, permisos observados y linaje desconocido están en `data/manifests/inventario-fase-03.v1.json`. Este inventario **no sustituye** los manifiestos aprobados de dataset/modelo de fase 6. Raw/splits/fecha original desconocidos permanecen null.
- Los modelos y reportes generados en `artifacts/` se ignoran en Git y quedan fuera de los contextos Docker oficiales. La copia activa integrada todavía debe empaquetarse en backend hasta fases 5–7: no excluirla ni retirarla ahora.

## Runtime y pruebas visuales

- `runtime/exports/`: salida CLI explícita; no retención nueva de descargas API.
- `runtime/tmp/`: temporales autorizados, sin limpieza automática en esta fase.
- `runtime/test-results/`: cobertura, resultados y QA nuevo; no Git ni imágenes.
- `runtime/test-results/diseno/<id>/fixtures/` y `manifest.json`: nuevas salidas de `apps/frontend/tests/validar_diseno.py`. IDs exclusivos: una ejecución no sobrescribe la evidencia de otra.
- `PREDICITAS_TEST_RESULTS_DIR` permite otra base **absoluta** fuera de OneDrive. Si está dentro del repositorio debe pertenecer a `runtime/test-results/`. No aceptar rutas relativas ni traversal como ID de ejecución.

Los CSV existentes en `apps/frontend/tests/fixtures/`, `ultima_validacion_diseno.json`
y capturas históricas quedan intactos. Solo se cambian las rutas de salidas futuras.
El QA legacy debe ejecutarse con venv/backend y BD de pruebas aislada configurados
**antes de importarlo**; no conectarlo al principal ni prometer que sus flujos previos
están libres de defectos. Debe establecerse `PREDICITAS_QA_DATABASE_NAME` con el nombre
exacto de la BD test/qa; una guarda rechaza principal o nombres no confirmados antes de
abrir conexión. La guarda es protección adicional, no sustituye inspeccionar la URL.
Fase 3 prueba los helpers de rutas/guarda y no certifica ese E2E visual.

`artifacts`, `runtime`, `data/raw` y `data/processed` se crean localmente; Git no conserva
directorios vacíos. Sus responsabilidades están documentadas; la preparación automática
de un equipo limpio corresponde al bootstrap de fase 9. No añadir datasets ficticios para
rellenar carpetas ni `.gitkeep` en `Skills/`.

## Actualización QA — migraciones D de fase 6

El runner de diseño ya no genera citas dentro del backend: lee tres CSV
sintéticos versionados de `apps/frontend/tests/fixtures/generados-v1/`, o un
bundle absoluto mediante `PREDICITAS_QA_FIXTURES_DIR`, verificando sus hashes.
Reasigna únicamente prefijos para aislar ejecuciones. Los payloads son del
contrato operacional de 13 columnas, sin features/target extra; se conservan
45/4 y 20/4 aceptadas/rechazadas como casos de QA, no como garantía para una BD
con duplicados. Antes de escribir se exige la misma guarda de BD test/qa.

La generación de muestras arbitrarias ahora vive en IA (`datasets.exportar_csv`).
Los fixtures históricos y capturas anteriores no se sobrescriben. La validación
ASGI de payloads no equivale a haber validado visualmente el navegador.
[Invocaciones, datos y resultados D](../migracion/fase-06/MIGRACIONES_D.md).

## Actualización E — camino limpio de fase 6

La ejecución `e-20261107-01` validó el paquete limpio y las imágenes en un
laboratorio PostgreSQL nuevo; no se modificaron los archivos de datos ni el
modelo activo. La evidencia portátil está en
[`evidencia/e-20261107-01/resumen.json`](../migracion/fase-06/evidencia/e-20261107-01/resumen.json)
y el detalle en [BLOQUE_E.md](../migracion/fase-06/BLOQUE_E.md). El laboratorio
propio quedó detenido; su volumen y red se preservan para diagnóstico y no
forman parte de la BD operativa.
