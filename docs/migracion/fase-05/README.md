# Fase 5 — Extraer y probar la aplicación IA independiente

**Estado vigente: EN CURSO — revisión correctiva (06/11/2026).**
El resultado histórico siguiente **no certifica cierre**: se detectaron fallos en
readiness, clave predeterminada, contrato y trazabilidad del runner. No se borra
la evidencia `ia-20261106-01` ni se reparan sus hashes retrospectivamente.
[Alcance y gates correctivos](CORRECCION.md). Backend/frontend permanecen intactos.

## Última entrega — bloque A validado

**Extracción offline de entrenamiento/evaluación/métricas aprobada**, ejecución
`ia-bloque-a-20261106-01`. Código `83a96a6`, runner `22c6788`, evidencia `9f6636b`.
Módulos en `apps/ia/training/`, datos/versiones/fecha explícitos y escritura
opcional exclusiva a candidato nuevo; sin BD, generador automático, promoción,
escritura o caché desde serving. Backend y serving IA permanecen sin cambios.

**105/105 pruebas**, cobertura conjunta **96,89 %**, offline **100 %**. Comparación
de dos entrenamientos reales con los mismos 1000 registros: splits 700/150/150,
preprocesadores, hiperparámetros, probabilidades crudas de ambos modelos, métricas,
equidad e importancias idénticos. F1 de prueba **0,8621**; candidatos solo en scratch,
artefacto activo/registry intactos. También pasan los 207 casos de inferencia y
HTTP real (100 elementos en 0,947 s). Sin nuevos algoritmos ni pipeline fase 6.

Imagen de la entrega:
`sha256:93b75b1f7d095dbdeb3c5d478cdf209026fb7ea6faf4822f834a0612fe329892`.
[Alcance, entradas y límites A](BLOQUE_A.md),
[evidencia](evidencia/ia-bloque-a-20261106-01/manifest.json). Hashes del índice y clon
limpio Windows/autocrlf aprobados. Ningún contenedor de prueba quedó activo.

**Estado global EN CURSO:** quedan B (generador/datasets/CSV) y C
(timeout/concurrencia); no se iniciaron en A. Los pendientes de entrenamiento
mencionados en el resultado histórico de corrección siguiente quedan resueltos
por A, sin marcar completo el ítem combinado de datasets ni cerrar la fase.

## Corrección vigente aceptada

Ejecución `ia-correccion-20261106-03`, código probado `bba0e61`, evidencia
`8dd4cdd`. **83/83 pruebas, 96,01 % cobertura, 207 casos de paridad diferencial**
en todos los campos, tres niveles de riesgo. Tres autopruebas stdlib del runner.
HTTP real: lote de 100 en 0,98 s; artefacto intacto. Imagen:
`sha256:21c8cd34539de93335c813b13a2bc7e81e254ba2ce293a9df90782c5e09e3bbf`.

- Sin clave predeterminada: `IA_API_KEY` explícita y no vacía, fallo de arranque
  seguro si falta. No usar secretos del backend ni publicar la clave en comandos.
- Montar el artefacto legacy confiable RO en `/models`, o configurar explícitamente
  `MODEL_REGISTRY_DIR`. No buscar silenciosamente dentro del backend.
- Manifiesto aprobado empaquetado en `manifests/legacy-approved.json`: hash antes
  de joblib, librerías/clases/features/catálogos/versión/umbrales/smoke. No admite
  artefactos arbitrarios ni promociones implícitas; un fallo deja readiness 503.
- `generado_en` del dataset legacy es fecha de creación de la importación de
  metadata. Los conteos se reconstruyen de tasas/tamaños declarados en el artefacto;
  no se afirma linaje raw ni se inventan hashes/IDs o una fecha de dataset.
- Versiones requeridas, enteros sin coerción y schemas congelados comprobados;
  OpenAPI incluye seguridad, respuestas tipadas y errores. Inferencia no finita
  falla sin score ficticio. Matemáticas y redondeos finitos conservados.
- Body ASGI limitado durante recepción, máximo 256 KiB y 10 s para recibirlo.
  Este plazo **no es** un timeout duro de cómputo nativo.
- Validación en imagen no-root, RO, sin red externa ni DSN/backend montado,
  acotada a 2 CPU/1 GiB. Un worker, límite 16 conexiones y un hilo nativo.

Construcción formal y verificación:

```powershell
python -B docs/migracion/fase-05/validar_ia.py ejecutar --run-id ia-<identidad-nueva>
python -B docs/migracion/fase-05/validar_ia.py publicar --run-id ia-<identidad-nueva>
python -B docs/migracion/fase-05/validar_ia.py verificar --run-id ia-correccion-20261106-03
```

El runner construye con un contexto contractual exclusivo de archivos registrados,
ejecuta por ID inmutable y obtiene cifras reales de JUnit/coverage. No sobrescribe
intentos ni publica logs/env. Clon limpio Windows con autocrlf: evidencia correctiva
y seed verifican; eso comprueba integridad, no reejecuta tests ni aporta el modelo.
No se modifica la evidencia histórica defectuosa de la primera implementación.

[Resumen vigente](evidencia/ia-correccion-20261106-03/resumen.json),
[JUnit sanitizado](evidencia/ia-correccion-20261106-03/pytest.xml),
[OpenAPI comprobado](evidencia/ia-correccion-20261106-03/openapi.json) y
[manifiesto](evidencia/ia-correccion-20261106-03/manifest.json).

