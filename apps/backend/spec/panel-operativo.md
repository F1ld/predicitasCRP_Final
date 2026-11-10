# Especificación del backend del Panel Operativo

Contrato funcional y técnico de la primera versión del Panel Operativo. Tras su implementación, este archivo conserva las reglas acordadas; los pendientes activos se mantienen en ToDo.md.

## Panel Operativo de Recepción — definición implementada

- Fecha de definición: **09/11/2026**, zona horaria de negocio `America/Lima`.
- Estado: **implementado y validado en laboratorio aislado**. Checklist de alcance completado; resultados y límites en [validacion-panel-operativo.md](validacion-panel-operativo.md). No desplegado al piloto.
- Alcance: backend del resumen diario y de los listados de pendientes del Panel Operativo.
- Referencia funcional: M07, Panel Operativo Principal; EDT 3.3.4.11 y requisitos RF-083, RF-085, RF-086 y RF-087 descritos en la especificación histórica. Esta definición concreta la primera versión y distingue los pendientes del panel de otras tareas permitidas por los módulos.
- Objetivo: responder **«¿Cuál es la situación actual de las citas y cupos programados para la fecha seleccionada y qué requiere atención?»**.

### 1. Resultado esperado y límites

El backend debe entregar indicadores verificables y pendientes consultables utilizando PostgreSQL como fuente de verdad. El frontend consumirá estos datos; no deberá descargar todas las bandejas ni calcular los totales a partir de páginas parciales.

El panel será un **adaptador de lectura compuesta**, no un nuevo propietario de las entidades operativas. Las acciones de registrar una intervención, confirmar una cita, liberar un cupo, ofrecerlo o confirmar una reasignación continuarán en sus respectivos módulos.

#### 1.1 Incluido en esta implementación

- [x] Resumen de citas del día por estado actual y por riesgo registrado.
- [x] Resumen de intervenciones relacionadas con esas citas, distinguiendo registros de intervención y citas distintas intervenidas.
- [x] Resumen de cupos de la jornada, disponibilidad accionable, ofertas en curso y recuperación efectiva.
- [x] Tres categorías de pendientes: citas sin intervención preventiva, intervenciones pendientes de respuesta y ofertas de cupo en curso.
- [x] Endpoint de resumen y endpoint paginado de pendientes.
- [x] Filtros comunes de fecha y especialidad, con fecha de hoy por defecto en Lima.
- [x] Autorización para Recepción y Administración.
- [x] Unificación acotada del criterio de selección de predicción en las consultas que deben coincidir con el panel.
- [x] Contratos de respuesta, errores, pruebas y documentación de dependencias.

#### 1.2 Fuera de alcance: no desarrollar ni alterar por esta tarea

| Área | Exclusión explícita |
|---|---|
| Frontend | No crear páginas React, tarjetas, gráficos, rutas, menús, estilos ni componentes en `apps/frontend`. Se define la API que posteriormente consumirán. |
| REP-01 | No implementar su consulta, vista, exportación ni agrupamientos. Es un pendiente separado que deberá reutilizar criterios compatibles. |
| Otros reportes | No completar REP-04/REP-05 ni corregir Excel o auditoría de exportación de REP-03 en esta entrega. |
| Operación | No crear endpoints de escritura del panel ni duplicar los workflows de Citas, Intervenciones o Lista de espera. |
| Reglas de negocio | No modificar estados, transiciones, consentimiento, opt-out, límites de reintento, elegibilidad ni confirmación humana. |
| IA | No ejecutar inferencias al consultar el panel, entrenar, promover modelos, cambiar umbrales, reclasificar probabilidades o llamar al motor HTTP. |
| Persistencia | No crear tablas de panel, snapshots, contadores persistidos, triggers ni vistas materializadas. |
| Cupos vencidos | No expirar ni reasignar cupos automáticamente desde una lectura. |
| Auditoría | No crear el visor administrativo ni registrar una operación de negocio por cada consulta del panel. Se conserva la trazabilidad HTTP existente. |
| Mensajería | No incorporar envíos reales, notificaciones automáticas ni nuevos textos de plantillas. |
| Infraestructura | No cambiar credenciales, Docker, bases, volúmenes ni servicios para implementar esta funcionalidad. |
| Históricos | No reconstruir el estado del sistema a una hora pasada ni producir cierres diarios inmutables. |
| Actualización | No introducir WebSockets, jobs, colas, caché, Redis ni sondeo automático en backend. Una petición nueva vuelve a consultar los datos. |

### 2. Semántica de fecha y universo de datos

#### 2.1 Parámetros comunes

| Parámetro | Tipo y validación | Comportamiento |
|---|---|---|
| `fecha` | Fecha ISO `YYYY-MM-DD`, opcional. | Si se omite, obtener la fecha del reloj inyectado convertida a `America/Lima`. |
| `especialidad` | Valor opcional del catálogo `ESPECIALIDADES`. | Si se omite, incluir todas las especialidades permitidas. No aceptar valores arbitrarios ni crear un valor de dominio `TODAS`. |

No se incluye filtro por médico, sede, estado, riesgo ni rango de fechas en la primera versión. Los desgloses por estado/riesgo no son filtros que reduzcan el total del panel. La sede del piloto continúa siendo la establecida por el dominio actual.

- [x] Usar `app.core.reloj.reloj` como dependencia temporal sustituible en pruebas y `LIMA` del mismo módulo.
- [x] Capturar una sola vez el instante de referencia de cada petición y devolverlo como `generado_en`, con zona horaria.
- [x] Construir `inicio = fecha a las 00:00 en Lima` y `fin = fecha siguiente a las 00:00 en Lima`.
- [x] Aplicar `campo_fecha >= inicio AND campo_fecha < fin` sobre timestamps con zona horaria.
- [x] No usar `23:59:59` como límite superior ni depender de la zona horaria del host o de la sesión de PostgreSQL.
- [x] Evitar convertir toda la columna a texto o a fecha en el filtro principal; preservar la posibilidad de utilizar índices por timestamp.

