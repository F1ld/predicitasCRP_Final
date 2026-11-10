# Actividad 8 · Validación del flujo operativo en navegador

**Resultado aprobado el 09/11/2026.** Chromium usó las imágenes Docker de la aplicación con PostgreSQL 16 desechable y el artefacto de IA montado en solo lectura. Los contenedores de laboratorio compartieron loopback, sin puertos publicados.

| Imagen validada | ID |
|---|---|
| Frontend | `sha256:2c10706e7748a3ded73a99f66429b20978feff4d3cf0ebdd00c45037c77eb010` |
| Backend | `sha256:5a643854105f5971b522895508b1b4d1cc8cf8abd1ea5c17cc44706f7d780de4` |
| IA | `sha256:94b9e4b9618c87f966fcd5e16c53fe86b77bda6d990b554a99201f2bf796b5fb` |

1. Iniciar sesión como Recepción. Registrar un candidato seudonimizado para Traumatología en turno tarde y una cita de esa especialidad programada para el 13 de noviembre.
2. Ejecutar la predicción en el detalle. La cita sintética `CIT-E2E-ACT8` obtuvo riesgo alto con `LightGBM_v1.0.0` y mostró el rótulo de simulación. Abrir Intervenciones desde la cita, seleccionar plantilla y registrar consentimiento, envío, entrega y solicitud de liberación.
3. Confirmar la liberación, abrir el detalle desde «Ver cupo liberado» y ofrecer el cupo al candidato. El formulario de reasignación mantuvo deshabilitado el envío hasta marcar la confirmación humana y elegir el medio.
4. Registrar la reasignación y recargar el detalle. El cupo 23 conservó el estado Reasignado, el seudónimo del candidato y la reasignación 3. La cita de origen conservó el estado Liberada y su historial.
5. Abrir REP-01 desde el Panel con la fecha de la cita. El reporte mostró una fila. En REP-02 apareció la intervención con cupo liberado. REP-03 mostró el mismo cupo como reasignado al candidato.

El primer recorrido detectó que la respuesta del detalle de Cupos omitía el seudónimo tras la recarga. Se corrigió el contrato y se repitió la prueba desde una base desechable recién migrada. También pasaron 21 pruebas de ofertas y reasignación. [Registro del cambio en backend](../../backend/spec/changelog.md).

La prueba cubrió el alta manual, la intervención simulada y las consultas JSON de reportes. Los datos sintéticos se retiraron junto con el laboratorio.

El entorno Docker local quedó ejecutando los mismos IDs de frontend y backend. Se verificó HTTP 200 en el frontend, el campo nuevo en OpenAPI y el estado saludable del backend, PostgreSQL e IA. Las migraciones se ejecutaron en el laboratorio temporal.
