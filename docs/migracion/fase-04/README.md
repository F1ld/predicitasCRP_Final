# Fase 4 — Límites internos y transacciones backend

**Estado: COMPLETADA (06/11/2026).** Inicio: 05/11/2026. Punto de retorno: `2f4140e`.
Responsable: agente bajo autorización del usuario. El cierre D al final de esta
bitácora sustituye los estados históricos EN CURSO. Fase 5 no iniciada.

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

**B.1 corregido y validado:** código en `d59d290`, ajuste de fixture en `6e7787c`; ejecución vigente `bloque-b1-20261105-02`. Las cifras y descripciones del apartado B original se conservan como históricas y quedan complementadas por la corrección B.1 siguiente. [Alcance, criterios y procedimiento B.1](B1.md).

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

## B.1 — Correcciones de auditoría y contratos antes de C

**Estado: validado; fase 4 completa sigue EN CURSO.** Baseline explícito `2f95273`, implementación probada `6e7787c0bce47bfd2d2e216b0de8c6b42cdda149`, imagen de dependencias por ID (fuentes montadas RO, no un build de entrega fase 4).

- Restaurados los payloads de liberación del bloque A: ID real, evento también con cupo existente, campos de liberación explícita y orden de auditoría de cancelación.
- `transicionar_cita_interno` rechaza `REPROGRAMADA` sin fecha antes de escribir. La reprogramación completa conserva su endpoint.
- Los contratos de Citas, Cupos e Intervenciones retornan snapshots inmutables; las operaciones de transición reciben ID. Se retiraron `fabrica_cupo`, la autoimportación y los imports de ORM/reglas privados ajenos en los tres servicios.
- Sin cambiar permisos, consentimiento, diferencias POST/PATCH, esquema, modelo ni S-02/S-03. Persisten las composiciones de lectura y tareas de C/D expresamente documentadas en [B1.md](B1.md).

| Verificación B.1 | Resultado |
|---|---|
| Pruebas focalizadas (B + B.1) | **27/27 aprobadas**: 8 existentes + 19 nuevas |
| Diagnóstico baseline B / actual B.1 | **284/1 → 303/1**, todos los casos/estados anteriores conservados |
| Cobertura aplicación | **87,42 %**, sin rebajar umbral de 75 % |
| Suite completa | Mismo error histórico de colección IA; no se declara verde |
| API / DDL / modelo / predicciones | Paridad exacta con baseline |
| Rollback tras flush de cupo | Cita, respuesta, cupo, historial y auditoría intactos desde otra conexión |
| Identidad / login / bloqueo / contraseña | Comprobaciones independientes del bloque A repetidas y aprobadas |
| Archivos protegidos | `.env`, modelos, CSV y revisiones existentes idénticos |
| Laboratorios B.1 01 y 02 | Detenidos, recursos conservados; sin volúmenes originales |
| Frontend / concurrencia | No reejecutado / pendiente del bloque D |

[Resumen y fuentes probadas](evidencia/bloque-b1-20261105-02/resumen.json), [JUnit focalizado sanitizado](evidencia/bloque-b1-20261105-02/b1_focalizadas.xml) y [manifiesto](evidencia/bloque-b1-20261105-02/manifest.json). El intento 01 se conserva como fallido por la nueva prueba de ciclo de sesión; no se reutilizan sus resultados. Los crudos permanecen privados en runtime. Comprobar el paquete sin Docker ni secretos:

```powershell
python -B docs/migracion/fase-04/publicar.py --run-id bloque-b1-20261105-02 --verify-only
```

El commit de resultados solo publica documentación/evidencia; no cambia las fuentes probadas. `--verify-only` comprueba integridad del paquete, no reejecuta suites ni demuestra identidad de un árbol posterior.

---

## Bloque C — Routers y pendientes S-03 / S-08

**C implementado y validado (06/11/2026):** commit de código `d7c7f45`, ejecución `bloque-c-20261106-01`, baseline B.1 `6da1c49`. [Alcance y criterios congelados](C.md). Incluye corrección de forwarding S-05 al extraer REP-02. **Fase 4 sigue EN CURSO**, pendiente D.

Alcance ejecutado, conservado para trazabilidad:

1. Retirar acceso directo a persistencia y llamadas `db.commit()` de routers:
   - `apps/backend/app/modules/lista_espera/router.py`: líneas 226 (`registrar_oferta`), 242 (`rechazo_oferta`), 258 (`desistimiento_oferta`).
   - `apps/backend/app/modules/reportes/router.py`: línea 67 (`exportar_intervenciones`).
2. Mover lógica de ofertas, rechazo y desistimiento (S-08) a casos de uso/servicios propios en `lista_espera`.
3. Corregir prueba histórica S-03 (`tests/test_reasignacion.py:52`) para consumir el objeto paginado `PaginaCuposLiberadosOut` sin debilitar aserciones.
4. Cobertura con pruebas específicas para cada operación de router desacoplada.

### Resultado C

