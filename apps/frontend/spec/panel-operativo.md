# Especificación del frontend del Panel Operativo

Definición funcional y técnica conservada tras implementar la pantalla. Los resultados y salvedades se registran en validacion-panel-operativo.md y changelog.md; los pendientes activos se mantienen en ToDo.md.

## Panel Operativo de Recepción — especificación de implementación

- Fecha de definición: **09/11/2026**, zona de negocio `America/Lima`.
- Estado: **implementado y validado en entorno aislado**, con la salvedad de 59 fallos preexistentes en la suite global. La evidencia no acredita un despliegue al piloto. Ver [validación](validacion-panel-operativo.md).
- Objetivo: dar a Recepción y Administración una pantalla inicial que permita conocer la jornada seleccionada, revisar pendientes y continuar las acciones en los detalles existentes.
- Ruta propuesta: **`/panel`**, dentro del Layout autenticado actual.
- Backend disponible en código: **`GET /panel/resumen`** y **`GET /panel/pendientes`**. Su despliegue al ambiente donde se pruebe la interfaz debe verificarse antes de la integración HTTP.
- Referencia: [contrato incremental v1](../../../contracts/backend/panel.v1.md), [schemas ejecutables](../../backend/app/modules/panel/schemas.py) y [especificación del backend](../../backend/spec/panel-operativo.md).

### 1. Alcance funcional y entregables

#### 1.1 Qué se implementará

- [x] Pantalla inicial de Panel Operativo para `RECEPCION` y `ADMINISTRADOR`.
- [x] Entrada de menú «Panel operativo», ordenada antes de Citas.
- [x] Filtros de fecha y especialidad, persistidos en la URL.
- [x] Cuatro tarjetas de resumen: citas, riesgo alto/medio, disponibilidad de cupos y recuperación.
- [x] Bandeja integrada con tres categorías de pendientes y una tabla visible a la vez.
- [x] Paginación de 20 registros usando el total del servidor.
- [x] Desgloses de citas por estado, riesgo y estado de intervenciones.
- [x] Carga, error, reintento, vacío y éxito por bloque, sin convertir errores en ceros.
- [x] Actualización manual y cancelación de solicitudes obsoletas.
- [x] Accesos a detalles existentes, con regreso al panel y conservación de contexto.
- [x] Formato de fechas y horas del panel explícitamente en Lima.
- [x] Diseño adaptable a escritorio, tablet y móvil, con controles accesibles.
- [x] Pruebas de la pantalla, navegación, filtros, contratos simulados y retorno desde detalles.
- [x] Validación de tipos, lint, build, suite y recorrido visual/HTTP contra un backend de pruebas compatible.

#### 1.2 Qué no se implementará ni modificará por esta tarea

| Área | Exclusión |
|---|---|
| Backend | No cambiar consultas, indicadores, schemas, reglas, roles ni endpoints ya definidos. Si aparece una incompatibilidad, documentarla y resolver su alcance antes de alterar el contrato. |
| Operaciones | No crear, editar, enviar, confirmar, liberar, ofertar ni reasignar desde el propio panel. Sus filas abren los detalles existentes. |
| Cálculo de negocio | No reconstruir elegibilidad, opt-out, estados activos, elección de predicción ni tasas a partir de bandejas descargadas. El servidor determina esas reglas. |
| Reportes | No implementar REP-01 ni exportaciones nuevas, PDF, Excel o impresión. No mostrar botones que aparenten un reporte disponible si aún no existe. |
| Auditoría/IA | No crear el visor de auditoría, restaurar Modelo IA, entrenar, predecir ni cambiar el modelo o sus umbrales. |
| Vistas operativas | No rediseñar Citas, Intervenciones, Seguimiento, Cupos o Lista de espera; solo incorporar el retorno acotado desde los detalles afectados. |
| Navegación general | No rehacer `App`, `Layout`, el menú lateral, autenticación ni la gestión de sesión. Usar las ranuras actuales. |
| Estilos globales | No cambiar marca, tipografía, paleta, logo, barra lateral, cabecera, pie ni reglas globales de tablas/tarjetas. |
| Tiempo global | No cambiar la zona horaria de todas las pantallas ni el comportamiento de `RelojLocal`. El formato explícito de Lima se aplica al módulo del panel. |
| Dependencias | No añadir bibliotecas de gráficos, tablas, fechas, estado, solicitudes o animaciones. |
| Actualización | No incorporar polling, WebSockets, service workers, refresco por intervalos, notificaciones o actualización automática de contadores. |
| Persistencia local | No guardar respuestas clínicas/operativas en localStorage, caches persistentes o nuevas claves de sesión. La URL conserva únicamente el contexto de navegación. |
| Históricos | No mostrar tendencias, comparativas con ayer, variaciones porcentuales, metas o reconstrucciones históricas que la API no entrega. |
| Despliegue | No reconstruir ni recrear el stack operativo del piloto como parte de construir la pantalla. La entrega de código y las pruebas aisladas no equivalen a un despliegue. |

### 2. Estructura de la pantalla

Orden de lectura y de foco, compartido por escritorio y móvil:

1. Título y descripción de la pantalla.
2. Filtros de jornada y controles de actualización.
3. Referencia de fecha, especialidad y hora de consulta del resumen.
4. Cuatro tarjetas de resumen.
5. Categorías de pendientes, tabla y paginación.
6. Desgloses de la jornada.

No agregar otra pantalla independiente de «dashboard», modal de bienvenida ni submenú para cada categoría. Los pendientes pertenecen a `/panel`; su categoría se representa mediante query string.

#### 2.1 Cabecera

- Título principal único: **«Panel operativo»**.
- Descripción breve: **«Resumen de la jornada y tareas pendientes de atención.»**
- Reutilizar el patrón `pagina-titulo` y los componentes visuales actuales.
- Mostrar la fecha aplicada y especialidad consultada; «Todas las especialidades» cuando el filtro no existe.
- Mostrar **«Resumen consultado a las HH:mm»**, basado en `resumen.generado_en` y con indicación de hora de Lima.
- Si el resumen no ha cargado correctamente, no presentar la hora actual del navegador como si fuera la hora de datos consultados.
- El rótulo del piloto sintético/simulado debe seguir el patrón existente, especialmente junto a resultados de riesgo. El contrato del panel no incluye `resultado_simulado` ni metadata del modelo: no inventar esos campos ni sus versiones.

