# Fase 4 — Límites internos y transacciones backend

**Estado: EN CURSO.** Inicio: 05/11/2026. Punto de retorno: `2f4140e`.

Se ejecuta por bloques pequeños para no mezclar identidades, flujos transaccionales y concurrencia. Separación estricta de implementación y evidencia.

---

## Bloque A — Infraestructura e identidad

Alcance: reloj técnico en core, registro ORM en bootstrap, propiedad de Usuario
en Usuarios, contratos de identidad sin hashes ni objetos ORM y auditoría pública
componible. Mantener tabla, API, algoritmo de hashing, precisión JWT, bloqueo,
revocación, timestamps y persistencia explícita de intentos fallidos.

**Bloque A implementado y validado el 05/11/2026**, ejecución definitiva
`bloque-a-20261105-02`. Commits: `fafaf4e` (código/tests) y `f158d4d` (documentación).

---

## Bloque B — Contratos públicos y workflows multimódulo

**Bloque B implementado y validado el 05/11/2026**, commit `fed8d2f`.

**Revisión B.1 EN CURSO:** se detectaron cambios no deseados en auditoría, una brecha en `REPROGRAMADA` y contratos que devolvían ORM. Las cifras siguientes son las declaradas por la entrega original B, no evidencia nueva de B.1. [Alcance, criterios y procedimiento B.1](B1.md). No iniciar C hasta registrar la corrección y su validación.

### Alcance ejecutado:
1. **Contratos públicos formales creados:**
   - `apps/backend/app/modules/citas/public.py`: operaciones de consulta `obtener_cita_consulta`, `obtener_metadatos_cita_para_cupo`, y operación componible `transicionar_cita_interno` sin commit.
   - `apps/backend/app/modules/intervenciones/public.py`: DTO inmutable `IntervencionSnapshot`, `validar_intervencion_de_cita`, y cálculo canónico de `acciones_disponibles_intervencion`.
   - `apps/backend/app/modules/lista_espera/public.py`: DTO inmutable `CupoLiberadoSnapshot`, `crear_cupo_liberado_interno` componible sin commit, y `obtener_cupo_por_cita_origen`.
2. **Desacoplamiento de persistencia ORM cruzada:**
   - `citas/service.py`: no importa modelos ORM de otros módulos; delega la creación del cupo a `lista_espera_public.crear_cupo_liberado_interno`.
   - `intervenciones/service.py`: no muta directamente entidades `Cita` ni añade filas `HistorialEstadoCita`; coordina la transición mediante `citas_public.transicionar_cita_interno` y `lista_espera_public.crear_cupo_liberado_interno`.
   - `lista_espera/service.py`: no importa `Cita` de citas; consume metadatos mediante `citas_public.obtener_metadatos_cita_para_cupo` y zona horaria desde `app.core.reloj.LIMA`.
3. **Atomicidad transaccional y unicidad de historial:**
   - Cada transición legal produce exactamente **1** fila de `HistorialEstadoCita` y el evento de auditoría requerido.
   - La sesión ORM `db: Session` se propaga en todas las operaciones del workflow con un único `db.commit()` al cierre.
4. **Pruebas y verificación:**
   - **8/8 nuevas pruebas aprobadas** en `apps/backend/tests/sistema/test_limites_flujos_fase4.py`.
   - Diagnóstico backend: **284 aprobadas / 1 fallo previo conocido (S-03)**.
   - Cobertura global de backend: **87.08 %** (umbral de 75 % holgadamente cumplido).
   - Zero regresiones sobre endpoints HTTP y contratos existentes.

---

## Siguiente entrega: Bloque C — Routers y pendientes S-03 / S-08

1. Retirar acceso directo a persistencia y llamadas `db.commit()` de routers:
   - `apps/backend/app/modules/lista_espera/router.py`: líneas 226 (`registrar_oferta`), 242 (`rechazo_oferta`), 258 (`desistimiento_oferta`).
   - `apps/backend/app/modules/reportes/router.py`: línea 67 (`exportar_intervenciones`).
2. Mover lógica de ofertas, rechazo y desistimiento (S-08) a casos de uso/servicios propios en `lista_espera`.
3. Corregir prueba histórica S-03 (`tests/test_reasignacion.py:52`) para consumir el objeto paginado `PaginaCuposLiberadosOut` sin debilitar aserciones.
4. Cobertura con pruebas específicas para cada operación de router desacoplada.

---

## Bloque D — Concurrencia, rollback y cierre final de Fase 4

1. Pruebas de concurrencia y contención en PostgreSQL (doble reasignación concurrente pesimista).
2. Pruebas de rollback multimódulo inducido en laboratorio aislado.
3. Construcción de imagen de Fase 4, freeze de OpenAPI y evidencia formal de cierre.
