# Fase 5 — bloque C: plazo duro y concurrencia de cómputo

Autorizado por el usuario. Baseline C `96d809d`, árbol limpio antes de implementar.
No se cambia el contrato HTTP, las fórmulas, los umbrales, las explicaciones, el
modelo aprobado, los datasets, el entrenamiento, el Dockerfile, las dependencias,
el backend, el frontend ni las credenciales. No se inicia fase 6/7 ni se conecta
el consumidor IA.

## Diseño

- Un **único worker persistente** en proceso separado atiende inferencias de a una.
  Carga el modelo una vez y no crea un proceso por solicitud. Vive en
  `apps/ia/app/execution.py` y `apps/ia/app/inference_worker.py`.
- El worker privado no abre HTTP, BD ni entrenamiento, no escribe artefactos y
  solo implementa el protocolo de una línea JSON por solicitud y una por respuesta.
  Una solicitud inválida responde `status=error`; el padre descarta el worker y
  **no publica resultados parciales**.
- **Cupo único sin cola ni retry:** si ya hay una inferencia en curso, la segunda
  se rechaza de inmediato. No se acumulan solicitudes ni se duplica la memoria del
  modelo.
- **Plazo total duro de 10 s** (`IA_COMPUTE_TIMEOUT_SECONDS`), medido desde la
  escritura de la solicitud hasta la respuesta completa. Incluye carga/validación
  ya realizada por el worker, cómputo, explicabilidad TreeSHAP y serialización.
  Al vencer se mata y recoge el hijo **antes** de liberar el cupo; la siguiente
  solicitud arranca un worker nuevo. No queda un hilo abandonado calculando.
- Un worker que no arranca, muere, tarda, devuelve una respuesta incompleta o
  incompatible se descarta. No se reintenta la misma solicitud ni se reutiliza
  estado contaminado.
- El entorno del hijo se filtra a `PATH`, `SYSTEMROOT`, `WINDIR`, `TEMP`, `TMP`,
  `HOME`, `LANG`, `LC_ALL`, `PYTHONPATH`, `MODEL_REGISTRY_DIR` y `MODEL_FILENAME`.
  No se transmiten `IA_API_KEY`, DSN ni secretos del proceso HTTP. Los hilos
  nativos quedan en uno (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
  `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`).
- El `lifespan` arranca y valida el worker solo si el modelo confiable cargó. Un
  fallo de aislamiento cierra el ejecutor y falla el arranque de forma segura.
- Los fallos conservan el contrato 503 existente (`MODELO_NO_DISPONIBLE`) y añaden
  `campos.motivo` con `PLAZO_AGOTADO`, `WORKER_FALLIDO` o `CAPACIDAD_OCUPADA`.
- No cambian probabilidades, redondeo a tres decimales, umbrales, niveles,
  `features_snapshot`, explicaciones, metadata ni la versión del modelo.

## Gates congelados antes de la ejecución formal

1. Regresión IA completa aprobada, cobertura medida ≥80 % y autopruebas del runner.
2. Paridad de inferencia con los 207 casos congelados/deterministas, todos los
   campos y los tres niveles de riesgo.
3. Plazo duro comprobado: el cómputo que no responde se interrumpe, se recoge el
   proceso y se libera el cupo; la interrupción debe medirse por debajo de 5 s.
4. Concurrencia real: con dos solicitudes simultáneas, una termina 200 y la otra
   recibe 503 `CAPACIDAD_OCUPADA` sin encolarse; una solicitud posterior se recupera.
5. Memoria del servidor más worker bajo 1 GiB, medida desde procfs/cgroup durante
   el lote máximo de 100 elementos.
6. Aislamiento: UID 1000, red `none`, filesystem y modelo RO, sin montar fuentes
   del backend ni DSN; un solo worker.
7. Entrenamiento, datasets, manifiestos, Dockerfile, dependencias, backend,
   frontend, contratos y modelo sin cambios respecto del baseline C `96d809d`.
8. Implementación registrada antes de validar, imagen inmutable por ID, evidencia
   sanitizada separada, hashes del paquete comprobados desde clon limpio.