#### 2.2 Formulario de filtros

| Control | Definición |
|---|---|
| Fecha | `input type="date"`, etiqueta visible «Fecha de la jornada». Obligatoria al aplicar. Valor inicial: hoy en Lima cuando no viene en la URL. |
| Especialidad | `select` con «Todas las especialidades», Cardiología, Traumatología y Pediatría. Enviar sus códigos de contrato. |
| Aplicar filtros | Confirma el borrador del formulario, actualiza la URL y vuelve a la primera página. |
| Hoy | Aplica la fecha actual de Lima, conserva especialidad y categoría y vuelve a la primera página. Sin esperar otro clic en Aplicar. |
| Actualizar | Repite resumen y listado con los filtros **ya aplicados**; conserva categoría y página. No aplica cambios del formulario aún no confirmados. |

- [x] Separar borrador del formulario de filtros aplicados en la URL.
- [x] Aplicar también mediante Enter desde el formulario.
- [x] No consultar por cada tecla o selección del borrador.
- [x] Si Aplicar no cambia los filtros, permitir actualizar los datos; no depender solo de que React Router detecte otra URL.
- [x] No cambiar automáticamente a mañana si la pantalla permanece abierta durante medianoche. La fecha aplicada permanece hasta usar Hoy o aplicar otra fecha.
- [x] Al usar atrás/adelante del navegador, sincronizar formulario, categoría y página con la URL restaurada.
- [x] Mantener disponibles los filtros para corregir un error; evitar que una carga anterior bloquee indefinidamente el formulario.

### 3. Tarjetas de resumen y fuente exacta

| Tarjeta | Campo(s) de `/panel/resumen` | Presentación |
|---|---|---|
| **Citas de la jornada** | `citas.total` | Entero principal y texto «Programadas para la fecha seleccionada». |
| **Riesgo de inasistencia** | `citas.por_riesgo.ALTO`, `citas.por_riesgo.MEDIO` | Dos cifras identificadas: «Alto: N» y «Medio: N». No mezclarlas con pendientes. |
| **Cupos disponibles** | `cupos.disponibles_para_ofrecer` | Entero y texto «Con horario futuro y disponibles para ofrecer». |
| **Recuperación de cupos** | `cupos.tasa_recuperacion_pct`, `cupos.reasignados_confirmados`, `cupos.total_liberados` | Porcentaje y texto «N de M cupos recuperados». |

- [x] Usar formato numérico `es-PE`; conservar cero como dato válido.
- [x] Si la tasa es `null`, mostrar **«Sin cupos liberados»**, no «0 %» ni «100 %».
- [x] Si hay cupos liberados y ninguno recuperado, sí mostrar `0 %`.
- [x] No multiplicar la tasa por 100: el backend ya devuelve un porcentaje en `[0,100]`.
- [x] La probabilidad de una cita sí viene en `[0,1]`: si se muestra en una fila, convertirla a porcentaje solo para presentación y etiquetarla como riesgo de inasistencia.
- [x] No añadir flechas de tendencia, comparación con ayer, metas o valoraciones de desempeño sin datos.
- [x] Las tarjetas iniciales serán informativas, sin aparentar enlaces que abran bandejas con filtros diferentes a sus conteos.
- [x] No abrir Cupos genérico afirmando que coincide exactamente con «disponibles»: esa bandeja puede incluir cupos vencidos almacenados como disponibles.

### 4. Bandeja integrada de pendientes

#### 4.1 Selector de categoría

Tres botones de selección con texto y contador:

| Texto visible | `tipo` del listado | Contador del resumen |
|---|---|---|
| Citas sin intervención | `CITAS_SIN_INTERVENCION` | `pendientes.citas_sin_intervencion` |
| Intervenciones sin respuesta | `INTERVENCIONES_SIN_RESPUESTA` | `pendientes.intervenciones_sin_respuesta` |
| Ofertas en curso | `OFERTAS_EN_CURSO` | `pendientes.ofertas_en_curso` |

- Categoría inicial: `CITAS_SIN_INTERVENCION`, aunque su contador sea cero.
- No cambiar de categoría automáticamente porque otra tenga resultados.
- Mostrar una tabla por vez y consultar únicamente la categoría seleccionada; no precargar tres listados.
- Elegir semántica de **grupo de botones con `aria-pressed`** y foco visible. No declarar `role="tab"` sin implementar también el patrón completo de teclado asociado.
- Cambiar categoría conserva fecha y especialidad, reinicia el desplazamiento y solicita su listado. No necesita recargar el resumen.
- Si el resumen no está disponible, los botones conservan sus etiquetas y pueden mostrar «—» en sus contadores; nunca inventar cero. El listado puede seguir consultándose por su cuenta.
- No sumar las tres cantidades en un «total de pendientes»: representan entidades distintas.

#### 4.2 Tabla de citas sin intervención

| Columna | Campo/presentación |
|---|---|
| Hora | `fecha_hora_cita`, hora de Lima. La fecha ya se identifica en el contexto de la jornada. |
| Cita | `id_cita_externa`; mantener `id_cita` como identificador de navegación, no como reemplazo del código externo. |
| Especialidad | `especialidad` con etiqueta legible. |
| Médico | `medico`. |
| Riesgo | `nivel_riesgo`, etiqueta Alto/Medio y, si se incorpora en el mismo espacio, porcentaje de `probabilidad_no_show`. |
| Acción | Enlace **«Ver cita»** a `/citas/{id_cita}`. |

Ayuda breve de la categoría: **«Citas recibidas de riesgo alto o medio, con horario futuro, sin intervención registrada y sin oposición de contacto.»**

La ayuda refleja la regla del backend; no se vuelve a implementarla en JavaScript. No convertir esta lista en la totalidad de citas intervenibles: M05 también permite otros estados y reintentos.

#### 4.3 Tabla de intervenciones sin respuesta

| Columna | Campo/presentación |
|---|---|
| Hora de cita | `fecha_hora_cita`, en Lima. |
| Cita | `id_cita_externa`. |
| Especialidad | `especialidad`. |
| Canal | `canal_contacto`: WhatsApp, SMS o Llamada telefónica. |
| Estado | `estado_intervencion`: Enviada o Entregada. |
| Envío registrado | `fecha_hora_envio`, fecha y hora completas porque puede ser de otro día; «—» si es `null`. |
| Acción | **«Ver seguimiento»** a `/intervenciones/{id_intervencion}`. |