#### 2.2 Fecha de pertenencia de cada entidad

| Entidad | Pertenencia al universo diario |
|---|---|
| `Cita` | `fecha_hora_cita` dentro de `[inicio, fin)` y especialidad seleccionada. |
| `PrediccionIA` | Asociada a una cita del universo; se selecciona una sola por cita. Su fecha de inferencia no debe caer necesariamente en el día consultado. |
| `Intervencion` | Asociada a una cita del universo, aunque haya sido registrada o enviada otro día. |
| `CupoLiberado` | `fecha_hora_cupo` dentro de `[inicio, fin)` y especialidad del cupo seleccionada. No filtrar por `liberado_en`. |
| `Reasignacion` | Asociada a un cupo del universo, independientemente de `fecha_hora_reasigna`. |

Ejemplo: una intervención realizada el lunes para una cita del martes aparece en el panel del martes. Este panel no mide «trabajo realizado por los operadores durante el lunes».

#### 2.3 Estado actual, no reconstrucción histórica

- Consultar ayer muestra el estado **actualmente almacenado** de las entidades programadas para ayer.
- `generado_en` identifica cuándo se evaluaron los datos; no es un identificador de snapshot persistido.
- Los pendientes accionables exigen horario estrictamente futuro respecto de `generado_en`. Un horario igual al instante de referencia ya no se considera futuro.
- El resumen general incluye toda la jornada, con independencia de si sus horarios ya pasaron.
- No mover citas entre jornadas por la fecha de creación, inferencia, intervención o reasignación.

### 3. Fuentes de información y propiedad

| Tabla/modelo existente | Uso de lectura |
|---|---|
| `citas` / `Cita` | Identidad, fecha, especialidad, médico, paciente seudonimizado y estado actual. |
| `predicciones_ia` / `PrediccionIA` | Riesgo y metadata de la predicción seleccionada. |
| `intervenciones` / `Intervencion` | Estados, respuestas, intervenciones previas y opt-out. |
| `cupos_liberados` / `CupoLiberado` | Fecha del cupo, especialidad, estado y origen de liberación. |
| `reasignaciones` / `Reasignacion` | Evidencia de reasignación confirmada por una persona. |
| `auditoria_eventos` / `AuditoriaEvento` | Solo si hace falta enriquecer una oferta con su evento vigente. No usar como fuente principal del conteo de ofertas. |

El historial de estados de citas no es necesario para contar estados actuales. La lista de espera completa tampoco es necesaria para calcular el resumen; no se deben agregar consultas sin un campo concreto que las justifique.

La lectura transversal debe quedar documentada como excepción de lectura compuesta conforme a ADR-002. No se permite importar servicios operativos ajenos para ejecutar escrituras desde el panel ni usar HTTP interno entre módulos del backend.

### 4. Reglas exactas de conteo

#### 4.1 Citas

Unidad: **una fila de `Cita`, identificada por `id_cita`**.

- `citas.total`: número de citas del universo diario, sin excluir estados finales ni registros con desenlace.
- `citas.por_estado`: cantidad en cada estado actual del catálogo:
  - `RECIBIDA`.
  - `CONFIRMADA`.
  - `REPROGRAMADA`.
  - `CANCELADA`.
  - `LIBERADA`.
  - `ATENDIDA`.
  - `NO_SHOW`.
- `citas.por_riesgo`: `ALTO`, `MEDIO`, `BAJO` y `SIN_PREDICCION`, según la única predicción seleccionada por cita.
- Devolver todas las claves, incluso cuando su valor sea cero.
- `SIN_PREDICCION` es una categoría de presentación, no un nuevo nivel de riesgo persistido.
- No usar `target_no_show` como filtro del resumen ni como riesgo de la cita.

Invariantes obligatorios:

```text
sum(citas.por_estado.values()) == citas.total
sum(citas.por_riesgo.values()) == citas.total
todos los conteos son enteros >= 0
```

El riesgo describe el último resultado registrado, incluso si la cita ya terminó o fue cancelada. No se debe presentar como el número de citas todavía intervenibles; esa condición pertenece al bloque de pendientes.

#### 4.2 Predicción única por cita

- [x] Usar el orden `fecha_hora_inferencia DESC, id_prediccion DESC`.
- [x] Implementar selección determinista con `ROW_NUMBER() OVER (PARTITION BY id_cita ORDER BY ...)` y conservar `rn = 1`, o un SQL equivalente que garantice una sola fila.
- [x] Aplicar `LEFT JOIN` desde citas para conservar las que no tienen predicción.
- [x] No elegir el mayor riesgo entre predicciones históricas, no promediar probabilidades y no contar una cita varias veces.
- [x] No exigir que la predicción pertenezca al modelo activo: la primera versión usa la última predicción registrada según el orden anterior.
- [x] No recalcular el nivel a partir de la probabilidad: leer `nivel_riesgo` almacenado.

**Diferencia existente a resolver de forma acotada:** Citas ya ordena por timestamp e ID; `intervenciones/consultas.py::obtener_prediccion_reciente` ordena únicamente por ID. Alinear esta selección y la bandeja de elegibles que depende de ella. No aprovechar esta corrección para cambiar qué estados permiten intervenir o cuántos reintentos existen.

