# Fase 10 — cerrada con salvedades

Punto de partida: `9d19cdf`. Las pruebas que escriben se ejecutan sobre
volúmenes de laboratorio. El entorno operativo se consulta por HTTP.

## Smoke local

```powershell
./scripts/smoke.ps1
```

Por defecto verifica salud, readiness PostgreSQL y frontend. En un
laboratorio, pasa una credencial demo obtenida con `Get-Credential` mediante
`-Credential` y `-AllowWrites` para verificar login y lectura. Para inferencia,
añade `-PredictAppointmentId` con una cita sintética elegible. La autorización
explícita se exige también para login porque puede escribir auditoría.
El script acepta orígenes locales, evita redirecciones y omite la salida
de credenciales, tokens y datos de citas.

Se comprobó el modo de solo lectura sobre el stack operativo y el rechazo
de inferencia sin autorización de escritura.

## Revisión inicial de contratos y límites

El OpenAPI operativo se comparó con `contracts/backend/openapi.actual.v0.5.0.json`.
Se añadió GET `/health/ready` en fase 9. Las operaciones anteriores
conservaron sus definiciones. La única diferencia de esquemas fue el campo
opcional y anulable `observacion` de `CheckInOut`. El snapshot queda
conservado para revisión de compatibilidad.

La búsqueda inicial en código activo no encontró imports de ML en backend,
imports de backend o SQL operativo en IA ni referencias a claves internas
de IA en el frontend. Quedan pendientes los controles completos de ciclos,
imágenes y logs, la matriz E2E y los ensayos de fallos y recuperación.

## Regresión inicial

- Backend: 399 aprobadas, dos omitidas en la selección general y
  93.97% de cobertura. Se ejecutó por separado el ensayo de
  arranque sin IA y recuperación. Pasaron los controles de concurrencia
  de predicción, cambio de cita y rollback tras flush.
- Frontend: 455 aprobadas, 56 fallos de Citas y 92,15% de líneas.
  Coinciden por archivo y nombre con los fallos diferidos de fase 8.
- IA: 241 aprobadas y 89.95% de cobertura sobre app, training,
  datasets y management. El modelo aprobado se montó en solo lectura.
  Con modelo ausente o bytes corruptos en una carpeta temporal, liveness
  devolvió 200 y readiness y la consulta del modelo devolvieron 503.

Se mantuvieron los umbrales de cobertura. El laboratorio backend se
detuvo y los servicios operativos conservaron su estado. Quedan el
recorrido E2E autenticado, restauración de respaldo, seguridad y
medición de arranque, latencias y RAM.

[Resumen de línea base](linea-base-20261108.json).

## Integración, restauración y seguridad

El laboratorio Compose usó volumen nuevo, redes internas e imágenes de
`9d19cdf`. Se probaron login, identidad, lectura y permisos de los tres
roles por HTTP, más predicción individual y por lote con persistencia.
El frontend respondió 200 por HTTP. El recorrido autenticado usa un
cliente HTTP y no automatiza la interfaz en navegador.

Se restauró un respaldo sintético en otra base del mismo PostgreSQL de
laboratorio y coincidieron las huellas de usuarios, citas, predicciones
y auditoría. Se comprobó una vuelta a la revisión anterior y el
upgrade a head sobre esa copia, con recuentos conservados. La instalación
nueva y el reinicio también pasaron.

Pasaron nueve carreras de cupos, reasignaciones y otros flujos, con espera
PostgreSQL observada y un solo éxito efectivo. El arnés histórico abrió
dos ciclos de vida FastAPI en la primera ejecución y falló en el cierre.
La adaptación usa un ciclo de vida común para la prueba, sin cambiar
el backend.

Se inspeccionaron los nombres de variables en backend, IA y frontend
y la ausencia de /app/.env. La búsqueda de patrones de claves en código
activo y de valores configurados en las últimas mil líneas de cada
servicio no dio coincidencias. Es una revisión acotada, sin publicar
valores ni contenido de logs.

Con imágenes ya construidas, el arranque inicial tardó 23,936 s y el
reinicio 21,627 s. En la muestra, una predicción tardó 0,071 s y un lote
de dos citas 0,056 s. La RAM se tomó en un instante después de inferir.
Estas mediciones establecen una referencia local y no son un presupuesto
de rendimiento ni una prueba de carga.

[Evidencia del laboratorio](e2e-20261108-01.json).

## Smoke autenticado y recorrido en navegador

El laboratorio publicó únicamente backend y frontend en loopback. La
primera prueba desde Windows falló con ambas redes internas. Se añadió
una red de acceso local solo para esos servicios. PostgreSQL e IA
continuaron sin puertos publicados.

Se comprobó la pantalla Usuarios como Administrador, Importar CSV como
Recepción y Modelo IA como Técnico IA. Recepción no vio el enlace a
Usuarios y Técnico IA no vio el enlace a Importar CSV. No se ejecutó
una importación desde el navegador en este ensayo.

El primer smoke autenticado pasó para Administrador y Recepción y
devolvió 401 al consultar identidad como Técnico IA durante las
pruebas paralelas de sesión. La repetición secuencial pasó para los
tres roles, incluida la inferencia sintética. Se detuvo el laboratorio.
Los servicios operativos conservaron sus IDs y horas de inicio.

[Evidencia de navegador y smoke](smoke-navegador-20261108.json).

## Presupuesto inicial propuesto

Con imágenes locales y en la misma máquina, se proponen hasta 45 s
para el arranque inicial, 40 s para el reinicio, 1 s por predicción
individual y 15 s para un lote de 500 sin contención. Se propone
1,5 GiB de RAM para la suma de los cuatro servicios persistentes.
Son criterios para discusión. Antes de hacerlos obligatorios, repetir
con muestras frías y calientes y registrar percentiles, pico de RAM,
carga y configuración del equipo.

## Cierre y presupuesto validado (08/11/2026)

Se importaron desde el navegador 500 citas sintéticas con cero rechazos.
Pasaron las tres mediciones de cada operación bajo el presupuesto acordado:
arranque nuevo 25,822 s máximo (45 s), reinicio 21,576 s (40 s), inferencia
individual 0,067 s (1 s) y lote de 500 con persistencia 6,844 s (15 s).
La suma máxima de picos cgroup de los cuatro servicios persistentes fue
860,883 MiB (1,5 GiB). Es una cota conservadora porque los picos por servicio
pueden ocurrir en instantes distintos. Se midió desde el último arranque
nuevo con la importación y la inferencia, y tras cada reinicio. Las imágenes
ya estaban construidas. Los reinicios conservaron las 500 citas y sus
predicciones. Se detuvo el laboratorio y el stack operativo permaneció intacto.

El primer comando de medición tuvo un error de sintaxis de unidad en
PowerShell y se corrigió antes de ejecutar las mediciones.

Se mantienen diferidos los 56 fallos históricos de Citas, la revisión
del botón de lote y el error reportado en la asignación de cupo en la
interfaz. Las carreras del backend no resuelven esa incidencia de interfaz.
El ensayo de rendimiento es local y sin contención. La revisión de secretos
fue acotada y no se configuró CI porque no se acordó proveedor.

[Evidencia del presupuesto y CSV](rendimiento-20261108-01.json).