Ayuda: **«Intervenciones enviadas o entregadas que siguen sin respuesta, asociadas a citas activas con horario futuro.»**

No interpretar `RESPONDIDA` con resultado `SIN_RESPUESTA` como una espera abierta ni confundir `PENDIENTE` con envío realizado. Esas exclusiones ya vienen resueltas en el servidor.

#### 4.4 Tabla de ofertas en curso

| Columna | Campo/presentación |
|---|---|
| Cupo | `id_cupo_liberado`, por ejemplo «#325». |
| Hora | `fecha_hora_cupo`, en Lima. |
| Especialidad | `especialidad`. |
| Médico | `medico`. |
| Estado | `estado_cupo`, etiqueta «En oferta». |
| Acción | **«Ver cupo»** a `/cupos/{id_cupo_liberado}`. |

Ayuda: **«Cupos con una oferta en curso, horario futuro y sin reasignación confirmada.»**

El contrato no entrega el candidato, un historial de oferta ni su fecha de creación. No añadir columnas vacías que aparenten esa información ni consultar cada detalle de cupo para completar la tabla.

#### 4.5 Orden y paginación

- [x] Mantener el orden recibido del backend. No ordenar localmente solo la página actual.
- [x] Página fija de **20 registros**. No incorporar selector de tamaño en esta versión.
- [x] `total` proviene de `/panel/pendientes`, no de `items.length` ni del contador del resumen.
- [x] Mostrar «N pendientes» y, cuando exista resultado, «Mostrando A–B de N».
- [x] Anterior resta 20 sin pasar de cero; Siguiente suma 20 mientras haya registros.
- [x] Deshabilitar Anterior en desplazamiento 0 y Siguiente si `desplazamiento + limite >= total`.
- [x] Deshabilitar la paginación durante la carga de esa lista, evitando peticiones duplicadas por clic repetido.
- [x] Si `total == 0`, mostrar vacío específico de la categoría y no una tabla sin explicación.
- [x] Si `total > 0` y `items == []` por un offset válido pero ya fuera de rango, mostrar **«Esta página ya no tiene resultados»** y un botón **«Ir a la primera página»**. No presentar «0 pendientes» ni una página ficticia «6 de 2».
- [x] No hacer reintentos automáticos infinitos para corregir un offset obsoleto. El usuario puede volver a la primera página o actualizar.

### 5. Desgloses de la jornada

Después de los pendientes, presentar tres secciones compactas con etiquetas y cifras:

| Sección | Datos | Criterio de presentación |
|---|---|---|
| **Citas por estado** | `citas.por_estado` | Recibida, Confirmada, Reprogramada, Cancelada, Liberada, Atendida y No asistió. |
| **Distribución de riesgo** | `citas.por_riesgo` | Alto, Medio, Bajo y Sin predicción. |
| **Intervenciones por estado** | `intervenciones.total`, `citas_con_intervencion` y `por_estado` | Total de registros, citas distintas intervenidas y distribución Pendiente/Enviada/Entregada/Respondida/Fallida. |

- Conservar categorías con cero; no omitirlas para aparentar que el catálogo cambió.
- El riesgo describe resultados registrados de toda la jornada, incluidas citas finalizadas; no es el número de pendientes.
- Una cita puede tener más de una intervención. «Intervenciones» y «citas con intervención» son unidades diferentes.
- Los estados de intervención son una distribución actual; no sumar Respondida a Enviada para inventar envíos acumulados.
- No convertir «Sin predicción» en riesgo Bajo ni usar colores idénticos para ambas categorías.
- Barras CSS simples son opcionales si mejoran la lectura; las cifras y etiquetas siempre deben estar visibles. Si se usan proporciones, usar el total del bloque correspondiente y evitar división por cero. Es formato visual, no recálculo de negocio.
- No añadir gráficos circulares, series temporales o un bloque técnico del modelo en esta versión.

### 6. URL, fecha de Lima y estado de navegación

#### 6.1 Parámetros de `/panel`

| Parámetro | Regla |
|---|---|
| `fecha` | ISO `YYYY-MM-DD`. Si falta, resolver hoy en Lima y fijarlo en la URL con `replace`, para que el contexto no cambie al regresar otro día. |
| `especialidad` | Opcional, catálogo backend. Ausente significa todas. No enviar `TODAS` al servidor. |
| `tipo` | Uno de los tres códigos. Ausente o desconocido: normalizar a `CITAS_SIN_INTERVENCION`. |
| `desplazamiento` | Entero seguro, no negativo y múltiplo de 20. Ausente, inválido o desalineado: normalizar a 0. |

Ejemplo de URL reproducible:

```text
/panel?fecha=2026-11-09&especialidad=CARDIOLOGIA&tipo=INTERVENCIONES_SIN_RESPUESTA&desplazamiento=20
```

- [x] Construir URLs mediante `URLSearchParams`; evitar concatenaciones de valores sin codificar.
- [x] Centralizar parseo, validación y construcción de URLs en el módulo, con pruebas.
- [x] Normalizar valores por defecto una sola vez con `replace`, sin llenar el historial ni entrar en un bucle de navegación.
- [x] Fecha imposible, fuera del rango que acepta backend o especialidad desconocida: mostrar error corregible en filtros y no consultar ese universo inválido. No sustituir silenciosamente la especialidad por «Todas».
- [x] No truncar valores de paginación como `20abc` mediante `parseInt`; validar el valor completo.
- [x] Usar historial normal al aplicar filtros, cambiar categoría o paginar, para que Atrás/Adelante restaure el contexto.
- [x] No guardar los filtros aplicados en un segundo estado independiente que pueda contradecir la URL.

#### 6.2 Formato temporal propio del panel

El formateador compartido actual `nucleo/formato/formato.ts` usa la zona del navegador. No cumple por sí solo la presentación explícita de Lima requerida por este panel.

