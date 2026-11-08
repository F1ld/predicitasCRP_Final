# Fase 7 — límite público y paridad

## Límite del lote

La consulta trae como máximo 501 citas elegibles. Con más de 500, la API
devuelve 422 `LOTE_IA_DEMASIADO_GRANDE` antes de construir o enviar los
fragmentos. La consulta a la versión del modelo se conserva porque determina
la elegibilidad sin `forzar`. La ejecución 02 midió 5,105–5,707 s para tres
lotes secuenciales de 500. El rechazo de 501 dejó las 500 predicciones previas
y no llamó al endpoint de inferencia. La ejecución 01 falló al crear la red
de Docker y se repitió con una subred explícita. No se midió latencia bajo
carga concurrente.

[Evidencia del límite](evidencia/7e-20261108-02/resumen.json).

## Paridad y atomicidad

Los dos motores recorren las mismas rutas públicas sobre transacciones de
laboratorio separadas y revertidas al terminar. Se comparan predicción
individual, alias Citas, lote con y sin `forzar`, métricas, dataset,
persistencia y auditoría. Se excluyen identificadores generados y timestamps.
El primer intento detectó diferencias de representación en el lote. La
comparación usa Decimal para puntuaciones y umbrales, con lo que verifica
igualdad numérica sin exigir igualdad textual del JSON. El fallo inyectado
en el segundo fragmento dejó cero predicciones y cero eventos adicionales.

Las dos incidencias históricas de colección siguen pendientes. La evidencia
no certifica paridad de todos los consumidores ni el retiro del motor legacy.

La ejecución 04 aprobó 17 pruebas focales, 356 de regresión empaquetada y
los controles independientes de concurrencia y rollback. Las dos pruebas
especiales de arranque y medición se ejecutan por separado.

[Evidencia de paridad](evidencia/7e-20261108-04/resumen.json).
