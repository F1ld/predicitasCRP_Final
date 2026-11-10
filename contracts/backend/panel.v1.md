# Panel Operativo — contrato incremental v1

Fecha: 09/11/2026. Extensión aditiva de la API backend; no sustituye ni modifica
`openapi.actual.v0.5.0.json`, snapshot histórico congelado.

## Operaciones

Autenticación Bearer vigente; roles `RECEPCION` y `ADMINISTRADOR`. Técnico IA
recibe `403`; sin sesión, `401`. Ninguna operación del panel escribe datos,
audita una acción de negocio, expira cupos o llama al motor predictivo.

| Método/ruta | Query | Respuesta |
|---|---|---|
| `GET /panel/resumen` | `fecha?: YYYY-MM-DD`, `especialidad?: ESPECIALIDADES` | `PanelResumenOut` |
| `GET /panel/pendientes` | Los anteriores; `tipo` obligatorio; `limite=20` (1..100), `desplazamiento=0` (>=0) | `PanelPendientesOut` |

Tipos: `CITAS_SIN_INTERVENCION`, `INTERVENCIONES_SIN_RESPUESTA`, `OFERTAS_EN_CURSO`.
Fechas/catálogos/tipos/paginación inválidos: `422`, envelope
`{"error":{"codigo":"VALIDACION","mensaje":"...","campos":{}}}`.
Un universo o página vacíos devuelve `200`; total sin paginar y arrays vacíos.

## Semántica estable

- Fecha omitida: hoy del reloj del servidor en `America/Lima`.
- Intervalo diario `[00:00, 00:00 del día siguiente)`, timezone aware.
- Citas/intervenciones por fecha programada de cita; cupos/reasignaciones por
  fecha programada del cupo. Las fechas de registro de eventos no recortan este panel.
- Estado actual de esa jornada, sin reconstrucción histórica.
- Una predicción por cita: `fecha_hora_inferencia DESC, id_prediccion DESC`.
  Se usan timestamps almacenados, sin cambiar la política del upsert de IA.
- Estados de intervención son categorías actuales exclusivas, no envíos acumulados.
- Recuperación: cupos con reasignación humana confirmada / total de cupos
  formalmente liberados. Porcentaje numérico redondeado a dos decimales; `null`
  cuando no hay denominador. No confundir confirmaciones con estado almacenado.
- Disponible/oferta accionable: futuro estricto y sin reasignación confirmada.
- Sin intervención: cita `RECIBIDA` futura, riesgo alto/medio, ninguna intervención
  previa y sin opt-out del paciente, incluyendo otras fechas y especialidades.
- Sin respuesta: intervención enviada/entregada con respuesta y fecha de respuesta
  nulas, cita activa futura y ausencia de opt-out del paciente.
- No se suman pendientes de entidades distintas.

## Respuestas y campos

Las dos respuestas incluyen `fecha`, `especialidad` (o `null`), `zona_horaria`
(`America/Lima`) y `generado_en` ISO con offset.

`PanelResumenOut` incluye `citas` (total, estados, riesgos con SIN_PREDICCION),
`intervenciones` (total, citas distintas, estados), `cupos` (total, estados,
disponibles, ofertas, confirmaciones, porcentaje) y `pendientes` (tres conteos).
Los catálogos de conteos conservan claves con cero.

`PanelPendientesOut` incluye `tipo`, `total`, `limite`, `desplazamiento` e `items`,
unión discriminada por `tipo` de los tres schemas concretos. IDs de entidades
permiten abrir detalles existentes; no se incluyen URLs frontend ni acciones nuevas.
Probabilidades JSON numéricas en `[0,1]`, conteos enteros no negativos.

Una sentencia SQL por respuesta conserva la coherencia de sus bloques y de total
con página, incluso fuera de rango. Peticiones independientes pueden cambiar por
actividad concurrente o por paso del tiempo; `generado_en` no congela snapshots.

Schemas ejecutables: `apps/backend/app/modules/panel/schemas.py`. OpenAPI actual:
`GET /openapi.json`. Definición completa, ejemplos y matriz de escenarios:
[especificación del panel](../../apps/backend/spec/panel-operativo.md).

## Ejemplos de solicitudes

```http
GET /panel/resumen?fecha=2026-11-09&especialidad=CARDIOLOGIA
GET /panel/pendientes?fecha=2026-11-09&tipo=CITAS_SIN_INTERVENCION&limite=20&desplazamiento=0
```

No cambia el contrato público ni los tipos de endpoints existentes de Citas,
Intervenciones, IA, Cupos o Reportes. La selección de predicción en Intervenciones
queda alineada con Citas; no se cambian estados intervenibles ni reintentos.