- [x] Crear funciones locales para hoy en Lima, fecha de jornada, hora y fecha/hora de timestamps.
- [x] Usar `Intl.DateTimeFormat("es-PE", { timeZone: "America/Lima", ... })`.
- [x] Obtener `YYYY-MM-DD` de partes numéricas del formato, sin asumir que una salida localizada viene ordenada como ISO.
- [x] No usar `new Date().toISOString().slice(0, 10)` para determinar hoy en Lima.
- [x] No interpretar `new Date("YYYY-MM-DD")` como medianoche local y luego restarle horas accidentalmente; tratar la jornada como fecha de calendario.
- [x] Usar timestamps con offset del servidor para horas de citas, cupos, envíos y `generado_en`.
- [x] No alterar el formateador compartido ni todas las pantallas para introducir este comportamiento.

### 7. Integración con los endpoints

#### 7.1 Solicitudes y disparadores

| Evento | Resumen | Listado |
|---|---|---|
| Entrada con URL válida | Consultar una vez. | Consultar la categoría/página seleccionada. |
| Aplicar fecha/especialidad nuevas | Consultar con filtros nuevos. | Consultar con filtros nuevos y desplazamiento 0. |
| Hoy | Consultar si cambia jornada; si ya es hoy, permitir refrescar. | Consultar primera página conservando categoría/especialidad. |
| Cambiar categoría | Conservar el resumen vigente. | Consultar categoría nueva, offset 0. |
| Paginar | Conservar el resumen vigente. | Consultar nueva página. |
| Actualizar | Repetir consulta actual. | Repetir consulta actual, conservando página. |
| Reintentar un bloque fallido | Solo si el bloque es resumen. | Solo si el bloque es listado. |
| Regresar de un detalle | Consultar nuevamente al montar el panel. | Consultar el contexto guardado, sin reutilizar una respuesta persistida. |

Peticiones propuestas:

```http
GET /panel/resumen?fecha=2026-11-09&especialidad=CARDIOLOGIA
GET /panel/pendientes?fecha=2026-11-09&especialidad=CARDIOLOGIA&tipo=CITAS_SIN_INTERVENCION&limite=20&desplazamiento=0
```

- Resumen solo recibe fecha y especialidad; no enviarle `tipo` o paginación.
- Listado siempre recibe `tipo`, `limite=20` y desplazamiento validado, además del universo.
- No consultar `/citas`, `/intervenciones`, `/cupos` o cada detalle para calcular indicadores o completar cada fila.
- No hacer un tercer request solo para obtener el total: el listado ya lo entrega.
- Los dos GET pueden resolverse independientemente; un fallo del resumen no debe impedir consultar pendientes válidos, y viceversa.

#### 7.2 Reutilización de infraestructura existente

- [x] Usar `api`/`useConsulta` existentes, sin `fetch` paralelo con otra política de token.
- [x] Reutilizar la cancelación y protección contra respuestas antiguas del hook para cambios de filtros, categoría, página o desmontaje.
- [x] Evitar solicitudes por simple rerender; construir claves de consulta estables.
- [x] Actualizar ambos bloques mediante sus callbacks al pulsar Actualizar; no crear parámetros falsos de negocio ni usar `generado_en` como query.
- [x] No cambiar la implementación global de `useConsulta` para mantener datos anteriores en esta entrega. Durante una nueva carga, puede mostrar estado de carga en vez de mezclar datos del filtro anterior.
- [x] Deshabilitar Actualizar mientras sus consultas están en curso, con texto de estado; no bloquear permanentemente los cambios de filtros/categoría.
- [x] Respetar el flujo de sesión existente: `401` lo gestiona el cliente compartido, sin duplicar redirecciones o almacenamiento de credenciales en Panel.

#### 7.3 Consistencia visible entre resumen y listado

Cada respuesta backend es coherente internamente, pero dos peticiones distintas no comparten un snapshot congelado.

- Mostrar el total de la tabla desde su propia respuesta.
- Los contadores de categoría proceden del resumen mientras ese resumen sea válido.
- Si el total de la categoría seleccionada difiere del contador del resumen, no sobrescribir silenciosamente el objeto de resumen ni presentar un error de cálculo. Mostrar un aviso discreto: **«Los datos pueden haber cambiado. Actualiza el panel para consultar el resumen nuevamente.»**
- Mostrar la hora de consulta del listado cerca de la tabla cuando haya datos o vacío confirmado; no confundirla con la hora del resumen.
- No iniciar un bucle de reconsultas para intentar igualar snapshots continuamente.
- No eliminar un registro localmente como si se hubiera realizado la acción desde el panel. Al regresar de su detalle se vuelve a consultar.

### 8. Estados de interfaz y textos

| Situación | Presentación y acción |
|---|---|
| Carga inicial del resumen | `Cargando` o estructura de carga que no simule datos. Pendientes puede cargar por separado. |
| Carga de nueva página/categoría | Mensaje de carga de lista; no mantener filas antiguas bajo un encabezado de categoría nueva. |
| Error de resumen | Mensaje y Reintentar. Mantener formulario y lista independiente; ocultar cifras no disponibles. |
| Error de listado | Mensaje y Reintentar en la bandeja; conservar resumen exitoso. |
| Error de conexión | Mensaje del cliente API y reintento manual; nunca «Sin pendientes». |
| Sin citas en la jornada | Tarjetas/desgloses en cero solo tras respuesta exitosa. No ocultar cupos si el universo de cupos sí tiene registros. |
| Sin citas pendientes | «No hay citas sin intervención con estos filtros.» |
| Sin intervenciones pendientes | «No hay intervenciones pendientes de respuesta con estos filtros.» |
| Sin ofertas pendientes | «No hay ofertas en curso con estos filtros.» |
| Sin denominador de recuperación | «Sin cupos liberados». |
| Página fuera de rango | Mensaje específico y botón de primera página, conservando el total real. |
| Respuesta vacía inesperada o forma incompatible | Mostrar error de datos no disponibles/contrato; no rellenar campos obligatorios con ceros para ocultarlo. |
| Sin permiso | Usar ruta protegida y protección local antes de montar consultas; no mostrar parcialmente información del panel. |

No usar información técnica de endpoints, transacciones o schemas en los textos de producto. Esos detalles pertenecen a esta especificación y las pruebas.

### 9. Navegación hacia detalles y retorno

#### 9.1 Comportamiento requerido

Al abrir una fila, enviar el contexto completo aplicado mediante el patrón existente de estado de navegación:

```tsx
<Link to={`/citas/${item.id_cita}`} state={{ volver: rutaPanelActual }}>
  Ver cita
</Link>
```

