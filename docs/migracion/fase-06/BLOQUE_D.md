# Fase 6 — bloque D: inventario y retirada controlada del generador

**Estado vigente: COMPLETADA COMO RETIRADA PROGRAMADA.** Las cinco migraciones
fueron implementadas y validadas en
[migraciones D](MIGRACIONES_D.md), conforme a la
[decisión aprobada](DECISION_D_RETIRADA_PROGRAMADA.md). Solo quedan predictor y
reexport como excepciones hasta fase 7. E se validó posteriormente
([BLOQUE_E.md](BLOQUE_E.md)); fase 7 sigue sin iniciar. El retiro
físico sigue prohibido mientras existan esos consumidores. El bloqueo inicial y
los intentos 01/02 siguientes son historia, no el estado actual de migración.

Inicio y
validación del control: 07/11/2026, bajo autorización del usuario. Se preservan
los cambios sin commit de A/B/C. No se hace commit automático ni se modifica el
funcionamiento de aplicaciones, seed, exportador, predictor, modelos o BD.

## Qué se implementó

- `inventariar_legacy_d.py`: inventario AST de imports absolutos/relativos,
  alias, wildcard, atributos conocidos y dynamic imports literales. Inspecciona
  backend app/scripts/tests, IA app/datasets/training/management/tests y QA frontend.
  No importa/ejecuta ninguno de esos módulos.
- `legacy-d.policy.json`: lista cerrada de dependencias conocidas con motivo de
  conservación y SHA-256 normalizado LF de ambos generadores. Una dependencia
  nueva, una retirada sin revisión, una fuente ilegible, un scope faltante o un
  cambio de generador hacen fallar la comprobación.
- Distinción entre usos del generador y simples imports de `citas.public` como
  namespace/DTO. No se exige eliminar imports legítimos de workflows o servicios
  para aparentar desacoplamiento; sus 9 referencias de namespace son informativas.
- Gate manual previo al retiro: código **0** inventario válido; **2** retirada
  bloqueada conocida; **3** inventario alterado/incompleto. El código 2 no es un
  fallo inesperado. Se exige además revisión/aprobación explícita de retirada,
  aunque un inventario futuro no encuentre consumidores.
- `test_inventario_d.py`: autopruebas stdlib en árboles temporales propios.
- `validar_legacy_d.py`: evidencia nueva exclusiva, comprobación de fuentes A/B/C
  y archivos protegidos, más smoke de exportador y generador IA en procesos
  separados con imágenes previas por ID, red none, rootfs RO y scratch efímero.

Estas comprobaciones se ejecutan por comando: **no se añadió CI ni un mecanismo
que intercepte borrados del filesystem**. El scanner no es un análisis exhaustivo
de flujo dinámico: `exec`, nombres de módulos calculados, aliases que se pasan
entre funciones o consumidores fuera de los scopes requieren revisión manual.
Los runners/evidencias históricos de `docs/` se preservan y no se presentan como
consumidores operativos a retirar. Un cambio de política exige revisión, no
actualizar automáticamente la lista/hash para silenciar una alerta.

## Dependencias que impiden eliminar la copia

| Ruta | Dependencia / condición de retirada |
|---|---|
| `apps/backend/app/modules/citas/public.py` | Reexport usado por el predictor; quitarlo ahora rompe su import. |
| `apps/backend/app/modules/ia/predictor.py` | Sigue generando históricos por fallback; sustituir consumidores del motor en fase 7 con regresión/paridad. |
| `apps/backend/scripts/exportar_csv.py` | CLI activo de muestras: preservar parámetros, columnas, reproducibilidad y cuatro filas inválidas intencionales al migrarlo. No es el seed nuevo. |
| `apps/backend/tests/citas/test_citas.py` | Fixtures del generador; migrar sin borrar cobertura. |
| `apps/backend/tests/citas/test_m02_contrato.py` | Fixture de 5000 filas para contrato/rendimiento; conservar esa comprobación. |
| `apps/backend/tests/test_ia_predictor.py` | Referencia del predictor integrado; migrar con su sustitución. |
| `apps/frontend/tests/validar_diseno.py` | **Consumidor QA adicional encontrado en D**: genera CSV para validar diseño/UI/API. Migrarlo a datos explícitos sin perder esos flujos. |

El seed de C ya consume CSV explícito y no es un consumidor directo del generador.
Los otros consumidores **no se han migrado ni retirado en esta entrega**. Tampoco
se han eliminado CSV legacy, fixtures, capturas o modelos.

## Bloqueo inicial de cierre y decisión de secuencia (histórico)

No es seguro declarar D completamente cerrado como **eliminación física total**
antes de sustituir el predictor en fase 7. El plan general hace que fase 7 dependa
de fase 6; exigir además esa eliminación dentro del cierre de 6 produciría una
dependencia circular. El propio plan reserva a fase 7 retirar predictor/generador
tras migrar consumidores; no se adelanta ese trabajo ni se reduce el alcance
implícitamente.

Para resolverlo hace falta decidir explícitamente el criterio de cierre:

1. Mantener la compatibilidad temporal inventariada y aceptar en fase 6 solo la
   **retirada programada**, reservando la eliminación final a fase 7; o
2. Aprobar una secuencia revisada que permita completar primero la sustitución
   del predictor, con sus gates de integración, antes del retiro total de D.

Mientras no se acuerde ese criterio y no migren exportador/fixtures/QA, D sigue
**BLOQUEADA para retiro total**, y fase 6 **EN CURSO**. No se marca COMPLETADA
por tener un inventario verde. La fuente snapshot BD sigue deshabilitada: no
se habilita entrenamiento con BD ni se incorporan datos personales por este bloque.

## Validación y errores del inventario inicial (histórico)

Ejecución histórica: `bloque-d-20261107-01`.

- **16/16 autopruebas aprobadas**, sin errores o fallos actuales.
- Inventario válido, **7 dependencias directas conocidas**, 9 namespaces
  informativos, cero consumidores inesperados y hashes de generadores intactos.
- `--exigir-retiro` devuelve **2 esperado**: retirada no permitida.
- Smoke: muestra de 3 filas + 4 inválidas, 13 columnas. Exportador backend y
  generador canónico IA producen el mismo contenido tras normalizar CRLF/LF:
  `030259575c89a141f4ab57c6cd4c25e4cb5227a34b4827a2fe2adb7995f1e1f4`.
  Esto **no** certifica la migración del exportador ni toda la paridad histórica.
- 18 verificaciones de hashes de fuentes A/B/C aprobadas; archivos privados/modelos
  protegidos idénticos antes/después (sus datos privados no se publican).
- No se creó BD, no se inició el stack principal, no se montó código fuente de
  aplicaciones en los contenedores y no se modificaron dependencias.

**Error de implementación de pruebas, corregido:** la primera ejecución local
tuvo 5 errores `FileNotFoundError` porque el fixture temporal no creaba las
carpetas padre de `synthetic.py`. Se corrigió el fixture y se repitieron las 16
pruebas con éxito. No fue un error de la aplicación ni afectó datos existentes.
El inventario detectó además el consumidor frontend omitido en el registro previo;
se incorporó a la política y al registro, sin cambiar su código.

**Errores/bloqueos abiertos en el intento 01:** consumidores anteriores y criterio
de secuencia, posteriormente resuelto por aprobación explícita. Los consumidores
siguen pendientes. S-02 y los límites de colección empaquetada de C no se
han corregido ni reejecutado aquí. No se afirma suite backend/frontend completa
verde, cobertura nueva de aplicaciones o verificación en clon limpio.

```powershell
python -B -m unittest discover -s docs/migracion/fase-06 -p test_inventario_d.py -v
python -B docs/migracion/fase-06/inventariar_legacy_d.py
python -B docs/migracion/fase-06/inventariar_legacy_d.py --exigir-retiro
# Para otra evidencia, elegir un run-id NUEVO:
python -B docs/migracion/fase-06/validar_legacy_d.py --run-id bloque-d-20261107-01
```

[Resumen y hashes](evidencia/bloque-d-20261107-01/resumen.json). Detalle completo
local en `runtime/test-results/fase-06/bloque-d-20261107-01/`; no es un paquete
portable de evidencias. No se elimina nada al ejecutar estos comandos.

Retorno: retirar únicamente las adiciones documentales/herramientas de D, sin
descartar A/B/C. No hay cambios operativos o datos que restaurar. La fecha
provisional 20/11/2026 sigue siendo de revisión, nunca de borrado automático.

## Actualización por aprobación — ejecución 02 (07/11/2026)

Se registró la retirada programada como criterio de cierre D. La política conserva
la prohibición de eliminación física y limita la excepción a predictor/reexport.
La nueva comprobación `--exigir-cierre-programado` informa las cinco migraciones
restantes; no da por migrado el exportador ni los fixtures por editar una lista.

**19/19 autopruebas aprobadas**, 3 nuevas para separar autorización programada de
retiro físico y exigir migraciones/inventario válido. Inventario código 0; cierre
programado y retiro físico código 2 esperado. Smoke backend/IA sin cambios,
18 comprobaciones de fuentes A/B/C y protegidos intactos. Sin errores nuevos.
No se modificó código de aplicaciones ni se migraron consumidores en esta
actualización del criterio. No se arrancó BD, no se ejecutó E ni se inició 7.

```powershell
python -B docs/migracion/fase-06/inventariar_legacy_d.py --exigir-cierre-programado
# Evidencia nueva, no sobrescribir un run-id previo:
python -B docs/migracion/fase-06/validar_legacy_d.py --run-id bloque-d-20261107-02
```

[Resumen histórico D-02](evidencia/bloque-d-20261107-02/resumen.json).
En ese punto fase 6 seguía EN CURSO y D no estaba completado. Los 16 tests y el
criterio pendiente anteriores describen el intento histórico 01. El cierre
programado posterior se acredita en [MIGRACIONES_D.md](MIGRACIONES_D.md).
