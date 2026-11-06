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

Implementación en revisión. Prevalidación sin BD: 37 aprobadas; no sustituye gates.
La fase 4 permanece **EN CURSO** hasta evaluar los criterios del plan y evidencia.
Cada intento formal usa un run-id nuevo; no se sobrescriben resultados.
