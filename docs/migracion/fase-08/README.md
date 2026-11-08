# Fase 8 — inventario y consolidación del frontend

Punto de retorno de código y de la imagen operativa anterior: `8bc3cf3`.
La entrada es `index.html → src/main.tsx → App.tsx`. App descubre
`modulos/*/rutas.tsx`; Layout descubre `modulos/*/menu.ts`. El análisis de
imports no encontró consumidores activos de las cuatro carpetas antiguas.

| Código anterior | Equivalente en el árbol modular |
| --- | --- |
| Login y sesión, guardas y layout | `modulos/sesion`, `nucleo/auth`, `nucleo/sesion` y `nucleo/layout` |
| Bandeja, detalle e importación de citas | `modulos/citas`, con registro y trazabilidad; se conserva `/importar` |
| Intervenciones y cálculo de riesgo por lote | `modulos/intervenciones`; se recupera el POST de lote para escritores en Elegibles |
| Reasignación y lista de espera | `modulos/lista-espera`, con redirect de `/reasignacion` a `/cupos` |
| Modelo IA | Nueva ranura `/ia`, antes sin equivalente modular; métricas, dataset, matriz y variables |
| Componentes y utilidades | `nucleo/componentes`, `nucleo/formato`, `nucleo/api` y transiciones de Citas |

Se retiraron 21 archivos de las carpetas antiguas tras comprobar sus
consumidores. La fixture de ranuras se carga desde `src/pruebas` solo
en modo de pruebas. REP-02 y REP-03 usan el mismo transporte que JSON,
con respuesta Blob, nombres y tipos de archivo preservados. Un fallo de IA
en el lote deja disponible la bandeja de intervenciones; el panel de
Modelo IA ofrece reintento y muestra el rótulo sintético.

## Línea base

La primera ejecución en Windows falló antes de coleccionar por permisos
de renombrado del directorio temporal. El contenedor de referencia de
fase 7 reprodujo 56 fallos en dos suites de Citas, con 451 pruebas
aprobadas. Las pruebas en contenedores se ejecutaron sin red, sin el
volumen PostgreSQL y con etiquetas distintas a la imagen operativa.

## Validación del candidato

Pasaron el typecheck, lint, build y 71 pruebas focales. Se comprobó que
el bundle no contiene la ruta de prueba. La suite completa dio
455 aprobadas y 56 fallos. La
comparación por nombre de archivo y caso detectó 0 fallos nuevos
y 0 casos previos corregidos. En esta prueba, el candidato se mantuvo separado
del frontend operativo.

[Resumen comparativo](resumen.json).

## Cierre con salvedades (08/11/2026)

El usuario confirmó la navegación con Administrador, Recepción y Técnico IA
y el funcionamiento de la importación CSV. Se conserva visible el botón
«Calcular riesgo por lote» y se difiere su revisión. También se difieren los
56 fallos históricos de las pruebas de Citas y el error reportado al asignar
un cupo liberado.

Se promovió la imagen `predicitas-frontend-fase8:20261108-02` al servicio
oficial `predicitas-frontend`. Respondió HTTP 200 en localhost:5173. Se
comprobó que backend, PostgreSQL e IA conservaron sus contenedores y sus
horas de arranque. La imagen anterior se conserva con la etiqueta local
`predicitas-frontend-retorno:8bc3cf3`. Para volver, etiquetarla como
`predicitas-crp-frontend:latest` y recrear solo el frontend con los mismos
archivos Compose y `up -d --no-deps --no-build --pull never frontend`.