**Límite de interpretación:** `ia/repository.py::guardar_o_actualizar_prediccion` puede actualizar la fila de una misma versión y actualmente no reasigna explícitamente `fecha_hora_inferencia` en esa rama. Por ello, «última» en este contrato significa el orden de los timestamps almacenados; no garantiza identificar la última ejecución física de inferencia entre versiones. Añadir una nueva política de actualización del timestamp o un historial inmutable de inferencias sería otra tarea, que deberá explicitar impacto y pruebas. No cambiarla silenciosamente al desarrollar el panel.

#### 4.3 Intervenciones

Unidad del desglose: **una intervención por `id_intervencion`**, vinculada a las citas del universo.

| Campo | Regla |
|---|---|
| `intervenciones.total` | Todos los registros de intervención asociados a las citas seleccionadas, incluidos intentos fallidos y reintentos. |
| `intervenciones.citas_con_intervencion` | `COUNT(DISTINCT id_cita)` dentro de esos registros. |
| `intervenciones.por_estado` | Conteos por `PENDIENTE`, `ENVIADA`, `ENTREGADA`, `RESPONDIDA` y `FALLIDA`; incluir ceros. |

Invariantes:

```text
sum(intervenciones.por_estado.values()) == intervenciones.total
intervenciones.citas_con_intervencion <= citas.total
intervenciones.citas_con_intervencion <= intervenciones.total
```

Ejemplo: una cita con un intento `FALLIDA` y otro `ENTREGADA` produce dos intervenciones y una cita con intervención.

Los estados son una distribución **actual**, no un embudo histórico acumulado. Una intervención `RESPONDIDA` cuenta en ese estado, no también en `ENVIADA` y `ENTREGADA`. No crear un campo ambiguo `total_enviadas` sin un contrato histórico independiente. La cantidad de respuestas se obtiene de la clave `RESPONDIDA`.

#### 4.4 Cupos y recuperación

Unidad: **un cupo por `id_cupo_liberado`** de la jornada seleccionada.

| Campo | Regla |
|---|---|
| `cupos.total_liberados` | Todos los cupos del universo diario, cualquiera sea su estado actual. Es la cantidad de cupos formalmente registrados, no la cantidad de citas canceladas. |
| `cupos.por_estado` | Conteos almacenados por `DISPONIBLE`, `EN_OFERTA`, `REASIGNADO` y `EXPIRADO`, incluyendo ceros. |
| `cupos.disponibles_para_ofrecer` | Estado `DISPONIBLE`, `fecha_hora_cupo > generado_en` y sin registro de reasignación confirmada. |
| `cupos.ofertas_en_curso` | Estado `EN_OFERTA`, `fecha_hora_cupo > generado_en` y sin registro de reasignación confirmada. |
| `cupos.reasignados_confirmados` | Cantidad de cupos distintos con registro en `reasignaciones` y `confirmacion_humana IS TRUE`. |
| `cupos.tasa_recuperacion_pct` | `100 * reasignados_confirmados / total_liberados`; redondear una sola vez al final a dos decimales. |

- [x] Si `total_liberados == 0`, devolver `tasa_recuperacion_pct = null`; los demás conteos son cero.
- [x] Contar recuperación mediante `EXISTS` o un agregado único por cupo; no por cantidad de candidatos, ofertas o eventos.
- [x] Mantener `sum(cupos.por_estado.values()) == cupos.total_liberados`.
- [x] Mantener `0 <= reasignados_confirmados <= total_liberados` y porcentaje entre 0 y 100 cuando exista denominador.
- [x] Un cupo vencido todavía almacenado como `DISPONIBLE` permanece en ese desglose, pero no en `disponibles_para_ofrecer`.
- [x] No derivar recuperación de la cantidad de citas `LIBERADA`: el cupo formal y su reasignación son la fuente correspondiente.

El estado `REASIGNADO` y el registro confirmado deben concordar en datos válidos. Si no concuerdan, conservar la distinción entre el desglose de estados almacenados y la recuperación acreditada; registrar la incidencia en la validación de datos. No reparar filas ni inventar una confirmación desde una consulta GET.

### 5. Pendientes accionables

Los pendientes se calculan sobre el mismo universo y el mismo `generado_en` de la petición. Cada categoría tiene su propia unidad; **no sumar las tres en un único total general**.

#### 5.1 `CITAS_SIN_INTERVENCION`

Unidad: cita. Todas las condiciones son obligatorias:

1. Pertenece al universo diario.
2. `estado_actual == RECIBIDA`.
3. `fecha_hora_cita > generado_en`.
4. Predicción seleccionada con riesgo `ALTO` o `MEDIO`.
5. No existe **ninguna** intervención de esa cita, ni siquiera fallida o pendiente.
6. No existe opt-out vigente según la regla actual, incluyendo cualquier intervención de otras citas del mismo `paciente_anon_id` con `consentimiento_optout IS TRUE`.

Implementar existencia de intervención y opt-out con `NOT EXISTS`, correlacionando correctamente por cita y paciente. El filtro de especialidad/fecha del panel **no limita** la búsqueda de opt-out en las otras citas del paciente.

Esta alerta respeta el criterio documental de cita recibida sin intervención. No equivale a toda la bandeja de elegibles de M05: las confirmadas, reprogramadas y los reintentos permitidos continúan disponibles allí. No agregar reintentos a esta categoría ni cambiar su etiqueta para ocultar la diferencia.

Orden estable del listado: riesgo `ALTO` antes que `MEDIO`, probabilidad descendente, fecha de cita ascendente e ID de cita ascendente. Este orden organiza el contacto preventivo; no modifica la prioridad de atención clínica.

#### 5.2 `INTERVENCIONES_SIN_RESPUESTA`

Unidad: intervención. Condiciones:

1. Cita relacionada dentro del universo diario.
2. Estado de intervención `ENVIADA` o `ENTREGADA`.
3. `fecha_hora_respuesta IS NULL` y `respuesta_paciente IS NULL`.
4. Cita en un estado activo existente: `RECIBIDA`, `CONFIRMADA` o `REPROGRAMADA`.
5. Cita estrictamente futura respecto de `generado_en`.
6. Ausencia de opt-out vigente del paciente según la misma regla transversal.

`RESPONDIDA` con `SIN_RESPUESTA` no se considera espera abierta: representa un resultado ya registrado. `PENDIENTE` tampoco pertenece a esta categoría porque aún falta registrar el envío. No se añaden alertas de reintento ni de envío pendiente en esta primera versión.

Orden estable: fecha de cita ascendente, fecha de envío ascendente e ID de intervención ascendente. La respuesta JSON debe devolver los identificadores de intervención y cita para consultar su seguimiento.

#### 5.3 `OFERTAS_EN_CURSO`

Unidad: cupo. Condiciones:

1. Cupo dentro del universo diario.
2. `estado_cupo == EN_OFERTA`.
3. `fecha_hora_cupo > generado_en`.
4. No existe una reasignación confirmada de ese cupo.

El conteo proviene de `cupos_liberados`, no de sumar eventos `OFERTAR` de la bitácora. Un mismo cupo puede haber tenido varias ofertas históricas.

La primera versión requiere identificar el cupo y abrir su detalle; no necesita incluir la identidad del candidato ni el historial de oferta. Si se incorpora ese enriquecimiento durante la implementación, deberá reutilizar la proyección de ofertas de Lista de espera y su semántica de cierre, resolverse por lote y no alterar el conteo ni inferir un candidato sin evidencia.

Orden estable: fecha/hora de cupo ascendente e ID de cupo ascendente.

#### 5.4 Cupos disponibles: indicador, no cuarta categoría

`cupos.disponibles_para_ofrecer` cubre la alerta de disponibilidad. El detalle operativo continúa en Cupos. No añadir una cuarta categoría paginada dentro de esta primera versión.

La bandeja actual de cupos puede incluir disponibles vencidos; por tanto, un enlace sin filtros adicionales no garantiza el mismo total. La futura integración frontend deberá utilizar los filtros equivalentes o requerir una ampliación explícita de esa consulta. No afirmar que una bandeja genérica ya representa exactamente este indicador.

### 6. Contrato HTTP a desarrollar

#### 6.1 `GET /panel/resumen`

Query: `fecha` y `especialidad` según la sección 2.

Respuesta `200`, schema propuesto `PanelResumenOut`:

```json
{
  "fecha": "2026-11-09",
  "especialidad": null,
  "zona_horaria": "America/Lima",
  "generado_en": "2026-11-09T09:00:00-05:00",
  "citas": {
    "total": 10,
    "por_estado": {
      "RECIBIDA": 4, "CONFIRMADA": 2, "REPROGRAMADA": 1,
      "CANCELADA": 1, "LIBERADA": 1, "ATENDIDA": 1, "NO_SHOW": 0
    },
    "por_riesgo": {"ALTO": 3, "MEDIO": 2, "BAJO": 3, "SIN_PREDICCION": 2}
  },
  "intervenciones": {
    "total": 4,
    "citas_con_intervencion": 3,
    "por_estado": {
      "PENDIENTE": 0, "ENVIADA": 1, "ENTREGADA": 1,
      "RESPONDIDA": 1, "FALLIDA": 1
    }
  },
  "cupos": {
    "total_liberados": 4,
    "por_estado": {"DISPONIBLE": 1, "EN_OFERTA": 1, "REASIGNADO": 1, "EXPIRADO": 1},
    "disponibles_para_ofrecer": 1,
    "ofertas_en_curso": 1,
    "reasignados_confirmados": 1,
    "tasa_recuperacion_pct": 25.0
  },
  "pendientes": {
    "citas_sin_intervencion": 2,
    "intervenciones_sin_respuesta": 2,
    "ofertas_en_curso": 1
  }
}
```

Ejemplo ilustrativo de contrato; no corresponde a una consulta ejecutada ni a datos operativos reales. Los cupos y las citas tienen universos propios por su fecha programada; sus cantidades no deben equipararse.

- [x] `especialidad` debe reflejar el valor aplicado o `null` para todas.
- [x] Mantener claves de catálogos completas y estables.
- [x] Serializar conteos como enteros; tasa como número JSON o `null`, no string con `%`.
- [x] Mantener `pendientes.ofertas_en_curso == cupos.ofertas_en_curso` dentro de la respuesta.
- [x] Día sin registros: `200`, todos los conteos en cero, tasa `null`; no devolver `404`.

#### 6.2 `GET /panel/pendientes`

| Parámetro | Contrato |
|---|---|
| `fecha`, `especialidad` | Mismas reglas del resumen. |
| `tipo` | Obligatorio: `CITAS_SIN_INTERVENCION`, `INTERVENCIONES_SIN_RESPUESTA` u `OFERTAS_EN_CURSO`. |
| `limite` | Entero, por defecto 20, mínimo 1 y máximo 100. |
| `desplazamiento` | Entero, por defecto 0 y mínimo 0. |

Respuesta `200`, schema propuesto `PanelPendientesOut`:

```json
{
  "fecha": "2026-11-09",
  "especialidad": null,
  "zona_horaria": "America/Lima",
  "generado_en": "2026-11-09T09:00:00-05:00",
  "tipo": "CITAS_SIN_INTERVENCION",
  "total": 2,
  "limite": 20,
  "desplazamiento": 0,
  "items": [
    {
      "tipo": "CITAS_SIN_INTERVENCION",
      "id_cita": 101,
      "id_cita_externa": "CITA-DEMO-101",
      "paciente_anon_id": "PAC-DEMO-01",
      "fecha_hora_cita": "2026-11-09T14:00:00-05:00",
      "especialidad": "CARDIOLOGIA",
      "medico": "Medico de ejemplo",
      "estado_cita": "RECIBIDA",
      "id_prediccion": 501,
      "nivel_riesgo": "ALTO",
      "probabilidad_no_show": 0.7
    },
    {
      "tipo": "CITAS_SIN_INTERVENCION",
      "id_cita": 102,
      "id_cita_externa": "CITA-DEMO-102",
      "paciente_anon_id": "PAC-DEMO-02",
      "fecha_hora_cita": "2026-11-09T15:00:00-05:00",
      "especialidad": "PEDIATRIA",
      "medico": "Medico de ejemplo",
      "estado_cita": "RECIBIDA",
      "id_prediccion": 502,
      "nivel_riesgo": "MEDIO",
      "probabilidad_no_show": 0.4
    }
  ]
}
```

Campos mínimos de cada tipo de item:

| Tipo/schema propuesto | Campos |
|---|---|
| `CitaSinIntervencionOut` | Los del ejemplo: discriminador `tipo`, IDs de cita/predicción, ID externo, paciente seudonimizado, fecha, especialidad, médico, estado y riesgo/probabilidad. |
| `IntervencionSinRespuestaOut` | `tipo`, `id_intervencion`, `id_cita`, `id_cita_externa`, `paciente_anon_id`, `fecha_hora_cita`, `especialidad`, `medico`, `estado_cita`, `canal_contacto`, `estado_intervencion`, `fecha_hora_envio`. |
| `OfertaEnCursoOut` | `tipo`, `id_cupo_liberado`, `id_cita_origen`, `fecha_hora_cupo`, `especialidad`, `medico`, `estado_cupo`, `origen_liberacion`. |

- [x] Definir modelos Pydantic explícitos y una unión discriminada por `tipo`; no usar un diccionario libre con campos arbitrarios.
- [x] Cada respuesta contiene solo items del tipo solicitado.
- [x] `total` es el número completo de pendientes después de filtrar y **antes** de paginar.
- [x] Un desplazamiento fuera de los resultados devuelve `items: []` y conserva `total`; no es un error.
- [x] Aplicar los órdenes estables de la sección 5 antes de `LIMIT/OFFSET`.
- [x] Los IDs permiten al consumidor abrir detalles existentes. No devolver URLs del frontend ni inventar nuevas acciones de escritura.
- [x] Mantener fechas con zona horaria y probabilidad JSON numérica en `[0,1]`; no cambiar por ello los tipos de endpoints IA existentes.

#### 6.3 Autorización y errores

- [x] Reutilizar `requiere_roles("ADMINISTRADOR", "RECEPCION")` y el principal público de Auth.
- [x] Sesión ausente/inválida: respuesta vigente de autenticación (`401`).
- [x] Usuario `TECNICO_IA`: `403`, sin entregar datos del panel.
- [x] Fecha, especialidad, tipo o paginación inválidos: `422`, con el envelope existente `{"error":{"codigo","mensaje","campos"}}`.
- [x] Reutilizar los manejadores y la trazabilidad HTTP existentes; no crear un formato de error paralelo.
- [x] Un fallo real de base de datos debe seguir el manejo de errores existente, nunca convertirse en un resumen vacío con `200`.
- [x] No devolver hashes de contraseña, tokens, datos de sesión ni JSON íntegro de auditoría. Usar únicamente los campos de salida definidos.

### 7. Diseño de consultas y consistencia

#### 7.1 Composición SQL propuesta

Expresiones/CTE reutilizables dentro del adaptador del panel. El CTE `citas_con_riesgo` usa `MATERIALIZED` en PostgreSQL para evitar un plan con nested loops costosos, según la medición documentada:

1. `citas_base`: IDs y campos necesarios de las citas del día/especialidad.
2. `predicciones_ordenadas` y `prediccion_por_cita`: una predicción por cita, con el orden definido.
3. `citas_con_riesgo`: unión externa uno a uno con esa predicción.
4. Agregados de citas por estado y riesgo sobre ese universo sin duplicados.
5. Agregados de intervenciones vinculadas a `citas_base`, sin unirlas a todas las predicciones.
6. `cupos_base`: cupos del día/especialidad, con comprobación de reasignación mediante existencia.
7. Predicados reutilizables de las tres categorías, que alimenten conteos y listados.

Para agregados condicionales usar `COUNT ... FILTER (WHERE ...)` o `CASE` equivalente. Para ausencia/presencia usar `NOT EXISTS`/`EXISTS`. No introducir `COUNT(DISTINCT ...)` como parche general de un JOIN multiplicado sin verificar el resto de agregados.

Error que debe evitarse:

```text
1 cita x 2 predicciones x 3 intervenciones = 6 filas de JOIN
Resultado correcto: 1 cita, 1 riesgo seleccionado, 3 intervenciones.
```

#### 7.2 Lectura coherente dentro de cada respuesta

- [x] Preferir una sola sentencia SQL para los agregados del resumen, componiendo subconsultas/CTE. PostgreSQL evaluará la lectura bajo un snapshot de esa sentencia.
- [x] Para el listado, obtener `total` y página en una lectura coherente, incluida una página vacía. Si se usan varias sentencias, fijar una transacción de lectura con snapshot consistente solo para este caso de uso.
- [x] No cambiar globalmente el nivel de aislamiento de `core/database.py` por el panel.
- [x] No confundir un mismo `generado_en` con consistencia de base de datos: fijar el reloj no impide cambios concurrentes entre sentencias.
- [x] No tomar `FOR UPDATE`, escribir entidades ni ejecutar `commit()` de negocio en estas lecturas. El ciclo de vida de sesión/transacción debe seguir la infraestructura existente.

