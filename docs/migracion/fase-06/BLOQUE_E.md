# Fase 6 — bloque E: camino limpio integrado (COMPLETADO)

**Estado vigente: BLOQUE E COMPLETADO. FASE 6 CERRADA.** La ejecución
`e-20261107-01` (07/11/2026) recorrió en aislamiento el camino limpio completo:
paquete de fuentes sin artefactos → imágenes limpias → generar → validar →
entrenar dos veces → promover → rollback → servir con release/hash explícitos →
sembrar 1080 filas → repetir seed → backend real con health/login/citas/usuarios/
catálogos/reportes. No se conectó el backend con IA ni se inició fase 7.

Este bloque **no** sustituye al predictor integrado, no toca la BD principal, el
compose, el modelo activo ni los archivos privados. Los recursos del laboratorio
propio quedaron detenidos y preservados para diagnóstico. No hay commit
automático. El retiro físico de D sigue prohibido; solo quedan las dos
excepciones aprobadas (predictor y reexport) hasta fase 7.

## Qué se implementó

- `soporte_e.py`: índice reproducible de `apps/backend`, `apps/ia` y `contracts`;
  paquete ZIP, reconstrucción y hashes. Excluye artefactos, `.joblib`, entornos,
  cachés, `runtime`, respaldos y secretos. La exclusión de `data` se limita a
  `apps/backend/data` y `apps/ia/data`: **`contracts/data` se conserva** porque
  contiene los esquemas v1 usados por pipeline y serving.
- `servidor_guardado_e.py`: arranque HTTP/worker con guardas que prohíben
  importar procesos offline (`training`, `management`, `datasets`) y ejecutar
  `Pipeline.fit`/`joblib.dump` desde serving.
- `probar_pipeline_e.py`: CLI real de generar/validar/entrenar, dos candidatos,
  comparación de métricas/predicciones, promoción, corrupción y rollback.
- `probar_serving_e.py`: HTTP TCP real, worker aislado, validación contra
  contratos, registry montado RO y escenario sin modelo (`--no-listo`).
- `probar_seed_e.py`: seed desde el `seed.csv` del pipeline, conteos con conexión
  independiente y repetición idempotente.
- `probar_backend_e.py`: smoke del backend limpio con uvicorn real, sin IA ni
  modelo empaquetado.
- `validar_bloque_e.py`: orquestador completo, laboratorio PostgreSQL nuevo,
  evidencias, gate D y comprobaciones de archivos protegidos/contenedores.

## Paquete limpio e imágenes

- **243 archivos** empaquetados; reconstrucción byte a byte igual al índice.
- Sin `.joblib`, sin `artifacts/`, sin `.env`/secretos, sin `runtime`.
- `contracts/data/*.json` incluido; `apps/backend/data/*.csv` excluido.
- Imagen IA: `sha256:6d1ee8581301819845e0d324fe3864fc2f48cb1fe35b68529fddd8e2e29a2853`,
  construida desde el árbol limpio con `--build-context contracts=<limpio>/contracts`.
  No incluye SQLAlchemy (verificado en ejecución).
- Imagen backend: `sha256:5e797c24b24b0f4056eb4cbf79184225eaebf14db7c2078e9ad28d0b288eba54`,
  construida desde el árbol limpio. **No contiene ningún `.joblib`** (verificado).
- Etiquetas locales: `predicitas-ia:e-e-20261107-01` y
  `predicitas-backend:e-e-20261107-01`. Las evidencias usan el ID, no la etiqueta.

## Laboratorio

- PostgreSQL 16 nuevo `predicitas-f6e-e-20261107-01-db`, red interna
  `predicitas-f6e-e-20261107-01-net` y volumen
  `predicitas-f6e-e-20261107-01-pgdata`, todos con etiqueta
  `predicitas.purpose=f6e-test`.
- Base `predicitas_f6e_test`; rol `predicitas_app` y contraseñas aleatorias en
  un directorio privado temporal, nunca en la evidencia pública.
- Migraciones `alembic upgrade head` con rol dueño; seed y backend con rol app.
- El contenedor quedó detenido; red y volumen se preservan. No se tocó la BD
  principal ni se levantó el stack operativo.
- Serving y seed son independientes y consumen salidas del mismo pipeline. El
  runner ejecuta pipeline → serving → seed → backend en un único laboratorio;
  la secuencia lógica generar → validar → entrenar → promover → sembrar → servir
  queda cubierta por esas etapas, sin afirmar que el seed alimente al serving.

## Resultados del recorrido

### Pipeline (sin BD, sin modelo legacy, sin escribir el registry de serving)

- Dataset `e-dataset`: manifiesto
  `0d73d775bdad7a31a9ff0dc3f78baaac9c546d0704790e00ed298c85d0476bc5`;
  1000 históricas, split 700/150/150; `seed.csv` de **1080 filas** con SHA-256
  `389e0276a837e6e9ad333463fa2759764f09aeea07419feeb428ef71fba26626`.
- Dos entrenamientos (`e-model-a`, `e-model-b`): **métricas y predicciones
  iguales**; los bytes del artefacto Joblib difieren, como estaba previsto y
  aceptado. No se declara equivalencia binaria entre Joblib distintos.
