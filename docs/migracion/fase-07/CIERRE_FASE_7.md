# Cierre de la fase 7 — 08/11/2026

Se aplicó el retiro en el Compose oficial sobre `predicitas-crp_pgdata`.
PostgreSQL conservó la revisión `m01_001_indices_auditoria`. Antes del
arranque se generó un respaldo privado y se verificó por lectura completa
del archivo con pg_restore y comparación SHA-256 tras copiarlo. Se
construyó la imagen de retorno de `b7180a2` con el modelo aprobado.

Backend y frontend respondieron 200. IA quedó sana en la red interna, sin
publicar su puerto. Se comprobó la lectura con el rol `predicitas_app`.
Desde el contenedor del backend se obtuvo una predicción sintética de
`LightGBM_v1.0.0`, y se consultaron métricas y dataset. El smoke
operativo no persistió predicciones ni sembró datos. Las rutas
autenticadas y la persistencia se verificaron en la regresión aislada.

Docker agotó el pool de asignación automática durante el primer intento,
antes de arrancar PostgreSQL. Se completó el arranque con dos subredes
explícitas mediante una capa local. El respaldo y esa capa se conservaron
en `%LOCALAPPDATA%/Temp/opencode/predicitas-fase7-cierre-20261108-01`.
Para gestionar el stack en esta máquina usar los mismos archivos:

```powershell
$redLocal = Join-Path $env:LOCALAPPDATA 'Temp/opencode/predicitas-fase7-cierre-20261108-01/red-local.yaml'
docker compose --env-file .env -f compose.yaml -f $redLocal ps -a
```

El retorno ensayado en laboratorio usa la imagen integrada sobre el mismo
volumen. La referencia para volver es `b7180a2` y la imagen local
`predicitas-retorno-fase7:b7180a2`. El respaldo queda como contingencia.
El empaquetado independiente de dependencias de pruebas queda como
tarea de empaquetado posterior. Las instalaciones se reprodujeron con
las versiones fijadas y la imagen del backend está libre de ML.

[Evidencia del arranque operativo](evidencia/cierre-20261108-01/resumen.json) ·
[Integración y pruebas](BLOQUE_7G.md) ·
[Retorno en laboratorio](evidencia/retiro-20261108-01/resumen.json).
