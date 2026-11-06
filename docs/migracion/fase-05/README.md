# Fase 5 — Extraer y probar la aplicación IA independiente

**Estado vigente: EN CURSO — revisión correctiva (06/11/2026).**
El resultado histórico siguiente **no certifica cierre**: se detectaron fallos en
readiness, clave predeterminada, contrato y trazabilidad del runner. No se borra
la evidencia `ia-20261106-01` ni se reparan sus hashes retrospectivamente.
[Alcance y gates correctivos](CORRECCION.md). Backend/frontend permanecen intactos.

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