- Promoción A → B, rechazo de candidato corrupto sin alterar el estado y
  rollback B → A → B correctos. Activo final `e-model-b`; aprobación
  `a9c449ad77eeb33ff759e53d56385a977856e59c5c9477129bb9166ba3ee2c69`.
- Release final con `model.joblib`, `approval.json`, `manifest.json`,
  `candidate-manifest.json`, `dataset-manifest.json` y `metrics.json`.

### Serving

- Con `IA_RELEASE_VERSION=e-model-b` + `IA_APPROVAL_SHA256` y registry RO:
  `/health/ready` 200, 3 casos individuales y lote de **60**, contratos
  validados, digest de predicciones
  `57f3a780dad79a0ea0135b7853c2fe5238754e2a5d59d275b4b9a316120f3098`.
- Registry sin cambios; sin DSN/BD; sin Joblib legacy en la imagen; sin
  entrenamiento ni escritura ML desde serving.
- Sin modelo/release (`--no-listo`): `/health/ready` 503 y predicción 503 con
  error de contrato. El worker guardado también se validó en este escenario.

### Seed

- Primera carga: 1080 recibidas, 1080 insertadas, 3 usuarios, 2080 historiales
  y 4 eventos de auditoría; rol `predicitas_app`.
- Repetición: 1080 existentes, **0 insertadas, 0 usuarios**, sin cambios en
  ninguna tabla. La contraseña no aparece en la salida.

### Backend limpio

- uvicorn real + HTTP TCP; `/health` OK; login `admin@predicitas.crp`.
- `/citas?limite=1` total **1080**; `/usuarios?limite=1` total **3**.
- `/citas/catalogos` con los seis catálogos; `/reportes/rep-02` y
  `/reportes/rep-03` responden 200.
- Sin IA configurada y sin modelo empaquetado. **El backend sigue sin consumir
  la IA por HTTP**; esa conexión es fase 7.

### Gate D y protección del entorno

- Inventario D válido: **2 referencias aprobadas**, cierre programado código 0,
  retiro físico no permitido (código 2).
- Archivos protegidos (`.env`, modelos legacy) con hashes idénticos antes/después.
  El modelo legacy conserva
  `89297942f603dc040c9954d534ae6dae97590203f0345925c12fc4e0a90e9074`.
- El conjunto de contenedores en ejecución no cambió (vacío antes y después).
- Fuentes de E, pipeline, releases y seed con hashes registrados.

## Errores y límites

- **Ajuste de la sonda de serving, no del contrato:** `multipleOf: 0.001` falla
  con `0.285` por representación binaria (`0.285/0.001` no es exactamente
  entero). La sonda compara con tolerancia de coma flotante y quita `$schema`
  de los recursos cargados para que `evolve` no reconstruya un validador
  estándar. Los contratos y la aplicación no se modificaron.
- **Corrección del paquete limpio:** la primera versión de `soporte_e.py`
  excluía cualquier directorio llamado `data`, lo que habría dejado fuera
  `contracts/data`. Se corrigió antes de ejecutar E; la reconstrucción final
  incluye los esquemas y conserva la exclusión de datos de aplicación.
- La imagen backend limpia no puede ejecutar las pruebas que dependen del
  modelo IA empaquetado. La suite backend completa sigue cubierta por D con el
  artefacto; **no se declara una suite completa verde** en E.
- No se ejecutó navegador ni validación visual; no se desplegó Compose; no se
  validó en un clon limpio ni se publicó un paquete portable completo.
- Los recursos del laboratorio se preservan detenidos; no se eliminan para no
  destruir evidencia. El retorno consiste en retirar solo las herramientas y
  documentación de E, sin restaurar BD ni borrar volúmenes.

## Reproducción

```powershell
# Desde la raíz. Elegir un run-id NUEVO; no reutilizar uno existente.
python -B docs/migracion/fase-06/validar_bloque_e.py --run-id e-20261107-01
```

El comando crea un paquete limpio, construye dos imágenes desde el árbol
reconstruido, crea un PostgreSQL nuevo, ejecuta el pipeline, serving, seed y
backend, y escribe la evidencia en
`runtime/test-results/fase-06/<run-id>/`. No toca el stack principal.

[Resumen y hashes](evidencia/e-20261107-01/resumen.json) ·
[Pipeline](evidencia/e-20261107-01/pipeline-e.json) ·
[Serving](evidencia/e-20261107-01/serving-e.json) ·
[Serving sin modelo](evidencia/e-20261107-01/serving-e-sin-modelo.json) ·
[Seed](evidencia/e-20261107-01/seed-e.json) ·
[Backend](evidencia/e-20261107-01/backend-e.json)

## Cierre de fase 6

Con E validado, la fase 6 queda **COMPLETADA** en su alcance documentado:
pipeline explícito, promoción/rollback, seed explícito, migraciones D y camino
limpio integrado en aislamiento. El predictor integrado y su reexport siguen
siendo la ruta operativa del backend hasta fase 7. **Fase 7 permanece
PENDIENTE** y no se inicia por esta entrega.
