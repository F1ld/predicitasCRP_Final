# Registro de compatibilidad temporal del generador backend

Designación temporal: **06/11/2026**, bloque B de fase 5. No se modifica código
backend para poner esta marca: el registro externo preserva los hashes aceptados
de fuente y comportamiento. La reexportación pública ya estaba marcada temporal.

Canónico nuevo: `apps/ia/datasets/synthetic.py`. Copia legacy conservada:
`apps/backend/app/modules/citas/synthetic.py`. No es una segunda implementación
permanente ni permiso para introducir divergencias matemáticas.

| Consumidor actual | Motivo de conservación / retirada |
|---|---|
| `apps/backend/scripts/seed.py` | Migrado en fase 6 C a CSV operacional explícito; ya no importa generador. Pruebas de repetición/carga parcial y límites en [bloque C](../fase-06/BLOQUE_C.md). No autoriza retirar las otras copias/consumidores. |
| `apps/backend/scripts/exportar_csv.py` | Migrado: copia CSV preparado con manifiesto/hash y parámetros coincidentes; generación canónica en `datasets.exportar_csv` de IA. Cuatro inválidas preservadas. |
| `apps/backend/app/modules/citas/public.py` | Reexport temporal, retirarlo solo cuando no queden consumidores. |
| `apps/backend/app/modules/ia/predictor.py` | Generación histórica por fallback del predictor integrado. Se conserva hasta la sustitución de consumidores de IA de fase 7; no introducir fallback en el servicio nuevo. |
| Tests backend de Citas/predictor | Migrados a CSV explícitos, sin importar generador; asserts y caso de 5000 preservados. Los tests del motor integrado siguen vigentes hasta 7. |
| `apps/frontend/tests/validar_diseno.py` | Migrado a tres CSV explícitos con hashes; solo reasigna prefijos. Payloads 45/4 y 20/4 verificados con backend real y rollback. |
| Laboratorios históricos | Evidencia inmutable. Los runners de referencia pueden usar imágenes preservadas, no una copia legacy activa mantenida indefinidamente. |

**Fecha objetivo provisional de retirada/revisión: 20/11/2026.** Es una marca de
planificación, no una fecha de eliminación automática ni una promesa de finalizar
fases 6/7. Si los gates no están cumplidos, registrar revisión y nueva fecha;
nunca borrar la copia para cumplir el calendario dejando consumidores rotos.

Gate efectivo de retirada: seed/exportador consumen datos explícitos sin importar
el generador; backend usa IA autónoma validada; búsqueda de consumidores productivos
sin referencias; regresión backend/frontend y retorno aprobados. Cada cambio
requiere su fase/autorización. B solo aporta paridad y el CSV futuro: no conecta
consumidores, no borra la copia y no modifica credenciales ni datos existentes.

## Revisión inicial — fase 6 D (07/11/2026, histórica)

[Inventario, gate y bloqueos D](../fase-06/BLOQUE_D.md): 7 dependencias directas
conocidas y 9 imports de namespace informativos, hashes de generadores preservados.
16/16 autopruebas aprobadas; el gate estricto devuelve 2 esperado y **no permite
el retiro total**. Seed C ya migrado; predictor/reexport, exportador y QA siguen
vigentes. No se retira código ni se considera cerrada D. Resolver explícitamente
el criterio de cierre frente a la dependencia de fase 7, sin adelantarla ni borrar
consumidores. Fecha 20/11/2026 conservada como revisión, no borrado automático.

**Actualización aprobada (07/11/2026):** el usuario aceptó el cierre D como
[retirada programada](../fase-06/DECISION_D_RETIRADA_PROGRAMADA.md). No requiere
eliminar físicamente la copia antes de 7, pero sí migrar previamente exportador
y cuatro consumidores QA. Solo predictor/reexport pueden quedar temporalmente;
no se han realizado aún esas cinco migraciones. D sigue EN CURSO; E/7 pendientes.
19/19 autopruebas de guardas; la aprobación no habilita borrar código ni cerrar
fase 6 sin la evidencia de E. La revisión original anterior queda como histórica.

## Estado vigente después de las migraciones

[Migraciones D validadas](../fase-06/MIGRACIONES_D.md): cinco consumidores ya
desacoplados del generador legacy; solo quedan predictor/reexport (dos referencias
directas) y nueve namespaces informativos. D completada como **retirada programada**,
con guardas físicas todavía cerradas. 241 pruebas IA, 339 backend y 33 de archivos/
CLI aprobadas; paridad de nueve escenarios CSV frente a referencia preservada.
No se borra la copia: la eliminación física queda para 7 tras sustituir el motor
y validar sus gates. E pendiente antes de cerrar fase 6/iniciar 7. Los párrafos
anteriores de consumidores pendientes son historial, no el estado actual.