#### 7.3 Correspondencia entre contador y listado

El contador de cada categoría y su listado deben reutilizar el **mismo predicado SQL**, no dos traducciones manuales de una regla. En pruebas con datos y reloj fijos, el contador del resumen debe coincidir con `total` del listado.

Dos peticiones HTTP independientes pueden diferir si hubo cambios de estado o pasó un horario entre ambas. Esta primera versión no garantiza navegación sobre un snapshot congelado ni acepta un parámetro `generado_en` del cliente para reconstruirlo. El listado informa su propio instante y estado actual; el consumidor podrá actualizar el resumen.

#### 7.4 Rendimiento

- [x] Calcular agregados en PostgreSQL; no cargar todas las filas ORM y contarlas en Python.
- [x] Evitar N+1: no consultar predicción, intervenciones, opt-out u oferta individualmente para cada item.
- [x] Mantener el número de consultas acotado e independiente del número de citas, y registrar el número observado en la validación.
- [x] Proyectar solo columnas necesarias y paginar listados.
- [x] Revisar índices existentes antes de proponer migraciones. Las fechas de citas y cupos ya tienen índice en los modelos revisados; `Intervencion.id_cita` también.
- [x] Evaluar con `EXPLAIN` y, en una base de pruebas representativa, `EXPLAIN ANALYZE`, las consultas por fecha/especialidad, selección de predicción y opt-out transversal.
- [x] Considerar índices adicionales sobre predicciones, intervención/opt-out o fecha/especialidad solo con evidencia del plan y volumen. Documentar costo de escritura y decisión; no crear índices preventivos por costumbre.
- [x] Si se justifica un índice, agregar una migración Alembic específica y reversible. No alterar datos de negocio, tablas ni secuencias por ese motivo.

### 8. Archivos a crear, modificar y conservar

Las rutas de código de esta sección son relativas a `apps/backend`, salvo que se indique «raíz». La matriz conserva el alcance acordado; los archivos obligatorios ya están creados y las ampliaciones condicionales solo se aplican cuando corresponde. La ejecución real se registra en changelog y validación.

#### 8.1 Archivos obligatorios creados

| Archivo | Responsabilidad |
|---|---|
| `app/modules/panel/__init__.py` | Declarar el paquete, sin efectos laterales ni consultas al importar. |
| `app/modules/panel/router.py` | Dos rutas GET, dependencias de DB/auth/reloj, parámetros validados y `response_model`. Sin SQL ni commits. |
| `app/modules/panel/schemas.py` | Modelos del resumen, desgloses, tipos de pendientes, paginación e items discriminados. |
| `app/modules/panel/service.py` | Resolver fecha por defecto, límites diarios y referencia temporal; coordinar consultas y construir respuestas. |
| `app/modules/panel/consultas.py` | SQLAlchemy de lectura compuesta, predicados compartidos, agregados y consultas paginadas. |
| `tests/panel/test_resumen.py` | Universo diario, conteos, estados, riesgos e invariantes del resumen. |
| `tests/panel/test_pendientes.py` | Condiciones de cada categoría, orden, paginación y coincidencia de conteos. |
| `tests/panel/test_api.py` | Contratos, roles, validación, errores y ausencia de escrituras/inferencia. |

Crear `tests/panel/conftest.py` únicamente si se necesitan fixtures propias; reutilizar primero las existentes. No duplicar infraestructura de conexión, login o reloj.

#### 8.2 Modificar con alcance acotado

| Archivo/área existente | Cambio requerido o condicionado |
|---|---|
| `app/main.py` | Importar y registrar el router del panel. No cambiar lifespan, motor IA, middleware, CORS ni rutas existentes. |
| `app/modules/intervenciones/consultas.py` | Alinear selección de predicción con timestamp/ID y asegurar que el filtrado de riesgo se aplique al resultado seleccionado, no a una versión histórica. Mantener elegibilidad actual de M05. |
| `app/modules/intervenciones/service.py` | Ajustar solo si la alineación anterior vuelve redundante o incorrecta la selección/sustitución de predicción de la bandeja. Evitar refactorización amplia. |
| Pruebas de Intervenciones existentes | Añadir regresión con varias versiones, cambios de riesgo y empate temporal, conservando consentimiento, opt-out, estados y reintentos. |
| `app/modules/citas/consultas.py` | Solo si se extrae una primitiva compartida para la selección de predicción. Su comportamiento público actual debe conservarse. |
| Documentación de arquitectura, raíz `docs/arquitectura/MAPA_DEPENDENCIAS_Y_ESCRITURAS.md` | Registrar Panel como lector compuesto, modelos leídos y ausencia de escritura transversal. |
| `app/bootstrap/limites.py` y `tests/sistema/test_limites_d_fase4.py` | Incorporar el adaptador de lectura a los controles que correspondan. Identificar el mecanismo vigente antes de editar; no crear una whitelist genérica de imports. |
| `README.md` del backend | Describir rutas, roles, fecha de pertenencia, unidades, ejemplos y limitaciones temporales. |
| `spec/changelog.md` | Registrar los cambios y la validación real cuando se implemente, no anticipar un cierre exitoso. |

No crear un módulo genérico de «últimas filas» en `core` con conocimiento de entidades de negocio. Si se comparte una proyección, ubicarla en el contrato de lectura del propietario y justificar la dependencia. Si se mantienen expresiones equivalentes en varios adaptadores, exigir pruebas de paridad para evitar divergencias.

