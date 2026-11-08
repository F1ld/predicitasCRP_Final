# Fase 7 — carga, colección y candidato de retiro

## Carga concurrente

Dos lotes simultáneos de 500 citas en Compose aislado dieron 200 en 8,056 s
y 503 en 0,067 s. Una conexión independiente observó 500 predicciones y
un evento de inferencia. Un lote posterior pasó en 7,480 s. Es una prueba
del comportamiento ante saturación del ejecutor, con una pareja de cargas.

[Evidencia de carga](evidencia/compose-20261108-03/resumen.json).

## Colección y regresión

Las pruebas del cliente anterior a v1 se archivaron completas fuera de la
colección activa. Importaban un módulo retirado y exigían, entre otras cosas,
éxito parcial de un lote. La cobertura vigente se enlaza en el archivo
histórico. El verificador de fase 3 resuelve su árbol en la fixture.
La imagen empaquetada coleccionó 401 pruebas sin errores. La suite en
estructura de repositorio, con insumos de solo lectura y sin exclusiones,
aprobó 399 y omitió dos ensayos de laboratorio que se ejecutan por separado.
Pasaron los controles independientes de concurrencia y rollback.

[Evidencia de colección y regresión](evidencia/7f-20261108-01/resumen.json).

## Candidato de retiro y retorno

Se construyó una copia en runtime mediante `preparar_retiro.py`, con
motor HTTP obligatorio y sin predictor, generador duplicado, modelos Joblib,
dependencias ML ni libgomp. Se verificó la ausencia en la imagen arrancada.
El backend sano devolvió 503 con IA apagada y 200 al iniciar IA, conservando
la instancia. La reversión usó la imagen anterior por ID con el mismo
PostgreSQL. Conservó la revisión de Alembic, los recuentos y el hash de
OpenAPI. Migraciones utilizó la imagen de referencia. El ensayo de la imagen
candidata fue HTTP focal, y la suite completa se ejecutó sobre el código
base con ambos motores.

El proyecto aislado se detuvo y se verificaron el Compose operativo y
el conjunto de contenedores activos. Sigue pendiente integrar el retiro
definitivo y validar el arranque oficial con IA separada.

[Evidencia del retiro y retorno](evidencia/retiro-20261108-01/resumen.json).
