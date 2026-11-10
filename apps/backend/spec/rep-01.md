# REP-01 · Consulta del reporte operativo diario

`GET /reportes/rep-01` es una consulta de solo lectura para el rol `RECEPCION`.

| Parámetro | Regla |
|---|---|
| `fecha` | Obligatoria, en formato `YYYY-MM-DD`. |
| `especialidad` | Opcional. Admite `CARDIOLOGIA`, `TRAUMATOLOGIA` o `PEDIATRIA`. |
| `nivel_riesgo` | Opcional. Admite `BAJO`, `MEDIO` o `ALTO`. |

Devuelve HTTP 200 con `fecha`, `filtros`, `total` y `grupos`. Cada grupo contiene `especialidad`, `franja_horaria`, `subtotal` y `filas`. Cada fila contiene `hora` local, `id_cita_externa`, `especialidad`, `medico`, `antelacion_dias`, `probabilidad_no_show`, `nivel_riesgo`, `estado_intervencion` y `respuesta_paciente`. Un día sin coincidencias devuelve total cero y grupos vacíos. Los parámetros inválidos devuelven 422. La sesión ausente y el rol no autorizado devuelven 401 y 403, respectivamente.

## Selección y agrupamiento

- Se incluyen las citas programadas en el día de Lima, desde su inicio inclusive hasta el inicio del día siguiente exclusivo, en todos los estados de cita.
- La predicción elegida es la más reciente por fecha de inferencia e ID. El filtro de riesgo se aplica a esa predicción. Al omitirlo, se incluyen las citas sin predicción, con probabilidad y nivel nulos.
- La intervención elegida es la más reciente por fecha de envío e ID. Estado y respuesta provienen de ese mismo intento. Ambos son nulos si no existe intervención. Los datos asociados reflejan lo registrado al consultar, incluso al elegir una fecha pasada.
- El agrupamiento usa especialidad y hora local, con `MANANA` antes de las 13:00 y `TARDE` desde esa hora. Las filas se ordenan por hora y, en caso de empate, por ID interno. El total y los subtotales se calculan con las mismas filas filtradas.
- La consulta usa una sola sentencia SQL, sin escrituras ni llamadas a IA. Los listados de pendientes del Panel aplican restricciones adicionales, por lo que sus totales solo se comparan usando universos equivalentes.

El alcance comprende el backend. La vista, las exportaciones y el despliegue al piloto quedan fuera de esta entrega.

## Validación

La ejecución focalizada en PostgreSQL 16 desechable, con las migraciones vigentes y el rol operativo, registró **145 pruebas aprobadas**. Incluyó REP-01, Panel, lecturas y exportación de REP-02, acceso a REP-03 y su alias, y controles de fronteras del backend. Las pruebas de REP-01 comprobaron el permiso de Recepción, los límites del día y de la franja, los desempates, los nulos y una única sentencia de lectura sin llamadas a IA. La ejecución cubrió esos módulos y casos de regresión.