- Todos los routers quedan sin imports de modelos/repositorios, SQL, lecturas ORM directas ni commits. Los servicios conservan los filtros/paginación históricos (no se endureció S-12).
- S-08: oferta/rechazo/sin respuesta/asignación auditables en la bitácora existente, con locks cupo → candidato, matching y un commit por caso de uso. Detalle y oferta vigente/historial se proyectan de eventos con referencia al ID de oferta; no se creó tabla ni se repararon datos legacy.
- S-03: el recorrido completo de reasignación pasa usando `items`, reloj fijo y rechazo 400 `SOLICITUD_INVALIDA` de confirmación falsa (caracterizado en baseline). Se conservan y amplían las comprobaciones de no escrituras, matching, prioridades, confirmación humana y doble asignación secuencial.
- S-05: TypeError del alias reproducido sin BD en baseline y corregido por forwarding de Request/usuario. JSON/CSV/OOXML de REP-02 y roles verificados. REP-03 xlsx (S-06) no se cambió.

| Verificación C | Resultado |
|---|---|
| Diagnóstico backend baseline / actual | **303 aprobadas + 1 fallo → 341 aprobadas, 0 fallos** |
| Casos anteriores | Único cambio permitido: S-03 failure → passed; ningún otro caso retirado/cambiado de estado |
| Nuevas pruebas | **37 aprobadas** |
| Focalizadas C + recorrido S-03 | **38/38 aprobadas** |
| Cobertura aplicación | **91,15 %**, umbral 75 % conservado |
| Suite completa | Mismo error previo de colección S-02; **no es suite verde** |
| OpenAPI / DDL / modelo / predicciones | Idénticos |
| Rollback con fallo tras flush | Oferta, cierre y exportación observados desde conexiones independientes |
| Archivos protegidos / laboratorio | `.env`, modelos, CSV, revisiones intactos; laboratorio nuevo detenido y preservado |
| Frontend / concurrencia real / imagen final fase 4 | No reejecutado / pendientes del D |

[Resumen y fuentes ejecutadas](evidencia/bloque-c-20261106-01/resumen.json), [JUnit focalizado](evidencia/bloque-c-20261106-01/c_focalizadas.xml) y [manifiesto sanitizado](evidencia/bloque-c-20261106-01/manifest.json). El commit de resultados no modifica las fuentes probadas. Verificación de paquete, sin repetir pruebas ni certificar un árbol posterior:

```powershell
python -B docs/migracion/fase-04/publicar.py --run-id bloque-c-20261106-01 --verify-only
```

**Límites operativos:** EN_OFERTA legacy sin candidato en bitácora no se cierra adivinando identidad (409 `OFERTA_NO_REGISTRADA`); no se modifica masivamente. El endpoint histórico de desistimiento cierra por SIN_RESPUESTA, no da de baja global al candidato. La baja global sigue por PATCH de lista de espera. No se añadieron rutas ni ajustes frontend para ocultar divergencias previas.

---

## Bloque D — Concurrencia, rollback y cierre final de Fase 4

**Validado:** `bloque-d-20261106-04`, baseline `2ad167e`, código `500c040` +
`a463fdb`; runner `62f04ac`. [Criterios y revisión](D.md).

| Verificación D | Resultado |
|---|---|
| Diagnóstico baseline / actual | **341/0 → 352/0**, once pruebas nuevas; ningún caso previo cambia |
| Cobertura | **91,23 %**, umbral 75 % conservado |
| Regresión runtime empaquetada | **211/211**, `/app` sin montaje de fuentes backend |
| Carreras HTTP | **9/9**, dos sesiones con filas precargadas, bloqueo observado en PostgreSQL, un éxito y un 409 |
| Rollback independiente tras flush | **4/4**: cancelación, respuesta legacy, reasignación, importación |
| Identidad | Login fallido/bloqueo persistidos; rollback de contraseña repetido |
| Arquitectura | Contratos, excepciones read-only, workflows sin commit, DAG y composición aprobados |
| OpenAPI / DDL / modelo / predicciones | Paridad exacta |
| Suite completa | S-02 histórico conservado; **no se declara verde** |
| Protegidos / originales | Sin cambios; sin puertos host ni volúmenes originales |
| Laboratorios D 01–04 | Detenidos y conservados; 01–03 no son aceptación |
| Evidencia | Commit separado `f2c5823`; hashes del índice y paquete verificados en clon limpio |

Imagen final ejecutada por ID:
`sha256:b1225267a59311a2fadce32ea139cabaa948b0b6ff2d344eb083a48e6421666d`.
Usuario 1000, sin `.env`/datos legacy ni DSN owner en runtime empaquetado;
versiones efectivas de dependencias registradas. No se desplegó al principal.

[Resumen sanitizado](evidencia/bloque-d-20261106-04/resumen.json),
[JUnit diagnóstico](evidencia/bloque-d-20261106-04/actual_diagnostico.xml),
[JUnit empaquetado](evidencia/bloque-d-20261106-04/paquete_runtime.xml) y
[manifiesto](evidencia/bloque-d-20261106-04/manifest.json).

```powershell
python -B docs/migracion/fase-04/publicar.py --run-id bloque-d-20261106-04 --verify-only
```

El resumen conserva EN CURSO porque se capturó antes de la revisión final del
checklist. El clon limpio verifica integridad del paquete, no reejecuta suites ni
reconstruye el modelo privado. Seed/import se revisaron para confirmar una vez;
la reversión del importador se probó, pero no se ejecutó el poblado demo integral.
No se cambió su política legacy de retorno si ya hay datos; esa deuda sigue en
fase 6. Frontend no reejecutado. S-02 y demás deudas fuera de alcance no se ocultan.
El cierre se limita a los criterios de fase 4, no a sanidad integral del producto.
