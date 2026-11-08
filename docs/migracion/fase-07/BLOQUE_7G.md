# Integración del retiro y arranque oficial

El backend requiere el puerto HTTP para inferencia. Se retiraron el
predictor integrado, el generador duplicado, su reexport y las dependencias
ML. El artefacto local anterior se excluye de la imagen. IA carga el modelo
aprobado en un montaje de solo lectura y comparte con el backend una red
interna. El Compose requiere definir `IA_API_KEY` en el entorno privado.
El volumen de PostgreSQL sigue siendo externo y el seed, manual.

## Verificación del 08/11/2026

Se ejecutó el Compose oficial con una capa de aislamiento que cambió
identidades, subredes y nombre de base y eliminó la publicación de puertos.
Las migraciones pasaron y el frontend respondió 200 por HTTP. El backend
arrancó con IA detenida, devolvió 503 para el lote y recuperó la inferencia
en el mismo contenedor al arrancar IA. Se verificó la ausencia de módulos
legacy, artefactos Joblib y librerías Python de ML en la imagen.

La ejecución 7g-20261108-01 coleccionó 398 pruebas sin errores y aprobó
396 en la suite de repositorio. Las dos omitidas corresponden a ensayos
especiales. El arranque se ejecutó por separado en esta misma corrida y el
lote se midió en los bloques anteriores. También pasaron 16 focales,
19 del adaptador, cinco de metadata, 19 autopruebas del inventario y los
controles de concurrencia y rollback. El primer intento de autopruebas
del inventario falló por permisos del directorio temporal en Windows;
pasó al usar una carpeta de runtime del laboratorio.

El inventario de retiro conserva el hash del generador canónico de IA y
confirma ausencia de productor y referencias legacy en el backend.

## Retorno

Punto de retorno `b7180a2` y la imagen integrada previa. El candidato
anterior demostró el retorno por ID de imagen sobre el mismo volumen,
con la misma revisión Alembic y los mismos recuentos. Esta integración
no añade migraciones. El entorno operativo permanece con sus contenedores
previos y el `.env` privado conserva su contenido. La comprobación de
frontend cubre la respuesta HTTP del servidor de desarrollo.

[Evidencia de Compose](evidencia/oficial-20261108-01/resumen.json) ·
[Evidencia de regresión](evidencia/7g-20261108-01/resumen.json) ·
[Ensayo previo de retorno](evidencia/retiro-20261108-01/resumen.json).

## Configuración de la clave interna

Se configuró una clave aleatoria en el entorno privado. Compose resolvió la
misma clave para backend e IA, y el frontend carece de esa variable. El
laboratorio usó su propia clave efímera. La clave correcta permitió
predecir y la incorrecta devolvió 401 en IA y 503 en el backend, sin
escribir predicciones ni eventos. Pasaron 17 focales y 397 pruebas de
regresión. Los contenedores operativos conservaron su estado.

[Evidencia de autenticación](evidencia/7g-clave-20261108-01/resumen.json).
