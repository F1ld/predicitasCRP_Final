# Fase 7 — trazabilidad y revisión de compatibilidad

## Trazabilidad validada (08/11/2026)

El backend genera un UUID opaco por petición y lo devuelve como
`X-Request-ID`, expuesto por CORS. El adaptador HTTP lo propaga a IA como
cabecera independiente del identificador de cada fragmento. IA registra el
identificador válido y la duración de la operación. Las trazas contienen
el identificador y el tiempo, sin incluir el cuerpo ni las credenciales.

La primera ejecución pasó las pruebas focales y la regresión. Se detectó
durante la revisión que los loggers iniciales no emitían INFO con la
configuración por defecto de Uvicorn. Se corrigió el logger y se incorporó
una comprobación de emisión al runner. La segunda ejecución, con imágenes
nuevas de backend e IA, registró 5 IDs distintos.
Pasaron 19 pruebas del puerto, 15 focales y 354 de regresión empaquetada.
Las rutas IA y alias Citas propagaron el ID observado por el consumidor
hasta el cliente HTTP interno, sin reenviar Authorization. Pasaron los
controles de concurrencia y rollback. El runner verificó los archivos
protegidos, detuvo los contenedores del laboratorio y preservó el conjunto
de contenedores operativos.

La colección completa conserva dos errores históricos en `tests/ia`
(import del cliente retirado) y el verificador de evidencia de fase 3
(rutas de repositorio en la imagen empaquetada).

[Resumen de la ejecución](evidencia/7c-20261108-02/resumen.json).

## Revisión de errores públicos

El detalle de Citas traduce `MOTOR_IA_NO_DISPONIBLE` y tiene regresión para
503. Se conserva ese contrato para timeout, respuesta incompatible y
servicio indisponible. El conflicto por cambio de versión mantiene 409.
La separación en 502/504 sigue pendiente de acordar y validar con los
consumidores de Citas y del lote.

## Condiciones pendientes del corte

El Compose actual todavía arranca con inferencia integrada y no incluye
un servicio IA. El corte requiere un arranque verificable con IA separada,
paridad ampliada de los consumidores, medición del lote público y prueba
de retorno. Conservar el motor integrado hasta validar ese camino evita
que un arranque habitual pierda inferencia.
