# Registro de compatibilidad temporal del generador backend

Designación temporal: **06/11/2026**, bloque B de fase 5. No se modifica código
backend para poner esta marca: el registro externo preserva los hashes aceptados
de fuente y comportamiento. La reexportación pública ya estaba marcada temporal.

Canónico nuevo: `apps/ia/datasets/synthetic.py`. Copia legacy conservada:
`apps/backend/app/modules/citas/synthetic.py`. No es una segunda implementación
permanente ni permiso para introducir divergencias matemáticas.

| Consumidor actual | Motivo de conservación / retirada |
|---|---|
| `apps/backend/scripts/seed.py` | Sigue usando generador legacy. Fase 6 debe cambiarlo a CSV operacional explícito y probar idempotencia/cargas parciales antes de retirar el import. |
| `apps/backend/scripts/exportar_csv.py` | Muestra operacional con cuatro inválidas intencionales; no es seed ni dataset IA. Migración de consumidor requiere preservar ese contrato. |
| `apps/backend/app/modules/citas/public.py` | Reexport temporal, retirarlo solo cuando no queden consumidores. |
| `apps/backend/app/modules/ia/predictor.py` | Generación histórica por fallback del predictor integrado. Se conserva hasta la sustitución de consumidores de IA de fase 7; no introducir fallback en el servicio nuevo. |
| Tests backend de Citas/predictor | Migrarlos junto a sus consumidores; no eliminarlos para aparentar encapsulación. |
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