`rutaPanelActual` debe contener `/panel` con fecha, especialidad, categoría y desplazamiento aplicados, no los valores de un borrador sin confirmar.

- [x] Desde cada uno de los tres detalles, si su origen válido es Panel, mostrar **«Volver al panel operativo»**.
- [x] Al volver, restituir filtros/categoría/página y obtener datos actuales.
- [x] Conservar el retorno propio actual cuando el detalle se abrió desde su módulo o por URL directa.
- [x] Admitir el enlace de regreso en las ramas de error o registro no encontrado donde ya se ofrece retorno.
- [x] No usar `navigate(-1)` como único mecanismo: el historial previo puede no ser el panel.
- [x] Aceptar solo rutas internas permitidas para retorno; mantener las restricciones de los detalles actuales. No aceptar cualquier `state.volver` como enlace externo.
- [x] El patrón usa el estado de React Router; no promete conservar contexto al copiar únicamente la URL del detalle a otra sesión. Sin estado, usar el retorno normal del módulo.

#### 9.2 Estado actual que exige cambios

| Vista existente | Situación observada | Cambio acotado |
|---|---|---|
| `citas/Detalle.tsx` | Acepta `state.volver` solo si empieza por `/citas?`; un retorno a `/panel?...` hoy se descarta. | Admitir también el panel y cambiar la etiqueta cuando corresponda, manteniendo el retorno a Citas. |
| `intervenciones/Seguimiento.tsx` | Retorno fijo a `/intervenciones`. | Leer el origen y permitir regreso al panel; conservar fallback actual. |
| `lista-espera/DetalleCupo.tsx` | Retorno fijo a `/cupos`. | Leer el origen y permitir regreso al panel, también en error/no encontrado. |

Crear un helper pequeño de navegación compartida para resolver y validar `state.volver`. Debe ser independiente de contratos de negocio y recibir rutas permitidas/fallback; no importar el módulo Panel desde las otras vistas.

La garantía inicial es **Panel → detalle directo → Panel**. Los enlaces secundarios hacia trazabilidad, otras bandejas o flujos de varias pantallas mantienen su navegación actual; no extender automáticamente el contexto por toda la aplicación en esta entrega. Si se solicita preservar un recorrido de varios niveles, documentarlo como ampliación específica antes de modificar más vistas.

### 10. Tipos y organización del módulo

#### 10.1 Contratos TypeScript

Definir en `modulos/panel/tipos.ts` equivalentes explícitos a los schemas backend:

- `TipoPendiente`: unión de los tres códigos.
- `PanelResumenOut`: contexto, citas, intervenciones, cupos y pendientes.
- `PanelPendientesOut`: contexto, categoría, total, límite, desplazamiento e items.
- Unión discriminada de `CitaSinIntervencionOut`, `IntervencionSinRespuestaOut` y `OfertaEnCursoOut`, por `tipo`.
- Fechas/timestamps como strings ISO en el transporte.
- `tasa_recuperacion_pct: number | null` y `fecha_hora_envio: string | null`.
- Conteos como `number`, con `Record` de claves de catálogo donde corresponda.
- No reutilizar como si fueran equivalentes `CitaDetalleOut`, `CupoDetalleOut` o `IntervencionOut`: los items del panel son proyecciones con menos campos.
- Reutilizar tipos de dominio existentes mediante `import type` cuando coincidan, sin mover todos los tipos de los módulos a una carpeta global.
- Mantener constantes locales de presentación y tipos de pendiente; no introducir catálogos nuevos en backend.
- No usar `any`, casts dobles o campos inventados para resolver diferencias de contrato. TypeScript no valida JSON en ejecución: si se añaden comprobaciones estructurales, serán locales y pequeñas, sin una nueva librería o framework.

#### 10.2 Componentes y responsabilidad

| Componente | Responsabilidad |
|---|---|
| `PanelOperativo` | Protección local por rol, coordinación de contexto URL, montaje de filtros y contenido autorizado. |
| `FiltrosPanel` | Borrador de fecha/especialidad, validación visible y callbacks de Aplicar/Hoy/Actualizar. |
| `ResumenPanel` | Cuatro tarjetas y los tres desgloses con datos recibidos; no solicita sus propias copias del resumen. |
| `PendientesPanel` | Selector de categoría, estado de la lista, tabla tipada, paginación y enlaces de detalle. |

La ubicación exacta de las dos llamadas `useConsulta` puede ser el contenedor o un hijo interno de contenido válido. Deben ejecutarse una sola vez por recurso, nunca duplicarse por tener tarjetas/desgloses separados. Usar componentes hijos para evitar hooks condicionales cuando la URL o el rol sean inválidos.

### 11. Archivos a crear, modificar y conservar

Rutas de esta sección relativas a `apps/frontend`, excepto las que indiquen raíz. La matriz conserva el alcance acordado. Los cambios realizados se detallan en changelog.md; las modificaciones condicionales no implican que todos los archivos se hayan alterado.

#### 11.1 Archivos previstos y creados

