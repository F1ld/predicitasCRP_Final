# Arranque y recuperación con IA separada

La ejecución `7d-20261108-01` probó FastAPI con su lifecycle real dentro
de una imagen nueva, PostgreSQL aislado y un servicio IA real por TCP.
Sin IA, salud devolvió 200 y la predicción 503 con código
`MOTOR_IA_NO_DISPONIBLE`. La misma instancia recuperó la inferencia al
arrancar IA y una nueva instancia con configuración integrada predijo por
el alias Citas. La prueba usó TestClient y no certifica el arranque de Compose.

Pasaron 15 pruebas focales y 354 de regresión empaquetada. La prueba de
arranque se ejecutó por separado y figura omitida en esas dos selecciones.
Los controles de concurrencia y rollback también pasaron. La colección
completa conserva los dos errores históricos de IA legacy y fase 3.
Los archivos protegidos y el conjunto activo de contenedores conservaron
su estado. Se detuvieron los contenedores del laboratorio.

[Evidencia del arranque](evidencia/7d-20261108-01/resumen.json).

## Medicion del lote publico

La ejecucion 03 midio 100 citas en 1,223 s, 250 en 2,636 s y 500 en 5,416 s.
Incluye HTTP a IA y persistencia PostgreSQL. Cada ensayo verifico 200,
el total evaluado y el conteo persistido. Son muestras de laboratorio
con datos sinteticos, una por tamano. No se aplica un limite publico nuevo.

La ejecucion 02 fallo al crear el rol de laboratorio antes de las
migraciones. El runner comprobaba disponibilidad mediante el socket
local, que tambien puede responder durante el arranque temporal de
PostgreSQL. Se cambio la comprobacion a TCP y el intento 03 paso.

[Evidencia del lote](evidencia/7d-20261108-03/resumen.json).

## Validación de Compose

El proyecto aislado 02 aplicó migraciones sobre un volumen nuevo y levantó
el backend con IA apagada. Por HTTP real, salud devolvió 200 y el lote 503.
Al levantar IA, el mismo contenedor backend devolvió 200 para el lote.
Después se detuvo IA, se recreó el backend con modo integrado y se repitió
el lote con 200 sobre la misma base del laboratorio.

El intento 01 falló al asignar una red porque Docker agotó sus rangos
automáticos. El intento 02 utilizó una subred privada explícita. Se
detuvieron los contenedores del laboratorio y se comprobó el hash del
Compose operativo y el conjunto activo de contenedores.

[Compose de laboratorio](compose.laboratorio.yaml) y
[evidencia](evidencia/compose-20261108-02/resumen.json).

La validación cubre el arranque, la recuperación y el retorno de backend.
Quedan el límite público, la paridad ampliada y la prueba del backend
sin dependencias ML antes del retiro.
