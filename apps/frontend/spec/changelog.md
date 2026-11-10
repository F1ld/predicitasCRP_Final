# Changelog del frontend

## 10/11/2026 — Diálogo de confirmación de reasignación

- La ventana de Cupos presenta el seudónimo del candidato, la cita de origen, la especialidad, el médico y la fecha, hora y franja antes de confirmar.
- Se reorganizaron los controles y las acciones con los colores y la animación de entrada existentes. La animación respeta la preferencia de movimiento reducido y la ventana se adapta a pantallas estrechas.
- Los errores recuperables de confirmación se muestran dentro de la ventana. Se conserva la confirmación humana y el medio como requisitos para registrar la reasignación.
- Validación: 140 pruebas focalizadas aprobadas, lint y build correctos. El recorrido en Chromium revisó el diálogo a 1280 y 390 px, la preferencia de movimiento reducido y la confirmación con persistencia tras recargar.

## 10/11/2026 — Pruebas de previsualización de plantillas

- Actualizada la prueba de Nueva intervención para comprobar que el formulario presenta el texto literal recibido de la API y cambia la previsualización al elegir otro canal.
- Validación de la actividad 3 del EDT 3.3.4.9 en Chromium con la imagen desplegada `2c10706e7748`. Recepción previsualizó los cinco textos, verificó que el formulario sin consentimiento no creó ninguna intervención y completó el seguimiento desde Pendiente hasta la liberación. La reasignación persistió al recargar y se comprobó en REP-01, REP-02 y REP-03.

## 09/11/2026 — Validación del flujo operativo en navegador

- Reconstruido el frontend local con las correcciones de Citas y el enlace al cupo liberado.
- Aprobado el recorrido de Recepción en Chromium con las imágenes Docker de la aplicación y datos sintéticos aislados. [Evidencia y alcance](validacion-flujo-operativo.md).

## 09/11/2026 — Integración de Citas, Intervenciones y Cupos

- El aviso de liberación de Intervenciones enlaza al detalle del cupo que confirmó el servidor.
- El detalle de Citas ofrece el mismo acceso a Recepción y Administración cuando la cita tiene un cupo liberado. Las pruebas verifican el destino y que el enlace se omite ante un fallo de liberación o un rol sin acceso a Cupos.
- Validación: 380 pruebas focalizadas de Citas, Intervenciones, Lista de espera y retorno al Panel aprobadas. Lint y compilación de producción aprobados.

## 09/11/2026 — Estabilización de Citas

- Alineadas las pruebas de Detalle, cambios de estado, check-in, inferencia e importación CSV con la interfaz vigente. Se mantienen las comprobaciones de permisos, datos enviados, errores y envíos duplicados.
- La reprogramación envía la fecha y hora acordadas en Lima con el desplazamiento explícito, independientemente de la zona horaria del navegador.
- El detalle usa una sola solicitud de inferencia por acción y adapta los decimales y el indicador de simulación del contrato de la API. Una respuesta de error conserva su mensaje y evita un segundo POST automático.
- Validación: 143 pruebas de Citas aprobadas con `TZ=UTC`. Suite completa del frontend con 599 aprobadas, 2 fallos preexistentes fuera de Citas (Mi Cuenta y componentes compartidos) y 96,91 % de cobertura de líneas. Lint y compilación aprobados.

## 09/11/2026 — Correcciones de Citas

- Restaurado el rótulo de resultado simulado junto al riesgo en la Bandeja, según `resultado_simulado`.
- El detalle de predicción muestra «Sin explicación registrada» si faltan factores y conserva los factores devueltos por el modelo.
- El aviso al abrir una cita desde Intervenciones usa el nombre de la acción vigente y muestra solo el origen cuando el rol o el estado impiden confirmar. Se conserva la preselección de la intervención válida.
- Validación de Citas con Vitest: 89 aprobadas y 54 fallos preexistentes, frente a 78 aprobadas y 57 fallos en el diagnóstico anterior. Lint y compilación aprobados.

## REP-01 · Reporte diario

- Agregada la vista para Recepción con entrada desde el Panel, retorno al contexto de origen, filtros en URL y tablas por especialidad y franja.
- [Comportamiento y alcance](reporte-diario.md).

## 09/11/2026 — Panel Operativo de Recepción

- Creado `src/modulos/panel`: pantalla `/panel`, cuatro tarjetas, desgloses y
  categorías de citas sin intervención, intervenciones sin respuesta y ofertas.
- Integrados los dos GET del backend con estados de carga/error/reintento
  independientes, comprobación estructural local y cancelación de respuestas
  obsoletas mediante la infraestructura existente.
- Filtros de jornada/especialidad, categoría y página en URL; 20 filas por página,
  hoy en Lima, borrador separado de filtros aplicados y actualización manual.
- Presentación diferenciada de recuperación sin denominador, riesgo sin
  predicción, contadores de resumen y total real de la lista. Sin polling,
  cálculo de elegibilidad, inferencia, exportaciones o escrituras desde el panel.
- Registradas ruta y entrada de menú por las ranuras existentes para Recepción y
  Administración. Login ahora pasa por `/` para resolver el inicio por rol en vez
  de enviar siempre a Citas; Técnico IA conserva su destino previo.
- Añadido helper de retorno interno y adaptados únicamente los enlaces de
  regreso de Cita, Seguimiento y Cupo. Se conserva el contexto directo del panel
  y los fallbacks anteriores sin cambiar formularios o workflows de negocio.
- Estilos propios adaptables, fechas explícitas de Lima, navegación por teclado
  y scroll local de tablas. Sin cambios en Layout, App, estilos globales,
  dependencias, cliente API compartido, backend o configuración del piloto.
- Añadidas pruebas y actualizadas las expectativas de inicio en App/Login/M01.
  **170 pruebas focalizadas aprobadas**; tipos, lint y build aprobados.
- Suite global: **525 aprobadas y 59 fallos preexistentes**, mismos casos del
  baseline, sin regresiones nuevas. Cobertura de líneas **92,46 %**; el umbral
  permanece en 75 %. No se declara la suite global completamente aprobada.
- Verificado el recorrido HTTP con backend/PostgreSQL temporales: tres roles,
  indicadores, categorías, paginación, filtros, vacío y retorno de tres detalles.
  Revisado a 1440, 1024 y 390 px. No desplegado al piloto.
- Especificación conservada en [panel-operativo.md](panel-operativo.md).
  Evidencia y límites en [validacion-panel-operativo.md](validacion-panel-operativo.md).
