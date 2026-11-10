# Changelog del backend

## 10/11/2026 — Auditoría de exportaciones de REP-03

- REP-03 y su alias registran un evento `REPORTES / EXPORT / rep-03` por cada CSV o XLSX generado correctamente. El evento conserva usuario, fecha, IP, formato y filtros solicitados.
- El caso de uso confirma la auditoría después de generar el archivo y antes de responder. Las consultas JSON, los rechazos y los fallos de generación quedan fuera del registro de exportación.
- Validación en PostgreSQL desechable: 59 pruebas aprobadas. Se verificó un único evento por exportación en ambas rutas y formatos, con usuario y filtros correctos, y cero eventos ante accesos denegados, formato inválido y errores de generación.
- Actividad 3 del EDT 3.3.4.11 validada en Chromium con la imagen desplegada `1ce601b37e5f`. Se descargaron CSV y XLSX con un resultado filtrado y con resultado vacío. Los archivos coincidieron con la consulta, se verificaron cuatro eventos de auditoría y los rechazos 401 y 403 quedaron fuera de ese registro.

## 10/11/2026 — Exportación Excel de REP-03

- `GET /reportes/rep-03?formato=xlsx` y su alias entregan un libro Excel válido generado con el exportador compartido. Las filas proceden de la misma consulta filtrada y mantienen las columnas de la exportación existente.
- Se conserva la descarga CSV con sus encabezados, BOM y nombre. La auditoría de exportación corresponde a una actividad separada.
- Validación en PostgreSQL desechable: 42 pruebas aprobadas. Se abrió el XLSX con openpyxl, se compararon sus filas con el JSON filtrado y se verificaron el alias, el libro vacío y la descarga CSV.

## 10/11/2026 — Creación de Intervenciones unificada

- `POST /intervenciones` y `POST /citas/{id_cita}/intervenciones` aplican el mismo caso de uso. Ambas rutas exigen consentimiento booleano verdadero, plantilla compatible y cita elegible, respetan opt-out y límite de reintentos, y crean en `PENDIENTE`.
- El alias conserva HTTP 200 y obtiene la cita de la URL. Si el cuerpo también incluye un ID diferente, devuelve 422. La ruta principal conserva HTTP 201 y recibe el ID en el cuerpo.
- Los clientes del alias deben confirmar el consentimiento y registrar el envío en un paso separado. Las pruebas comparan ambas rutas y verifican que los rechazos no creen intervenciones ni eventos de alta.
- Validación en laboratorio con PostgreSQL 16: 216 pruebas aprobadas. El recorrido desde el alta de la cita hasta la reasignación pasó con el motor real `LightGBM_v1.0.0`.
- Cierre técnico de la actividad 3 del EDT 3.3.4.9. Sobre la imagen desplegada `77a8cd121e1e` pasaron 71 pruebas de Intervenciones y Reasignación. La verificación cubrió ambas rutas de alta y los rechazos sin escrituras. El recorrido en Chromium con esa imagen llegó a la liberación, la reasignación y los tres reportes en un PostgreSQL desechable.

## 10/11/2026 — Plantillas de Intervención Inteligente

- Reemplazado el marcador provisional del catálogo por cinco textos estáticos de previsualización para el piloto simulado: confirmación y liberación en WhatsApp y SMS, y guion telefónico. Se conservan los identificadores y las combinaciones admitidas por canal.
- Las pruebas del catálogo verifican las cinco variantes, sus permisos y la longitud breve de los SMS.

## 09/11/2026 — Seudónimo al consultar una reasignación

- La respuesta de reasignación y el detalle de Cupos incluyen `paciente_anon_id` del candidato asignado. El detalle conserva ese dato al recargar. Cambio aditivo en las respuestas, sin migraciones.
- Agregadas comprobaciones del seudónimo tanto al confirmar como al consultar el cupo de nuevo.
- Validación en PostgreSQL temporal: 21 pruebas de ofertas y reasignación aprobadas. La recarga del detalle y la consulta de reportes se verificaron con la misma imagen candidata en [el recorrido de navegador](../../frontend/spec/validacion-flujo-operativo.md).

## 09/11/2026 — Verificación de integración de Citas a Reasignación

- Agregado `python -m scripts.validar_integracion_citas` para comprobar las rutas de alta manual, predicción, elegibilidad, intervención, liberación, oferta y confirmación en una base temporal recién migrada. El verificador exige la base `predicitas_integracion_test` en loopback, sin usuarios previos.
- Comprueba permisos, rechazo de liberación duplicada y de reasignación sin confirmación humana, persistencia de los estados e historial, y una entrada de auditoría por operación clave.
- Ejecución aprobada con PostgreSQL 16 desechable y el motor real `LightGBM_v1.0.0`. La cita sintética obtuvo riesgo alto, habilitó Intervenciones y su cupo terminó reasignado. El laboratorio se retiró al concluir.

## REP-01 · Consulta del reporte operativo diario

- Agregado `GET /reportes/rep-01` para Recepción, con fecha de Lima, filtros por especialidad y riesgo, y subtotales por especialidad y franja.
- Selección determinista de la predicción y la intervención más recientes por cita en una sola lectura.
- [Contrato, reglas y validación](rep-01.md).

## 09/11/2026 — Panel Operativo de Recepción

- Implementados `GET /panel/resumen` y `GET /panel/pendientes`, autorizados para
  Recepción y Administración, con filtros por fecha de Lima y especialidad.
- Agregados de citas, riesgo único por cita, intervenciones y cupos; recuperación
  basada en reasignación humana confirmada. Pendientes tipados, con paginación,
  total completo, opt-out transversal y exclusión de horarios vencidos.
- Una sentencia/snapshot por respuesta, sin escrituras, inferencia ni tablas
  nuevas. Optimización del CTE de riesgo sin índices o migraciones nuevos.
- Alineada selección de predicción en Intervenciones con Citas; preservados
  estados intervenibles, consentimiento, opt-out y límites de reintento.
- Registradas dependencias de lectura y rutas. Contrato incremental nuevo sin
  modificar el snapshot histórico de OpenAPI ni contratos previos.
- Añadidas pruebas de Panel, regresión y herramienta de medición SQL aislada.
- Validación: **511 aprobadas, 2 omitidas por laboratorio IA específico, 94,28 %
  de cobertura global y 100 % en Panel**; 67 pruebas focalizadas adicionales
  aprobadas tras ampliar comprobaciones de pendientes.
- Medición local con 5.000 citas y 10.000 predicciones: resumen ~64 ms y listado
  de citas sin intervención ~60 ms. No equivale a un SLA de producción.
- Definición trasladada desde ToDo a [panel-operativo.md](panel-operativo.md).
  Evidencia y límites: [validacion-panel-operativo.md](validacion-panel-operativo.md).
- No se desplegó al piloto ni se modificó frontend, datos operativos, reportes o
  artefactos del modelo.
