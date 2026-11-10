# ToDo del backend

Archivo de tareas, decisiones y cambios pendientes del backend de PrediCitas CRP. Cuando una tarea se completa, se registra en changelog y se retira de este archivo, conservando la especificación vigente cuando corresponde.

## Panel Operativo de Recepción

**Backend implementado y validado el 09/11/2026.** No quedan tareas pendientes dentro del alcance backend definido para esta primera versión.

- [Especificación funcional y técnica](panel-operativo.md).
- [Validación: pruebas, cobertura, rendimiento y limitaciones](validacion-panel-operativo.md).
- [Registro de cambios](changelog.md).
- [Contrato incremental de la API](../../../contracts/backend/panel.v1.md).

La implementación incluye `/panel/resumen` y `/panel/pendientes`; no está desplegada al piloto. La consulta de REP-01 se implementó por separado. Su vista y el despliegue al piloto siguen fuera del alcance del backend de consulta.

## REP-01 · Consulta del reporte operativo diario

Backend implementado. [Contrato y validación](rep-01.md).
