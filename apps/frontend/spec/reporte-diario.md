# REP-01 · Reporte diario

Recepción abre el reporte en `/panel/reporte-diario` desde el Panel Operativo o por URL directa. El enlace del Panel hereda su fecha y especialidad aplicadas. «Volver al panel operativo» restaura la ubicación de origen permitida, incluida la categoría y página de pendientes. Desde un enlace directo, el regreso apunta a `/panel`.

La fecha inicial corresponde a Lima. Los filtros de fecha, especialidad y riesgo se aplican mediante formulario y quedan en la URL. Se usa el cliente autenticado existente para consumir [el contrato REP-01](../../backend/spec/rep-01.md). Se distinguen la carga, el día vacío, el error de consulta y una respuesta incompatible. El reintento conserva los filtros aplicados y el cliente descarta las respuestas obsoletas.

La pantalla presenta el total, las tablas por especialidad y franja y sus subtotales. La hora se muestra tal como viene de la API, en hora local de Lima. La interfaz distingue una probabilidad de cero, una cita sin evaluación, una cita sin intervención y una intervención sin respuesta. Las tablas tienen encabezados accesibles y un contenedor con desplazamiento horizontal para pantallas estrechas.

La vista cubre la consulta. Exportación, impresión y despliegue al piloto conservan su alcance separado.

## Validación

TypeScript, ESLint y compilación de producción aprobados. Vitest registró **79 pruebas focalizadas aprobadas** entre REP-01, Panel, rutas de la aplicación y retorno desde detalles. Se verificaron los permisos, la fecha de Lima, los filtros, los nulos, la recuperación tras errores y el descarte de respuestas anteriores. La ejecución fue focalizada.

En Chromium, con el frontend compilado, el backend real y PostgreSQL temporal con datos sintéticos, Recepción inició sesión y abrió el reporte desde el Panel. El total y la cantidad de filas visibles coincidieron con las 17 citas devueltas por la API para Cardiología. También se verificaron el resultado vacío al filtrar por riesgo bajo, el regreso al contexto original y el bloqueo de acceso directo para Administración. A 390 px, con la navegación plegada, el desplazamiento horizontal quedó dentro de la tabla. La tecla Tab movió el foco del filtro de especialidad al de riesgo.