**Pendientes de fase 5:** extracción del entrenamiento y generador/datasets/CSV,
política de retirada temporal y timeout de cómputo bajo concurrencia. La medición
local del lote no sustituye esa resolución ni una prueba de carga sostenida.
No se reducen requisitos para cerrar la fase. Backend sigue integrado; fase 6/7
no iniciadas por esta corrección. S-02 histórico backend y frontend no revalidados.

## Resultado histórico de la primera implementación (supeditado a corrección)
- **Baseline:** `af13b3b` (Cierre y evidencia sanitizada de la validación del Seed).
- **Punto de retorno:** `af13b3b`.
- **Objetivo:** Disponer de una aplicación de IA autónoma, contenerizada y verificada por contrato antes de modificar sus consumidores.
- **Ejecución aceptada:** `ia-20261106-01`.
- **Imagen ID:** `sha256:82d2316f5247f5f698e966885b22f2787ece0f40573c38a5c75b831e6e070395` (no-root `predicitas:1000`).
- **Pruebas empaquetadas:** **21/21 aprobadas / 0 fallos**.
- **Cobertura de código:** **92.0 %** (supera holgadamente el umbral de 80 %).
- **Paridad matemática:** Probabilidades, clasificación por umbrales y explicabilidad TreeSHAP 100 % idénticas a la línea base congelada.
- **Backend intacto:** `apps/backend/` y `apps/frontend/` se conservaron sin cambios.

---

## Principios y Reglas de No-Regresión

1. **Patrón Strangler Fig (Estrangulamiento Progresivo):**
   - Se construye `apps/ia/` como servicio completamente independiente.
   - **El backend integrado (`apps/backend`) NO se modifica en esta fase:** sigue atendiendo peticiones con su predictor interno. La sustitución y reconexión de clientes corresponde estrictamente a la **Fase 7**.
   - El frontend (`apps/frontend`) permanece intacto.
2. **Aislamiento absoluto de infraestructura:**
   - La nueva app IA **no depende de PostgreSQL**: no contiene DSN, ni SQLAlchemy, ni modelos relacionales.
   - **Cero dependencias cruzadas:** no importa módulos de `apps/backend`.
   - Inferencia es de solo lectura (**read-only**): ningún endpoint HTTP entrena, calibra ni sobrescribe archivos de modelos en disco.
3. **Paridad matemática y ética estricta:**
   - Probabilidades idénticas redondeadas a 3 decimales (`round(max(0, min(1, raw)), 3)`).
   - Umbrales idénticos: `BAJO < 0.300`, `MEDIO 0.300..0.450`, `ALTO > 0.450`.
   - Explicabilidad TreeSHAP local idéntica (top 3 factores, longitud $\le 255$ caracteres).
   - Rótulo ético y marcas de simulación obligatorias según RF-056.
4. **Cumplimiento de contrato:**
   - Estricto apego a `contracts/ia/openapi.objetivo.v1.json` y schemas JSON asociados.
   - Autenticación interna mediante header `X-IA-API-Key` con comparación segura en tiempo constante.
   - Límite de tamaño de payload $\le 256\text{ KiB}$ (`SOLICITUD_DEMASIADO_GRANDE`, HTTP 413).
   - Lotes de 1 a 100 elementos; no se admiten respuestas parciales.

---

## Desglose de Entregas por Bloques

### Bloque A — Estructura, Configuración y Core Predictor Autónomo
- Crear `apps/ia/` con estructura limpia:
  - `apps/ia/app/config.py`: Variables de configuración (puerto, clave API, ruta a registry).
  - `apps/ia/app/schemas.py`: Modelos Pydantic v2 validados contra `contracts/ia/*.schema.json`.
  - `apps/ia/app/core/features.py`: Derivación y validación de features pre-cita sin dependencias externas.
  - `apps/ia/app/core/inference.py`: Pipeline de inferencia, clamping, redondeo y TreeSHAP.
  - `apps/ia/app/core/model_registry.py`: Carga en memoria y verificación del artefacto serializado.
  - `apps/ia/app/auth.py`: Autenticación segura de cabecera `X-IA-API-Key`.
  - `apps/ia/app/main.py`: Aplicación FastAPI, lifespan de carga, middleware de 256 KiB y rutas base.

### Bloque B — Endpoints de Contrato, Manejo de Errores y Paridad
- Implementar los 6 endpoints requeridos:
  - `GET /health/live`
  - `GET /health/ready`
  - `GET /v1/model`
  - `GET /v1/metrics`
  - `GET /v1/dataset`
  - `POST /v1/predict`
  - `POST /v1/predict-batch`
- Manejadores de error exactos según `error.v1.schema.json`:
  - 401 `NO_AUTENTICADO`
  - 409 `VERSION_MODELO_INCOMPATIBLE`
  - 413 `SOLICITUD_DEMASIADO_GRANDE`
  - 422 `VALIDACION`
  - 503 `MODELO_NO_DISPONIBLE`
  - 500 `ERROR_INTERNO`
- Suite de pruebas de paridad contra `contracts/examples/casos.json` y predictor original.

### Bloque C — Empaquetado Docker y Aislamiento de Runtime
- `apps/ia/Dockerfile`: imagen no-root, con `libgomp1` para OpenMP (LightGBM).
- Validación de arranque en contenedor independiente sin red ni volúmenes del backend.

### Bloque D — Evidencia, Verificación Final y Cierre de Fase 5
- Generación y publicación de evidencia sanitizada.
- Actualización de checklist y certificación de Fase 5 completada.