| Archivo | Contenido |
|---|---|
| `src/modulos/panel/PanelOperativo.tsx` | Página principal y composición autorizada; dos recursos API, URL y acciones de consulta. |
| `src/modulos/panel/FiltrosPanel.tsx` | Formulario accesible y borrador, sin consultas por tecla. |
| `src/modulos/panel/ResumenPanel.tsx` | Tarjetas, recuperación nula y desgloses. |
| `src/modulos/panel/PendientesPanel.tsx` | Tres categorías, tabla según tipo, estados y paginación. |
| `src/modulos/panel/tipos.ts` | Tipos fieles al contrato backend, constantes de categorías y etiquetas locales necesarias. |
| `src/modulos/panel/consulta.ts` | Parseo/validación de query, normalización, generación de URL del panel y URLs de los dos endpoints. Funciones puras. |
| `src/modulos/panel/formato.ts` | Fecha de hoy y presentación temporal de Lima; formato numérico/porcentaje propio del módulo si hace falta. |
| `src/modulos/panel/rutas.tsx` | Exportar la ruta `/panel` con roles Recepción/Administración usando `RutaModulo`. |
| `src/modulos/panel/menu.ts` | Exportar entrada «Panel operativo», ruta `/panel`, roles permitidos y orden anterior a Citas, por ejemplo 0. Reutilizar icono existente. |
| `src/modulos/panel/panel.css` | Estilos con prefijo propio `panel-`, adaptación de tarjetas, selector y tabla sin reglas globales invasivas. |
| `src/modulos/panel/validacion.ts` y su prueba | Comprobación estructural local de respuestas; error ante proyecciones incompatibles. |
| `src/nucleo/navegacion/retorno.ts` | Resolver origen interno permitido/fallback para enlaces de regreso, sin conocer entidades del panel. |
| `src/modulos/panel/PanelOperativo.test.tsx` | Integración de filtros, consultas, errores parciales, permisos, selección y navegación. |
| `src/modulos/panel/ResumenPanel.test.tsx` | Datos completos, ceros, recuperación nula, etiquetas y unidades. |
| `src/modulos/panel/PendientesPanel.test.tsx` | Tres variantes de tabla, orden preservado, paginación, offset vacío, enlaces y estados. |
| `src/modulos/panel/consulta.test.ts` | URL, valores inválidos, normalización, límites y restablecimiento de página. |
| `src/modulos/panel/formato.test.ts` | Lima frente a UTC/otra zona, fecha ISO, medianoche y formato de porcentaje. |
| `src/nucleo/navegacion/retorno.test.ts` | Origen del panel permitido, fallback propio y rechazo de rutas no permitidas. |

Los tests deben comprobar comportamiento y contratos; no duplicar cada línea del render con pruebas que solo reflejen su implementación. Se pueden ajustar los límites entre archivos de pruebas sin perder los escenarios requeridos.

#### 11.2 Modificar obligatoriamente con alcance acotado

| Archivo existente | Cambio permitido/requerido |
|---|---|
| `src/modulos/sesion/Login.tsx` y `Login.test.tsx` | Cambiar únicamente la redirección autenticada de `/citas` a `/`, para resolver el inicio por rol; actualizar su prueba. No cambiar autenticación ni credenciales. |
| `src/App.test.tsx` | Sustituir la expectativa «todos inician en Citas mientras no existe panel»: Recepción/Administración ahora inician en Panel; Técnico IA continúa en Citas. Agregar respuestas simuladas específicas para los dos endpoints del panel. |
| `src/nucleo/layout/ranuras.ts` | Actualizar el comentario obsoleto que anuncia `/panel` como futuro. La lógica de `inicioPorRol` ya contempla la ruta; conservarla si funciona al registrar el módulo. |
| `src/modulos/citas/Detalle.tsx` | Admitir retorno al panel y etiqueta contextual, sin cambiar formularios, transiciones, predicción ni trazabilidad. |
| `src/modulos/intervenciones/Seguimiento.tsx` | Retorno contextual del detalle al panel, conservando acciones y fallback. |
| `src/modulos/lista-espera/DetalleCupo.tsx` | Retorno contextual del detalle al panel en estados normales y de error, sin tocar ofertas o confirmación. |
| Pruebas de los tres detalles | Añadir casos de retorno desde panel y de fallback previo; no reescribir pruebas ajenas ni desactivar fallos para conseguir una suite verde. |
| `README.md` | Documentar entrada por rol, filtros, endpoints, significado de la jornada, actualización manual y comandos de verificación. |
| `spec/changelog.md` | Registrar implementación y resultados reales al terminar. No escribir todavía un cierre exitoso. |

Las pruebas actuales de navegación que asuman redirección a Citas después del login deberán localizarse y ajustarse **solo** cuando su expectativa cambie por el inicio en Panel. Mantener el propósito original de autenticación de esas pruebas.

#### 11.3 Modificar solo si una necesidad concreta lo exige

- `src/modulos/sesion/IntegracionM01.test.tsx`, pruebas de Login o de gestor de sesión: solo expectativas/mocks afectados por la ruta inicial nueva.
- `src/modulos/citas/Detalle.test.tsx`, `src/modulos/intervenciones/Seguimiento.test.tsx` y `src/modulos/lista-espera/DetalleCupo.test.tsx`: usar los archivos existentes si permiten aislar las nuevas pruebas; crear un archivo de integración de retorno aparte si así se evita mezclar una deuda histórica con esta funcionalidad.
- `src/modulos/panel/FiltrosPanel.test.tsx`: si los comportamientos del formulario no quedan cubiertos claramente por las pruebas de pantalla.
- Fixtures del panel: crear un archivo local de datos sintéticos si evita duplicación significativa. No usar fixtures incompletos ni la misma respuesta JSON para endpoints de formas diferentes.
- Control de respuesta local: si hace falta detectar datos incompatibles, crear una función pequeña con pruebas. No cambiar el cliente global para introducir un validador de todos los módulos.

#### 11.4 Conservar sin cambios funcionales por esta entrega

- `src/App.tsx`: `import.meta.glob` ya descubre `modulos/*/rutas.tsx`; no agregar imports manuales del panel ni otra rama de permisos paralela.
- `src/nucleo/layout/Layout.tsx`: ya descubre `menu.ts`; no insertar una entrada a mano ni alterar menú plegable, cabecera o pie.
- `src/nucleo/api/cliente.ts` y `src/nucleo/api/useConsulta.ts`: conservar token, errores, sesión, cancelación y semántica de carga.
- AuthProvider, contexto de sesión, RutaProtegida y mecanismos de autenticación.
- `src/nucleo/formato/formato.ts` y `RelojLocal`: conservar el comportamiento global actual.
- `src/index.css`, marca, imágenes, logos, `Icono.tsx` y navegación visual común: reutilizar lo existente.
- Formularios de registro/importación de Citas, creación/seguimiento de intervenciones y reasignación, salvo el enlace de retorno indicado.
- Reportes, Modelo IA, Usuarios y Lista de espera: no ampliar sus funciones.
- `package.json`, `package-lock.json`, `vite.config.ts`, TypeScript y ESLint: no se necesitan dependencias o umbrales nuevos.
- Backend, contratos públicos existentes, datos, entorno, contenedores y artefactos IA.

### 12. Diseño visual, adaptación y accesibilidad

