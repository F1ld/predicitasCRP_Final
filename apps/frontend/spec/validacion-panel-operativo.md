# Validación del frontend del Panel Operativo

Fecha: 09/11/2026. Alcance: pantalla `/panel`, descubrimiento por ranuras, inicio
por rol y retorno directo desde Cita, Seguimiento y Cupo. No desplegado al piloto.

## Resultados automatizados

| Comprobación | Resultado |
|---|---|
| TypeScript (`npm run typecheck`) | Aprobado. |
| ESLint (`npm run lint`) | Aprobado. |
| Producción (`npm run build`) | Aprobado, sin dependencias nuevas. |
| Suite focalizada de Panel, retorno, App, Login, M01, Seguimiento y DetalleCupo | **170 aprobadas, 0 fallos**. |
| Suite completa, 584 casos | **525 aprobados y 59 fallos preexistentes; 0 regresiones nuevas** frente a la copia del checkout anterior a esta entrega. La suite global no está verde. |
| Cobertura global de líneas | **92,46 %**, supera el umbral vigente de 75 %, sin reducirlo. |

La copia baseline se tomó antes de crear el módulo, conservando los cambios
previos del workspace: **515 casos, 456 aprobados y 59 fallidos**. La ejecución
final contiene 69 casos adicionales. Los fallos previos se repiten en:

| Archivo | Fallos |
|---|---:|
| `src/modulos/citas/Detalle.test.tsx` | 40 |
| `src/modulos/citas/citas.test.tsx` | 17 |
| `src/modulos/sesion/MiCuenta.test.tsx` | 1 |
| `src/nucleo/componentes/componentes.test.tsx` | 1 |

La comparación usa archivo, nombre de caso y multiplicidad; nombres de casos
repetidos no deben colapsarse para aparentar menos fallos. No se cambiaron,
omitieron ni desactivaron esos casos para aprobar la entrega del panel.

La suite global se ejecutó con `npm test -- --maxWorkers=2
--coverage.reportOnFailure=true --reporter=json --outputFile=...`. La opción
`reportOnFailure` permite conservar el informe de cobertura aun con fallos; no
los ignora ni cambia el código de salida. El resultado global es código 1.
La suite focalizada se ejecutó sin cobertura global para iterar sobre el alcance.

Los tests automatizados comprueban URL, hoy de Lima, offsets, filtros diferidos,
actualización con universo aplicado, categorías, estados nulos/ceros, errores
parciales, contrato incompleto, cancelación de consultas antiguas y retorno de los
tres detalles con éxito, error y recurso ausente. Hay pruebas específicas del
helper de retorno y de validación de proyecciones mínimas sin campos de detalle.

La cobertura del contenedor del panel es 92,30 % de líneas; filtros, tablas,
resúmenes, URL, formato y validación estructural alcanzan 100 %. No se afirma
100 % de cobertura de todo el módulo: los archivos de ranuras aparecen con
cobertura 0 % en el informe de Vite, aunque se verifica su descubrimiento y
protección mediante App y el recorrido real.

## Recorrido con backend real

Se creó un laboratorio temporal con PostgreSQL 16, base
`predicitas_panel_ui_test` en tmpfs y los schemas/migraciones actuales. El API
se ejecutó desde el código del repositorio montado en solo lectura y se publicó
únicamente en `127.0.0.1:18009`; Vite temporal en `127.0.0.1:5179`. No se
modificaron `.env`, backend, contratos, datos del piloto ni artefactos IA.

Datos sintéticos: 34 citas, 30 predicciones, 6 intervenciones, 4 cupos y tres
usuarios de prueba. Resultado observado: 24 citas sin intervención, 6
intervenciones sin respuesta, 1 oferta en curso, 2 cupos disponibles y 25 %
de recuperación (1 de 4). No hubo inferencias, mensajes ni reasignaciones desde
el panel durante el recorrido.

Comprobaciones en navegador:

- Inicio de Recepción y Administración en Panel después del login real.
- Técnico IA mantiene Citas y no puede abrir Panel por URL directa.
- Menú del panel visible y activo solo en roles autorizados.
- Los cuatro indicadores coinciden con el backend del laboratorio.
- Paginación de citas: «Mostrando 1–20 de 24» y «21–24 de 24».
- Apertura de Cita, Seguimiento y Cupo, retorno con fecha, categoría y página.
- Especialidad aplicada mediante formulario y actualización de ambos recursos.
- Fecha sin registros muestra vacío y «Sin cupos liberados», no un error.
- Navegación por teclado entre categorías con foco en el siguiente botón.
- Sin errores de consola de la aplicación observados durante la revisión.

## Revisión adaptable

| Ancho | Tarjetas | Resultado |
|---|---|---|
| 1440 px | Cuatro columnas | Sin desbordamiento horizontal de documento. |
| 1024 px | Dos columnas | Filtros/categorías adaptados, sin desbordamiento horizontal global. |
| 390 px | Una columna | Con menú plegado usando su control existente; sin desbordamiento horizontal global. |

En móvil, la tabla conserva ancho de contenido 680 px dentro de un contenedor
local de 259 px con scroll propio. Se conserva el comportamiento del menú
existente al redimensionar; no se modificó Layout para cerrar automáticamente un
menú que ya estaba abierto en escritorio.

Se guardaron capturas de escritorio, tablet y móvil. Las capturas de página
completa pueden reproducir la posición de elementos fijos al capturar una página
ya desplazada; para la evidencia principal se usa la captura de escritorio desde
el inicio, `panel-escritorio.jpg`.

## Evidencia local y salvedades

Resultados bajo `runtime/panel-frontend` (ignorado por Git):

- `baseline-vitest.json` y `baseline.log`: estado anterior aislado.
- `focal-final.json`: 170 casos focalizados aprobados.
- `integrada-vitest.json`, `integrada-vitest.log` y `comparacion.json`: suite
  global y contraste con el baseline.
- `panel-escritorio.jpg`, `panel-tablet.jpg` y `panel-movil.jpg`: capturas.
- Cobertura HTML/JSON en `apps/frontend/coverage`.

La primera ejecución de baseline no pudo completar pruebas por el renombrado de
archivos temporales bajo el sandbox de Windows; se repitió con TMP/TEMP dentro
del workspace y produjo el baseline citado. La prueba inicial de navegador no
alcanzó al Vite aislado; se reinició el servidor temporal fuera de ese aislamiento
de red y el recorrido posterior funcionó. No se cambiaron protecciones del sistema.

Persisten los 59 fallos previos descritos. No se acredita aceptación integral del
frontend ni cierre de esa deuda por implementar el Panel. REP-01, contexto de
recorridos secundarios de varios niveles y despliegue quedan fuera del alcance.
Los servicios y la red de laboratorio se retiran al cerrar esta tarea.
