# Fase 4 — Límites internos y transacciones backend

**Estado: EN CURSO.** Inicio: 05/11/2026. Punto de retorno: `2f4140e`.

Se ejecuta por bloques para no mezclar una reorganización de identidad con todos
los workflows de escritura. No se crean commits automáticamente.

## Bloque A — Infraestructura e identidad

Alcance: reloj técnico en core, registro ORM en bootstrap, propiedad de Usuario
en Usuarios, contratos de identidad sin hashes ni objetos ORM y auditoría pública
componible. Mantener tabla, API, algoritmo de hashing, precisión JWT, bloqueo,
revocación, timestamps y persistencia explícita de intentos fallidos.

**Bloque A implementado y validado el 05/11/2026**, ejecución definitiva
`bloque-a-20261105-02`. **La fase 4 completa sigue EN CURSO.**

| Comprobación | Resultado |
|---|---|
| Nuevas pruebas de límites/identidad/rollback | **15/15 aprobadas** |
| Diagnóstico anterior, snapshot completo de `2f4140e` | **261 aprobadas / 1 fallo previo** |
| Diagnóstico con bloque A | **276 aprobadas / el mismo fallo previo** |
| Cobertura aplicación | **87,14 %**, umbral de 75 % conservado |
| Suite completa | Mismo error previo de colección en `tests.ia`; salida 2 en ambos árboles |
| OpenAPI, DDL de metadata, modelo y tres predicciones congeladas | Idénticos; sin entrenar ni actualizar snapshots |
| Alembic desde código actualizado | Salida 0 sobre BD de laboratorio en head; sin revisiones nuevas |
| Login fallido/bloqueo | Cinco intentos fallidos y bloqueo visibles desde conexiones independientes |
| Fallo de auditoría tras flush de contraseña | Rollback comprobado desde otra conexión; clave y timestamp anteriores preservados |
| Preservación | `.env`, modelos, CSV y revisiones existentes idénticos por hash |
| Laboratorios 01 y 02 | **Detenidos**, recursos conservados, sin borrar volúmenes |
| Frontend/E2E visual | No reejecutados ni certificados |

El único fallo del diagnóstico sigue siendo S-03, prueba antigua de reasignación
que interpreta una respuesta paginada como lista. No se arregló/ocultó como parte
de este bloque; bloquea el cierre funcional de la fase completa hasta su entrega
correspondiente. Tampoco se corrigió S-02 de colección IA ni se extrajo el predictor.

[Resumen con hashes de las fuentes ejecutadas](evidencia/bloque-a-20261105-02/resumen.json)
y [manifiesto de evidencia](evidencia/bloque-a-20261105-02/manifest.json). Se publican
JUnit sin tracebacks, logs ni secretos. Los crudos quedan en
`runtime/test-results/fase-04/bloque-a-20261105-02/`, ignorados por Git.

Verificación de integridad sin Docker ni archivos privados (no repite pruebas):

```powershell
python -B docs/migracion/fase-04/publicar.py --run-id bloque-a-20261105-02 --verify-only
```

Los módulos de compatibilidad `auth/models.py`, `auth/reloj.py`, `auth/repository.py` y `core/models.py`
se conservan para herramientas históricas; no son nuevas implementaciones ni
autorizan nuevos consumidores. Las aplicaciones y pruebas vigentes se actualizan.

## Pendiente para cerrar la fase completa

- Contratos de Citas/Intervenciones/Lista de Espera y adaptadores de lectura.
- Workflows componibles, orden de locks y un único cierre transaccional.
- Retirar SQL/commits de todos los routers, incluyendo ofertas y exportaciones.
- Resolver gates S-03/S-08 con pruebas independientes, sin ocultar baseline.
- Rollback multímódulo y concurrencia real en PostgreSQL.
- Tests de arquitectura de todos los módulos y regresión completa caracterizada.

No se extrae IA (fases 5–7), no se entrena/promueve modelo, no se modifican
credenciales/esquema ni se inicia o escribe en volúmenes preexistentes.

La validación de este bloque se registra separadamente: no equivale al cierre
de fase 4, a suite completa verde ni a certificación frontend/E2E visual.

Diseño aplicado: [alcance y transacciones de identidad](ALCANCE_BLOQUE_A.md).
Continuación concreta: [siguiente bloque](SIGUIENTE_BLOQUE.md).

## Laboratorio y procedimiento

Se usa la imagen de fase 3 por ID para mantener Python 3.12 y las dependencias
efectivas, montando las fuentes del backend **en solo lectura**. No es un build
nuevo de la imagen de entrega ni un arranque del stack principal. Los hashes de
las fuentes ejecutadas identifican el árbol sin necesidad de crear un commit.

`preparar` crea un snapshot Git del punto de retorno en `backups/`, añade copias
por hash de ambos modelos privados (activo y preservación legacy), y crea una BD
**nueva** con red interna, sin puertos publicados y con credenciales aleatorias
en un directorio privado con ACL. Rechaza nombres de recursos preexistentes. No
restaura datos del principal ni ejecuta seed. Las migraciones existentes se
aplican solo al laboratorio. No se añaden revisiones.

Ejemplo desde la raíz en PowerShell, usando siempre un run-id nuevo:

```powershell
python -B docs/migracion/fase-04/validar.py preparar --run-id bloque-a-20261105-02
python -B docs/migracion/fase-04/validar.py baseline --run-id bloque-a-20261105-02
python -B docs/migracion/fase-04/validar.py actual --run-id bloque-a-20261105-02
python -B docs/migracion/fase-04/validar.py detener --run-id bloque-a-20261105-02
python -B docs/migracion/fase-04/validar.py resumen --run-id bloque-a-20261105-02
python -B docs/migracion/fase-04/publicar.py --run-id bloque-a-20261105-02
```

Los comandos rechazan salidas existentes; **no repetir este ejemplo sobre la
ejecución ya registrada**. La preparación fija `2f4140e` como punto de retorno;
una entrega posterior requiere revisar esa decisión, no cambiarla a ciegas.
Ante fallo, conservar evidencia y detener solo el laboratorio que identifique su
JSON; no borrar ni reutilizar sus volúmenes como si fueran vacíos.

`baseline` y `actual` registran por separado códigos de salida de la suite completa
y diagnóstico. El estado global del comando no sustituye leer esos resultados;
`resumen` exige equivalencia de los casos anteriores, nuevas pruebas aprobadas,
paridad de API/DDL/predicciones/modelo, cobertura ≥75% y archivos protegidos
intactos. La prueba adicional de identidad verifica con conexiones independientes
persistencia de fallos/bloqueo y rollback después de flush de una contraseña.

### Intento inicial conservado

`bloque-a-20261105-01`: el snapshot inicial llevaba el modelo activo, pero no la
copia legacy ignorada por Git. Eso produjo un fallo de preparación adicional en
el test de inventario de fase 3, no una regresión del backend. Se conserva toda
su evidencia cruda. La implementación aprobó sus 15 pruebas nuevas, pero ese
intento **no se usa como baseline final**. El laboratorio quedó detenido, sin
borrar recursos. Se corrigió la preparación y se repite la comparación en una
BD nueva (`bloque-a-20261105-02`), sin reutilizar resultados ni ocultar el fallo.