- [x] Reutilizar la identidad visual actual: tarjetas, bordes, tipografía, espaciado, mensajes y botones.
- [x] Escritorio: cuatro tarjetas cuando el ancho útil lo permita; tablet: dos; móvil: una. Elegir cortes por espacio disponible, sin forzar desbordamientos para mantener cuatro columnas.
- [x] Filtros en una fila o varias según ancho; en móvil, controles y botones con espacio suficiente y sin desbordar la pantalla.
- [x] Selector de categorías adaptable a varias filas o columna. No esconder categorías ni truncar su significado.
- [x] Tabla dentro de contenedor con desplazamiento horizontal propio, encabezados semánticos y `caption` accesible. No permitir desplazamiento horizontal de toda la página.
- [x] Acciones con texto explícito: Ver cita, Ver seguimiento, Ver cupo. Si hay iconos, serán decorativos y no reemplazarán el nombre accesible.
- [x] Estados/riesgos con etiqueta textual, no únicamente color. Sin predicción debe diferenciarse de Bajo.
- [x] Etiquetas vinculadas a inputs, errores comprensibles y foco visible.
- [x] Usar encabezados jerárquicos: un `h1`, secciones `h2` y subsecciones cuando corresponda.
- [x] Mantener el enlace para saltar al contenido y los landmarks ya provistos por Layout; no agregar otro `main` dentro de la página.
- [x] Comunicar carga/error/resultado con regiones de estado moderadas, sin anunciar todos los contadores en cada render ni mover el foco de forma inesperada.
- [x] Respetar `prefers-reduced-motion`; no introducir animaciones necesarias para interpretar el panel.
- [x] Verificar 1440 px, 1024 px y 390 px de ancho y navegación por teclado.
- Comprobación visual adicional recomendada: zoom real del navegador. Se verificó reflow mediante viewport; no se acredita una prueba específica de zoom.

### 13. Matriz de pruebas de aceptación

Matriz acordada de verificación. Las pruebas y revisión del alcance se ejecutaron; UI-PAN-40 conserva la salvedad de fallos globales preexistentes descrita en validacion-panel-operativo.md. Usar respuestas sintéticas fieles al backend y no consultar la base operativa del piloto para automatizar acciones.

| ID | Escenario | Resultado requerido |
|---|---|---|
| UI-PAN-01 | Recepción entra por `/`. | Llega al Panel; menú visible y activo. |
| UI-PAN-02 | Administración entra por `/`. | Mismo inicio autorizado. |
| UI-PAN-03 | Técnico IA entra por `/` o solicita `/panel`. | Conserva inicio actual; acceso directo rechazado sin consultas de panel. |
| UI-PAN-04 | Usuario sin sesión entra a `/panel`. | Gestión de login existente; sin datos del panel. |
| UI-PAN-05 | Abrir `/panel` sin fecha, navegador en otra zona. | Hoy calculado en Lima, URL explícita y consultas del mismo día. |
| UI-PAN-06 | Envío de filtros con especialidad. | Resumen/lista reciben filtros iguales; offset vuelve a cero. |
| UI-PAN-07 | Cambiar borrador sin Aplicar. | No se consulta ni se alteran los datos aplicados. Actualizar conserva el universo aplicado. |
| UI-PAN-08 | Hoy desde otra fecha. | Cambia a hoy en Lima, conserva especialidad/categoría y reinicia página. |
| UI-PAN-09 | Aplicar sin cambiar filtros o pulsar Actualizar. | Reconsulta manual válida, sin depender de una URL diferente. |
| UI-PAN-10 | Atrás/Adelante del navegador. | Restaura filtros, categoría y página; formulario coherente. |
| UI-PAN-11 | Fecha imposible o especialidad desconocida en URL. | Error corregible, sin GET con universo inválido. |
| UI-PAN-12 | Tipo desconocido, offset negativo/no entero/desalineado. | Normalización documentada, sin bucles ni historial innecesario. |
| UI-PAN-13 | Resumen completo. | Cuatro tarjetas con fuentes correctas, riesgo alto/medio diferenciados y desgloses completos. |
| UI-PAN-14 | Cero citas, pero existen cupos. | No ocultar cupos por el total de citas. |
| UI-PAN-15 | Recuperación `null`, cero real y porcentaje decimal. | Sin denominador se distingue de 0 %; formato correcto, sin multiplicar otra vez por 100. |
| UI-PAN-16 | Riesgo sin predicción. | Categoría visible y diferenciada de Bajo. |
| UI-PAN-17 | Varias intervenciones por cita. | Mostrar total de registros y citas distintas sin confundir unidades. |
| UI-PAN-18 | Alternar las tres categorías. | Columnas, IDs y acciones correctos; una lista solicitada por vez. |
| UI-PAN-19 | Categoría con contador cero. | Se puede seleccionar, muestra vacío; no salta automáticamente a otra. |
| UI-PAN-20 | Listado con más de 20 registros. | Total servidor, offset y navegación de página correctos. |
| UI-PAN-21 | Total cambia y la página queda vacía. | Conserva total real y ofrece volver al inicio; no «0 pendientes» ni página imposible. |
| UI-PAN-22 | Resumen y lista tienen distintos conteos por cambios concurrentes. | Total de tabla propio y aviso discreto, sin sobrescribir ni reconsultar en bucle. |
| UI-PAN-23 | Falla resumen y funciona listado; caso inverso. | Error/reintento independientes; no ceros ni bloqueo total de la pantalla. |
| UI-PAN-24 | Cambiar filtros rápido, respuesta antigua llega al final. | Solo la respuesta vigente se muestra; solicitudes obsoletas canceladas/ignoradas. |
| UI-PAN-25 | Desmontar la pantalla durante una consulta. | Sin actualización tardía del componente ni petición recurrente. |
| UI-PAN-26 | Abrir cada tipo de detalle desde una fila. | URL por ID correcto y estado de retorno con contexto completo. |
| UI-PAN-27 | Volver desde Cita, Seguimiento o Cupo. | Regreso al panel con filtros/categoría/página y consultas nuevas. |
| UI-PAN-28 | Abrir detalle directamente o desde su bandeja original. | Conservar fallback/retorno anterior y formularios funcionales. |
| UI-PAN-29 | `state.volver` externo o no permitido. | No crear enlace a esa ruta; aplicar fallback del detalle. |
| UI-PAN-30 | Medianoche, timestamps UTC y equipo en otra zona. | Fecha de jornada y horarios del panel se mantienen en Lima. |
| UI-PAN-31 | Timestamp de envío nulo o envío otro día. | «—» para nulo, fecha/hora completas para registro anterior. |
| UI-PAN-32 | Respuesta con proyección de item según cada tipo. | No exigir campos exclusivos del detalle ni inventar candidatos/metadata. |
| UI-PAN-33 | API responde `401` o `403`. | Flujo de sesión/permiso vigente, sin exposición de datos previos. |
| UI-PAN-34 | Página en carga o error. | No mostrar datos del filtro anterior bajo el nuevo contexto; acciones coherentes y reintento. |
| UI-PAN-35 | Navegación por teclado y etiquetas accesibles. | Filtros, categorías, enlaces y paginación operables con foco visible. |
| UI-PAN-36 | Anchos 1440, 1024 y 390 px. | Lectura útil, tarjetas adaptadas y tabla con scroll local, sin desbordamiento global. |
| UI-PAN-37 | Inspección de tráfico del Panel. | Solo los dos GET previstos; sin descargas masivas, detalles por fila, mutaciones o inferencias. |
| UI-PAN-38 | Regresión de menú, login e inicio por rol. | Panel descubierto por ranuras, accesos anteriores preservados y expectativas nuevas actualizadas. |
| UI-PAN-39 | Orden de datos de backend. | Se conserva; no reordenar la página por criterio visual distinto. |
| UI-PAN-40 | Typecheck, lint, build y suite. | Validaciones ejecutadas con evidencia, sin reducir cobertura ni ocultar fallos. |