#### 8.3 Crear o modificar solo si existe una necesidad demostrada

- `app/modules/panel/reglas.py`: solo si hay reglas puras con suficiente entidad; no crear una capa vacía.
- `app/modules/panel/public.py`: solo si aparece un consumidor interno real; el router no obliga a publicarlo.
- Migración Alembic: exclusivamente si el análisis demuestra necesidad de índices nuevos.
- Proyecciones públicas de Citas/IA/Intervenciones: si se decide compartir una selección determinista sin importar servicios privados ajenos.
- Documento de contrato incremental, raíz `contracts/backend/panel.v1.md` o equivalente acordado: registrar la API nueva y ejemplos comprobables sin alterar el snapshot histórico.

#### 8.4 Conservar sin cambios funcionales por esta entrega

- `app/modules/*/models.py`, tablas, restricciones, FK, secuencias y ownership de escritura.
- `app/bootstrap/models.py`: no hay modelos nuevos que registrar.
- `app/core/database.py`, configuración global de conexiones y aislamiento.
- `app/core/dominio.py`: no hay estados ni catálogos nuevos de negocio. Los tipos de pendiente pertenecen al contrato del panel.
- `app/modules/ia/repository.py`, motor HTTP y servicio IA: el panel lee predicciones; no cambia su persistencia ni ejecución.
- Reglas de consentimiento, opt-out y reintentos de Intervenciones.
- Flujos de liberación, oferta, rechazo y confirmación de Lista de espera.
- Servicios de escritura de auditoría y workflows existentes.
- Router/servicio de reportes REP-02 y REP-03, salvo otra tarea explícita.
- Frontend, archivos de entorno, infraestructura, datasets, artefactos y modelo activo.
- Snapshot histórico raíz `contracts/backend/openapi.actual.v0.5.0.json`: no sobrescribirlo para incluir la API nueva. Si se genera un OpenAPI actualizado, guardarlo como artefacto nuevo, identificado y diferenciado.

### 9. Matriz de pruebas de aceptación

Requisitos de verificación de la entrega; usar datos sintéticos controlados, el reloj sustituido y una base de pruebas. No usar seed/reset ni ejecutar pruebas con escritura sobre la base operativa del piloto.

| ID | Escenario | Resultado obligatorio |
|---|---|---|
| PAN-01 | Fecha sin citas ni cupos. | `200`, claves completas, ceros y tasa `null`. |
| PAN-02 | Citas en los siete estados. | Cada una cuenta una vez; suma de estados igual al total. |
| PAN-03 | Riesgos alto, medio, bajo y cita sin predicción. | Distribución completa y suma igual al total. |
| PAN-04 | Una cita con varias predicciones y varias intervenciones. | Una cita y un riesgo; intervenciones contadas individualmente, sin multiplicación. |
| PAN-05 | Predicción antigua alta y reciente baja; caso inverso. | Selección de la reciente según timestamp/ID y alerta solo cuando corresponda. |
| PAN-06 | Predicciones con igual timestamp e IDs distintos. | Mayor ID como desempate estable. |
| PAN-07 | Mayor ID con timestamp anterior a otra predicción. | Prevalece el timestamp más reciente; no seleccionar solo por ID. |
| PAN-08 | Reintento fallido seguido de intervención entregada. | Dos intervenciones, una cita intervenida; no aparece como cita sin intervención. |
| PAN-09 | Cita recibida, futura, alto/medio riesgo y sin intervención. | Incluida en `CITAS_SIN_INTERVENCION`. |
| PAN-10 | Misma cita confirmada/reprogramada. | Excluida de esa alerta; no eliminar por ello su elegibilidad vigente en M05. |
| PAN-11 | Cita con intervención fallida o pendiente. | Excluida de «sin intervención», aunque M05 pueda permitir otro paso. |
| PAN-12 | Opt-out en otra cita de igual paciente, otra fecha/especialidad. | Excluida de los pendientes de contacto; no limitar la comprobación al filtro diario. |
| PAN-13 | Cita pasada o exactamente en `generado_en`. | Sigue en resumen; no en pendientes futuros. |
| PAN-14 | Intervención enviada/entregada sin respuesta en cita activa futura. | Incluida en pendientes de respuesta. |
| PAN-15 | Intervención respondida con resultado `SIN_RESPUESTA`, pendiente o fallida. | No incluida en espera de respuesta. |
| PAN-16 | Intervención abierta en cita cancelada, liberada o finalizada. | Cuenta en su resumen por estado, no en pendiente accionable. |
| PAN-17 | Cupo disponible futuro y disponible vencido. | Ambos en estado almacenado; solo el futuro en disponibilidad accionable. |
| PAN-18 | Cupo en oferta futuro con múltiples eventos históricos de oferta. | Una oferta en curso, no una por evento. |
| PAN-19 | Cupo con reasignación humana confirmada. | Una recuperación; no disponible ni oferta pendiente. |
| PAN-20 | Dos cupos recuperados de cuatro liberados. | Tasa 50; límites 0/100 y denominador vacío correctamente resueltos. |
| PAN-21 | Estado de cupo y existencia de reasignación discordantes. | No inventar ni reparar; conservar conteos por fuente y excluir de acciones si hay confirmación. |
| PAN-22 | Registro exacto a las 00:00, justo antes y a las 00:00 del día siguiente. | Inclusión/exclusión conforme al intervalo de Lima, también con timestamps equivalentes en UTC. |
| PAN-23 | Especialidades mezcladas. | Mismo filtro en citas, intervenciones y cupos; opt-out sigue siendo transversal. |
| PAN-24 | Intervención/reasignación realizada otro día. | Pertenece al panel según fecha programada de cita/cupo, no fecha del evento. |
| PAN-25 | Peticiones de resumen y lista con mismo reloj/datos. | Cada contador igual al `total` de su categoría; sin total global de unidades mezcladas. |
| PAN-26 | Paginación, empates de orden y offset fuera de rango. | Orden determinista, total sin paginar, página vacía válida. |
| PAN-27 | Recepción, Administrador, Técnico IA y sin sesión. | Acceso permitido a los dos primeros; `403`/`401` según corresponda. |
| PAN-28 | Fecha/tipo/especialidad inválidos y límites negativos/excesivos. | `422` y formato de error del proyecto. |
| PAN-29 | Consulta de endpoints del panel. | Sin DML, locks de escritura, nuevos eventos de negocio ni llamadas al motor IA. |
| PAN-30 | Aumento de cantidad de citas con relaciones. | Número de consultas acotado; no N+1 ni descarga completa para contar en Python. |
| PAN-31 | Listado fuera de rango y cambios concurrentes durante agregación. | Total/página coherentes bajo la estrategia de snapshot elegida. |
| PAN-32 | Fallo de DB en la consulta. | Error real conforme al manejo vigente; no ocultarlo con ceros. |
| PAN-33 | Base fija y consultas repetidas. | Mismos resultados/orden; no efectos laterales persistidos. |
| PAN-34 | Motor IA no disponible al consultar. | La lectura no depende del motor ni solicita inferencia; usar los datos persistidos. |

