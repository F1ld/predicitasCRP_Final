# Validación del backend del Panel Operativo

Fecha: 09/11/2026. Implementación conforme a [panel-operativo.md](panel-operativo.md).

## Entorno y límites de la validación

- Python 3.12.16, SQLAlchemy 2.1.4 y pytest 9.1.1 de la imagen backend local existente.
- PostgreSQL 16 en contenedor nuevo, base `predicitas_panel_test`, sin puertos
  publicados ni volumen persistente; datos en tmpfs. Migraciones existentes hasta
  `m01_001_indices_auditoria`, sin migraciones nuevas.
- Suite funcional con `predicitas_app`, conservando las políticas y restricciones
  existentes. Cuenta propietaria solo para migración y medición de planes con `ANALYZE`.
- IA de pruebas aislada con el artefacto existente montado en solo lectura. No se
  entrenó, promovió ni modificó el modelo. El panel no requiere contactarlo.
- Montaje del repositorio en solo lectura para las ejecuciones; resultados en
  `runtime/panel-backend`. No se usó ni modificó la base operativa del piloto.
- Contenedores y red temporales retirados al terminar. Ningún cambio desplegado.

## Resultados

| Verificación | Resultado |
|---|---|
| Suite completa con cobertura (`python -B -m pytest -q -p no:cacheprovider --cov-report=xml:... --junitxml=...`) | **511 passed, 2 skipped, 0 fallos**, 166,07 s. |
| Cobertura global de `app` | **94,28 %**, supera el umbral vigente de 75 %. No se desactivó el gate. |
| Cobertura de `app/modules/panel` | **100 %** de statements en consultas, router, schemas y service. |
| Casos del panel dentro de la suite completa | **110 aprobados**. |
| Revisión final de `tests/panel/test_pendientes.py` tras ampliar comprobaciones de empate y eventos históricos de oferta | **67 aprobados**, sin cobertura global por ser repetición focalizada posterior a la suite completa. |
| OpenAPI frente al `main.py` de HEAD anterior a esta implementación | Solo dos rutas añadidas; rutas y schemas previos conservados estructuralmente. |
| Snapshot histórico `openapi.actual.v0.5.0.json` | Conservado; SHA-256 `F39DB2A15F5B10CC461F3E28CB386FB9B96AD6CAA7B98BFDC25D6D6289B59EAD`. |
| Fronteras/imports y controles de lectura | Aprobados dentro de la suite completa; excepción del adaptador declarada específicamente. |
| Escrituras e IA desde las lecturas del panel | Pruebas de sentencias y transportes: una consulta por respuesta, sin commits, DML, locks de escritura ni HTTP IA. |

Las dos omisiones corresponden a `test_arranque_recuperacion` y
`test_medir_lote_publico`, que exigen flags de laboratorios de arranque/carga de IA.
No son pruebas omitidas del panel. Las advertencias restantes son deprecaciones
existentes de Starlette/httpx, `regex` en reportes, `flush(objects)` y una opción de
cache al desactivar su plugin; no se modificaron dependencias para eliminarlas.

La primera ejecución completa, sin IA de laboratorio, detectó fallos de entorno
y dos ajustes de integración. Se corrigió el fixture de orden temporal de una
prueba de Intervenciones y se registró Panel en el control de fronteras. La
ejecución integrada final incluyó IA y terminó sin fallos. El caso de filtro bajo
en la consulta interna de elegibles también quedó restringido a alto/medio.

## Medición de consultas

Herramienta reproducible: `python -m scripts.validar_panel --salida ...`.
Requiere una base desechable con `panel_test` en su nombre y rol propietario.
Inserta datos sintéticos, obtiene planes `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`
y revierte los registros. No crea tablas, índices ni artefactos de modelo.

Volumen: 5.000 citas, 10.000 predicciones, 2.500 intervenciones y 500 cupos.
Incluye pacientes compartidos, oposición en intervenciones y más de una
predicción por cita. Se midieron todas las especialidades y Cardiología.

| Consulta | Todas las especialidades | Cardiología |
|---|---:|---:|
| Resumen | 63,60 ms | 48,30 ms |
| Citas sin intervención | 59,88 ms | 33,24 ms |
| Intervenciones sin respuesta | 23,49 ms | 28,86 ms |
| Ofertas en curso | 0,40 ms | 0,47 ms |

Son tiempos SQL observados de una ejecución local, no percentiles ni garantía
de latencia HTTP en producción. El plan inicial del listado de citas sin
intervención tardó 5.866,94 ms: PostgreSQL empujaba el filtro hacia la ventana de
predicciones y elegía nested loops con estimaciones bajas de cardinalidad.
Materializar el CTE `citas_con_riesgo` evitó esa expansión y redujo el tiempo sin
añadir índices. No se justificó una migración de índices para este volumen.

## Cambios de integración acotados

- Registro explícito del router en `app/main.py`.
- Lectura compuesta declarada en `app/bootstrap/limites.py`, documentación de
  arquitectura y prueba específica de frontera del panel.
- Control general de fronteras admite que Panel, como lector HTTP sin consumidor
  interno, no tenga un `public.py` vacío. Se conserva el control de imports ORM.
- Intervenciones selecciona la predicción por timestamp e ID antes de filtrar su
  riesgo; el servicio deja de sustituirla mediante otra consulta por fila.
- Una prueba antigua que llamaba «reciente» a una inferencia con fecha anterior
  a otra quedó con timestamps explícitos coherentes con su escenario.
- Sin cambios en persistencia de IA, catálogos, modelos ORM, transiciones,
  reintentos, consentimiento, opt-out, workflows, reportes o frontend.

## Evidencia local generada

Los siguientes archivos quedan bajo `runtime/panel-backend` (directorio ignorado
por Git). Este documento conserva el resultado aunque se retire ese laboratorio:

- `suite-integrada.xml`: JUnit de la suite final.
- `cobertura-integrada.xml`: cobertura final.
- `pendientes-final.xml`: comprobación focalizada posterior.
- `planes-panel.json` y `planes-panel-optimizados.json`: planes antes/después.
- `openapi-panel.json`: OpenAPI generado con las rutas nuevas.

La entrega acredita el backend y su contrato; no incluye frontend, REP-01,
consulta administrativa de auditoría ni aceptación integral del piloto.