Las pruebas unitarias/integración deben usar React Testing Library, Vitest y el patrón de fixtures/fetch existente. Los casos visuales y de recorrido HTTP se acreditan además con revisión de la pantalla en un entorno aislado. No presentar pruebas simuladas de fetch como evidencia de conexión real con backend.

### 14. Secuencia de implementación y validación

1. [x] Revisar instrucciones aplicables, estado del checkout y cambios ajenos al iniciar; conservarlos.
2. [x] Verificar contrato del backend y disponibilidad de sus dos rutas en el ambiente de integración.
3. [x] Definir tipos, fixtures completos y funciones puras de URL/formato temporal con sus pruebas.
4. [x] Crear ruta y menú por ranuras; actualizar expectativas de inicio por rol sin rediseñar App/Layout.
5. [x] Construir estructura de página, formulario y estados independientes de consulta.
6. [x] Conectar resumen, tarjetas y desgloses con sus campos exactos.
7. [x] Conectar categorías, tablas tipadas y paginación, reutilizando cancelación del hook.
8. [x] Implementar enlaces de detalle y helper de retorno; adaptar solo los tres detalles acordados.
9. [x] Verificar ceros/nulls, filtros inválidos, errores parciales, páginas obsoletas y consultas concurrentes.
10. [x] Completar estilos propios y revisar teclado, foco, rótulos y adaptación a tres anchos.
11. [x] Ejecutar pruebas focalizadas de Panel, retorno y rutas afectadas.
12. [x] Ejecutar `npm run typecheck`, `npm run lint` y `npm run build` dentro de `apps/frontend`.
13. [x] Ejecutar `npm test` con la configuración vigente de cobertura de líneas >= 75 %.
14. [x] Si aparecen fallos preexistentes, caracterizarlos con evidencia del checkout base y distinguirlos de regresiones nuevas. No asumir que las cifras históricas de Citas describen el estado actual ni desactivar casos para cerrar la tarea.
15. [x] Recorrer en entorno aislado: entrar como Recepción → filtrar → revisar cada categoría → abrir detalle → volver → comprobar filtros/página y datos actualizados.
16. [x] Comprobar Administración, Técnico IA, sin sesión, fallos de API y ausencia de acciones de negocio desde el Panel.
17. [x] Registrar comandos, resultados, cobertura, limitaciones y evidencia visual/HTTP en README/changelog.
18. [x] Conservar la especificación final en un documento vigente y retirar de este ToDo únicamente lo completado y validado.

Comandos de referencia (desde `apps/frontend`):

```bash
npx vitest run src/modulos/panel src/nucleo/navegacion/retorno.test.ts
npm run typecheck
npm run lint
npm run build
npm test
```

Las pruebas focalizadas sirven para iterar; no sustituyen la suite con cobertura ni la validación HTTP/visual. No instalar paquetes nuevos para ejecutar este alcance si el runtime/dependencias existentes ya permiten hacerlo.

### 15. Criterio de cierre

La pantalla estará terminada cuando los roles autorizados entren al Panel por la navegación normal; sus dos consultas usen el mismo universo aplicado; tarjetas/desgloses respeten unidades y valores nulos; los tres listados estén paginados y abran el detalle correcto; el regreso conserve el contexto directo; y los estados de carga/error/vacío, la zona horaria y la adaptación visual estén acreditados por pruebas y revisión.

El cierre de esta tarea no acredita REP-01, nuevas operaciones del backend, conservación de contexto en todos los recorridos de múltiples niveles, despliegue al piloto ni aceptación integral del sistema.

### 16. Referencias de trabajo

- [Validación y salvedades](validacion-panel-operativo.md).
- [Registro de cambios](changelog.md).

- [Contrato incremental del panel](../../../contracts/backend/panel.v1.md).
- [Especificación del backend implementado](../../backend/spec/panel-operativo.md).
- [Schemas backend](../../backend/app/modules/panel/schemas.py).
- [Descubrimiento de rutas](../src/App.tsx) y [pruebas actuales de navegación](../src/App.test.tsx).
- [Layout y descubrimiento de menú](../src/nucleo/layout/Layout.tsx).
- [Selección de inicio por rol](../src/nucleo/layout/ranuras.ts).
- [Hook de consultas y cancelación](../src/nucleo/api/useConsulta.ts).
- [Cliente API y sesión](../src/nucleo/api/cliente.ts).
- [Formato compartido actual](../src/nucleo/formato/formato.ts), cuya zona de navegador se conserva fuera del panel.
- [Detalle de Citas](../src/modulos/citas/Detalle.tsx).
- [Seguimiento de Intervenciones](../src/modulos/intervenciones/Seguimiento.tsx).
- [Detalle de Cupos](../src/modulos/lista-espera/DetalleCupo.tsx).
- [Configuración de pruebas y cobertura](../vite.config.ts).
- [Registro de cambios del frontend](changelog.md), a completar cuando se implemente.
