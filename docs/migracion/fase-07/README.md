# Fase 7 — conexión backend/IA (EN CURSO)

**Actualización 7B:** cableado conservador de servicios/alias/metadata al puerto,
lifespan y protección transaccional. El integrado permanece por defecto; HTTP
solo opt-in, sin despliegue. [Alcance y validación 7B](BLOQUE_7B.md).
La sección 7A siguiente describe su entrega histórica anterior al cableado.

## 7A — puerto y adaptadores de inferencia

Base de retorno: `3700c5f` (fase 6 comprometida con autorización del usuario).
Implementación del 07/11/2026; **sin commit automático de 7A**.

### Alcance implementado

- `apps/backend/app/modules/ia/puerto.py`: `MotorPredictivo`, features pre-cita
  estrictas y resultado tipado; sin BD, HTTP ni librerías ML. El backend deriva
  el snapshot y verifica que la respuesta corresponda a sus datos.
- `motor_integrado.py`: adaptador temporal con imports diferidos. No retira ni
  modifica el predictor legacy (incluido su comportamiento histórico).
- `motor_http.py`: cliente `httpx` propio, `close()` y context manager. URL y
  clave internas explícitas; sin JWT, cookies, cabeceras del usuario, proxies
  del entorno, redirecciones ni reintentos automáticos.
- Timeouts separados connect/read/write/pool: 2/15/5/2 segundos por defecto.
  Presupuesto de lote de 60 s, comprobado entre operaciones y al leer bloques;
  **no es un cancelador duro de cómputo remoto**. IA conserva su propio plazo.
- `/v1/model`, `/v1/predict` y `/v1/predict-batch`; fragmentos de hasta 100.
  La versión se fija explícitamente durante todo el lote. Correlación por UUID
  e id de ítem, rechazo de duplicados/faltantes/extras y reordenación segura.
- Respuesta JSON limitada a 2 MiB; validación de contrato, features, snapshot,
  rango/precisión del score, clasificación, umbrales y rotulado sintético.
  Se conserva la explicación validada para la futura persistencia en backend.
- Caída, timeout, clave interna inválida, modelo ausente o respuesta inválida:
  `MotorIANoDisponible` (503), sin filtrar detalles remotos. Cambio de versión:
  `Conflicto` con `VERSION_MODELO_INCOMPATIBLE` (409). No devuelve lote parcial.

### Ruta operativa y límites deliberados

**No se conecta todavía el adaptador a los routers ni a `ia/service.py`.**
El predictor integrado sigue siendo la ruta operativa por defecto y el camino
de retorno. No se activa fallback automático durante una operación HTTP: cambiar
de motor/versión silenciosamente podría mezclar resultados dentro de un lote.

El lifecycle probado es el del cliente/context manager; su creación/cierre en
el lifespan FastAPI y la selección por configuración corresponden al cableado
siguiente. No se modificaron API pública, esquema, persistencia, auditoría,
roles, endpoints, dependencias ML, Compose, modelos ni datos operativos.

Falta completar en el siguiente bloque: puerto para métricas/dataset-resumen,
inyección en servicios y alias Citas, lifecycle de aplicación y pruebas de
transacción/auditoría con dobles del puerto en PostgreSQL **nuevo y aislado**.
No retirar el predictor/generador hasta paridad y regresión de todos sus
consumidores. El gate D sigue con dos excepciones y retiro físico bloqueado.

### Validación

Ejecución final: `7a-20261107-05`.

```powershell
python -B docs/migracion/fase-07/test_motor_7a.py
python -B docs/migracion/fase-07/validar_7a.py --nombre <nombre-nuevo>
python -B docs/migracion/fase-06/inventariar_legacy_d.py --exigir-cierre-programado
```

- **19/19 pruebas unitarias**, con subcasos de límites y fallos, en host y/o
  imagen empaquetada. Sin fixtures/conftest de BD. Incluyen doble del puerto,
  cambio de versión en segundo fragmento y respuesta malformada.
- HTTP TCP y uvicorn reales: una predicción y **105 en lote (100+5)** iguales
  al adaptador integrado usando el modelo legacy aprobado. Son muestras de
  paridad de inferencia, **no paridad integral de fase 7**.
- IA caída, clave incorrecta, modelo ausente, versión incompatible, timeout de
  lectura TCP y respuesta malformada TCP. Cambio a mitad de lote simulado con
  transporte controlado, no promoción real durante una petición.
- Contenedores `--network none`, rootfs RO, fuentes/modelos RO, 2 CPU/1 GiB;
  sin PostgreSQL. El import legacy exige configuración backend: URL inalcanzable
  de laboratorio y guarda de `Engine.connect` que falla ante cualquier conexión.
- Reutiliza imagen backend de E por ID con fuentes montadas RO; **no es un
  build limpio nuevo ni una prueba del despliegue Compose**. Sin suite completa
  de regresión, cobertura global ni validación visual. S-02 y el verificador
  histórico de fase 3 no se consideran resueltos por esta entrega.
- Modelo conserva SHA-256 `89297942f603dc040c9954d534ae6dae97590203f0345925c12fc4e0a90e9074`.
  Archivos protegidos y conjunto de contenedores activos sin cambios.
  Los contenedores propios quedan detenidos, sin borrar evidencia ni volúmenes.

**Incidencias del harness, no ocultadas:** primer intento con hilos nativos sin
acotar obtuvo 503 en el lote; segundo intento ya acotado llegó a la comparación
legacy y falló por Settings obligatorios sin configurar. Se corrigió solo el
harness (1 hilo nativo y configuración inalcanzable + guarda BD); los intentos
03 y posteriores pasaron. Evidencia exploratoria privada en `runtime/fase-07/`.

[Resumen portátil de validación](evidencia/7a-20261107-05/resumen.json).
El detalle y logs del laboratorio quedan en `runtime/fase-07/7a-20261107-05/`.

**Estado:** base 7A de inferencia validada; fase 7 EN CURSO. Siguiente paso:
cableado controlado del puerto, metadata y pruebas transaccionales, manteniendo
el integrado por defecto hasta autorización y paridad suficientes.