## Ejecución formal aceptada

```powershell
python -B docs/migracion/fase-05/validar_ia.py ejecutar --scope C --run-id ia-bloque-c-20261107-02
python -B docs/migracion/fase-05/validar_ia.py publicar --scope C --run-id ia-bloque-c-20261107-02
python -B docs/migracion/fase-05/validar_ia.py verificar --scope C --run-id ia-bloque-c-20261107-02
```

**Bloque C VALIDADO**, ejecución `ia-bloque-c-20261107-02` del 07/11/2026.
Implementación `4d00f07`; pruebas y ramas límite `3294380`; evidencia separada
`bc1af92`. Commit probado `3294380e0ff10421058c165179fa22fcdfa281e8`.

| Gate | Resultado de la ejecución archivada |
|---|---|
| Regresión IA | **184/184 pruebas**: 135 previas + 49 de ejecución/worker; tres autopruebas del runner |
| Cobertura conjunta | **94,37340153452685 %**; `inference_worker.py` **97,87 %** y `execution.py` **92,41 %** |
| Paridad | **207 casos**, todos los campos idénticos; presentes BAJO, MEDIO y ALTO |
| Plazo duro | Interrupción y recogida en **0,30240533300002426 s** (<5 s); cupo liberado y worker reiniciado |
| Concurrencia | 2 simultáneas: **1×200 + 1×503 `CAPACIDAD_OCUPADA`**; recuperación posterior **200** |
| Lote máximo | 100 elementos en **0,9287412510000195 s**, dentro del presupuesto de 10 s |
| Memoria | Pico **303 251 456 bytes** (~289 MiB) bajo **1 073 741 824 bytes**; método `procfs-vmrss+cgroup` |
| Aislamiento | UID 1000, red `none`, RO, sin DSN ni fuentes backend; un worker persistente |
| Protegidos | Backend/frontend/contratos, entrenamiento, datasets, manifiestos, Dockerfile y dependencias iguales a `96d809d` |

Imagen ejecutada por ID:
`sha256:b1a1f3b30300ff2537f5ea689e1cf3e3d3e4c822c9ffbf2d3743abc1b438140c`.

El intento `ia-bloque-c-20261107-01` se conserva sin sobrescribir: aprobó 157
pruebas y 86,96 % de cobertura, pero se sustituyó por el run 02 al añadir pruebas
directas del worker que hacen visible su cobertura. No se publicó como evidencia
aceptada.

## Verificación y límites

- El paquete `ia-bloque-c-20261107-02` verifica íntegro desde un clon limpio de
  Windows. Los 71 hashes de fuentes se reproducen byte a byte en un clon que
  preserva LF salvo cuatro archivos cuyo fin de línea cambia por atributos del
  repositorio; normalizados CRLF/LF, **71/71 coinciden**. Con `autocrlf=true` el
  árbol completo se convierte a CRLF, igual que en las evidencias A/B ya aceptadas;
  eso afecta solo a los hashes del árbol de trabajo, no al contenido ni al paquete.
- La prueba de concurrencia es de **dos solicitudes simultáneas**, no una prueba de
  carga sostenida. El límite de 16 conexiones y un worker se conserva; no se
  certifica latencia bajo saturación prolongada.
- La memoria se midió durante el lote máximo en el contenedor acotado. No es una
  garantía para cualquier host o modelo futuro con otro tamaño.
- No se entrenó, promovió ni seleccionó ningún modelo. No se modificaron datos,
  CSV, seed ni consumidores. El backend sigue usando su predictor integrado hasta
  fase 7.
- S-02 backend y E2E frontend no se revalidan por esta entrega.

[Resumen sanitizado](evidencia/ia-bloque-c-20261107-02/resumen.json),
[JUnit](evidencia/ia-bloque-c-20261107-02/pytest.xml),
[OpenAPI comprobado](evidencia/ia-bloque-c-20261107-02/openapi.json) y
[manifiesto](evidencia/ia-bloque-c-20261107-02/manifest.json).
