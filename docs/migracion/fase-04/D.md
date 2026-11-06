# Bloque D — criterios congelados antes de validación

Baseline obligatorio: `2ad167e` (C registrado). D no autoriza fase 5 ni cambios
de esquema, contratos HTTP, reglas, CSV, credenciales o artefacto del modelo.

## Implementación

- Recargar filas al adquirir `FOR UPDATE`, incluso si ya existen en identity map.
  Una segunda transición propia conserva su cambio mediante flush dirigido.
- Orden de composición: cita → intervención → cupo → candidato. Los casos que
  solo modifican intervención o candidato no adquieren después locks de padres.
- Coordinadores en `app/workflows/`: contratos públicos, misma sesión, sin commit.
- Oferta/cierre/reasignación e importación tienen entradas componibles sin commit;
  los servicios HTTP cierran una vez. Seed confirma usuarios e importación juntos.
- Lecturas compuestas en adaptadores explícitos; excepciones exhaustivas en
  `bootstrap/limites.py`, comprobación de límites y DAG de imports.

## Gates de aceptación

1. Laboratorio PostgreSQL nuevo, red interna sin puertos host, rol app limitado,
   volumen exclusivo; conservar intentos fallidos y recursos anteriores.
2. Diagnóstico sin regresiones frente a C y nuevas pruebas aprobadas; cobertura
   ≥75 %. Suite completa mantiene explícito S-02 en `tests/ia` (no suite verde).
3. Nueve carreras HTTP: mismo cupo, mismo candidato, ofertas, liberaciones,
   cancelación vs liberación, respuesta estricta, cierre y creación de intervención.
   Dos sesiones con ORM precargado, espera observada con `pg_blocking_pids`, un
   éxito efectivo y un conflicto; comprobar filas/historial/auditoría persistidos.
4. Rollback tras flush en cancelación, respuesta legacy, reasignación e importación,
   observado desde conexiones independientes; preservar gates de identidad.
5. Imagen nueva identificada por ID inmutable: OpenAPI, DDL, modelo y predicciones
   idénticos. Proceso no-root, sin fuentes backend montadas, sin env owner ni datos
   legacy; regresión runtime y sondas HTTP/rollback ejecutadas sobre `/app`.
6. Fuentes y protegidos sin cambios durante ejecución. Publicación sanitizada
   separada del commit de implementación; hashes comprobados desde clon limpio.

## Estado

**D validado; fase 4 COMPLETADA (06/11/2026)** tras revisión de criterios del plan.
Prevalidación sin BD: 37 aprobadas; no sustituye los gates siguientes.
Cada intento formal usa un run-id nuevo; no se sobrescriben resultados.

Intentos conservados: `bloque-d-20261106-01` interrumpido por timeout del host;
`bloque-d-20261106-02` detectó un acceso a relación ORM opcional sin `getattr`
en lectura de intervenciones. Corregido respetando la ausencia histórica de esa
relación. Ninguno se considera aceptación; ambos laboratorios detenidos.
`bloque-d-20261106-03` falló al provisionar: pg_isready por socket observó el
servidor temporal de initdb. El runner espera ahora TCP del servidor definitivo.

## Ejecución aceptada y revisión final

`bloque-d-20261106-04`, baseline `2ad167e`, implementación `500c040` + `a463fdb`,
runner `62f04ac`; evidencia publicada por separado en `f2c5823`.

- Diagnóstico **341 → 352 aprobadas**, once nuevas, sin casos previos retirados ni
  cambios de estado; cobertura **91,23445556566575 %**.
- **211 pruebas empaquetadas**, **9 carreras HTTP** y **4 rollbacks** aprobados.
  Las nueve carreras observaron espera PostgreSQL con filas retenidas en memoria,
  un único éxito y un conflicto. Identidad entre conexiones también pasó.
- Paridad exacta OpenAPI/DDL/modelo/predicciones; imagen no-root y sin backend
  montado: `sha256:b1225267a59311a2fadce32ea139cabaa948b0b6ff2d344eb083a48e6421666d`.
- Los tests D comprueban contratos por módulo, excepciones exhaustivas de lectura,
  DAG de imports, workflows sin commit, refresco de lock y transiciones/importador
  componibles con reversión. Los gates A/B.1/C forman parte del diagnóstico D.
- Auditoría append-only y permisos: suites de rol operativo/negocio aprobadas,
  sin revisiones nuevas; login/bloqueo y rollback de contraseña repetidos.
- Importación/seed: importador sin commit probado; seed revisado para flush de
  usuarios + importación y un commit al final, sin begin anidado. **No se ejecutó
  el seed demo integral**; se conserva la rama legacy de datos ya existentes y
  su deuda de detección de cargas parciales, reservada a fase 6.
- Fuentes/protegidos sin cambios durante ejecución, cuatro laboratorios detenidos.
  Crudos privados conservados; solo resumen y JUnit sanitizados en Git. Hashes
  comprobados contra índice Git y desde clon limpio de `f2c5823`, sin env/modelo.

S-02 sigue provocando el mismo fallo de colección de la suite completa; **no es
una suite completa verde**. Frontend no reejecutado. El resumen inmutable decía
EN CURSO antes de esta revisión final; no se altera retrospectivamente. El cierre
corresponde al alcance de fase 4 y no resuelve deudas ajenas ni inicia fase 5.

Retorno D: `2ad167e`; retorno de fase: `2f4140e`. Revertir únicamente entregas de
lógica compatibles con trabajo posterior; no restaurar ni eliminar volúmenes,
no hacer downgrade de datos. No se desplegó ni modificó el principal.