En PAN-29 distinguir las escrituras de preparación de fixtures/login de las realizadas por la lectura bajo prueba. No exigir una base completamente inmutable mientras se está creando el escenario de prueba.

### 10. Secuencia de implementación completada

1. [x] Confirmar el estado real del checkout al iniciar; conservar cambios ajenos y releer contratos relevantes.
2. [x] Formalizar schemas, tipos de pendiente y ejemplos de API conforme a este documento.
3. [x] Implementar y probar el cálculo puro de fecha, límites diarios y reloj único por petición.
4. [x] Alinear la selección de predicción en las consultas afectadas de Intervenciones y añadir pruebas de regresión antes de usarla como referencia.
5. [x] Construir universos diarios, selección de predicción y predicados reutilizables del panel.
6. [x] Implementar agregados del resumen y sus invariantes con estrategia de lectura coherente.
7. [x] Implementar listados por tipo, total, orden y paginación.
8. [x] Integrar service y router con auth, DB, reloj, response models y manejadores existentes.
9. [x] Registrar el router en `app/main.py`.
10. [x] Completar la matriz de pruebas aplicable, usando base de pruebas y reloj controlado.
11. [x] Revisar consultas, planes de ejecución y ausencia de N+1; justificar cualquier índice adicional antes de migrarlo.
12. [x] Ejecutar pruebas focalizadas de Panel e Intervenciones/Citas afectadas y los controles vigentes de arquitectura/contratos.
13. [x] Ejecutar la suite backend exigida por el repositorio y su configuración de cobertura; separar fallos nuevos de deudas preexistentes con evidencia. No desactivar gates para declarar cierre.
14. [x] Verificar OpenAPI generado y compatibilidad: nuevas rutas presentes, contratos previos preservados, snapshot histórico intacto.
15. [x] Documentar resultados reales, archivos modificados, limitaciones y comandos de validación en README/changelog.
16. [x] Retirar los pendientes completados de este ToDo solo al contar con implementación y evidencia de aceptación.

### 11. Criterio de cierre del backend del panel

La entrega estará terminada cuando las dos rutas estén integradas, autorizadas y documentadas; los conteos cumplan las unidades e invariantes definidos; cada categoría tenga listado paginado coherente; las lecturas no ejecuten operaciones de negocio; y las pruebas acrediten permisos, fechas, duplicados, opt-out, cupos, consistencia y regresiones de los criterios ajustados.

La existencia del backend del panel **no acredita** frontend terminado, REP-01 implementado, auditoría administrativa completa, reportes IA cerrados ni aceptación integral del piloto. Esos pendientes conservan su alcance propio.

### 12. Referencias de implementación

- [Resultados de validación y limitaciones](validacion-panel-operativo.md).
- [Registro de cambios](changelog.md).

- [Especificación histórica de M07](../../../docs/historico/diseno/ESPECIFICACION_SISTEMA_Y_ESTADO_ACTUAL.md), sección 1.7. Describe la intención funcional; sus porcentajes históricos no son un diagnóstico actualizado del código.
- [Decisiones de arquitectura](../../../docs/arquitectura/DECISIONES.md), especialmente ADR-002, ADR-003 y ADR-008.
- [Mapa de dependencias y escrituras](../../../docs/arquitectura/MAPA_DEPENDENCIAS_Y_ESCRITURAS.md).
- [Reglas y reloj compartido](../app/core/reloj.py).
- [Catálogos de dominio](../app/core/dominio.py).
- [Consulta actual de Citas](../app/modules/citas/consultas.py), selección por timestamp/ID e intervalo diario.
- [Consultas de Intervenciones](../app/modules/intervenciones/consultas.py), selección de predicción y opt-out transversal.
- [Reglas de Intervenciones](../app/modules/intervenciones/reglas.py), límites y estados del flujo actual.
- [Modelos de Lista de espera y cupos](../app/modules/lista_espera/models.py), unicidades y confirmación humana.
- [Proyección de ofertas](../app/modules/lista_espera/ofertas.py), si se requiere enriquecimiento de detalle.
- [Persistencia de predicciones](../app/modules/ia/repository.py), límite de actualización de timestamp descrito en 4.2.
- [Contratos backend y compatibilidad](../../../contracts/backend/COMPATIBILIDAD.md).
