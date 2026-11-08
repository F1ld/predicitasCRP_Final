# Migraciones de consumidores D — completadas y validadas

Autorización: el usuario indicó «Procede con las migraciones», después de aprobar
el cierre de D como retirada programada. No se inicia E ni fase 7 por esta entrega.
Se preservan cambios A/B/C, la BD principal, el modelo activo y las dependencias.

## Implementación

### Exportador

La generación del CLI se trasladó a `apps/ia/datasets/exportar_csv.py` y utiliza
exclusivamente el generador canónico. Conserva `--filas`, `--semilla`,
`--fecha-referencia`, `--salida`, CSV UTF-8 de 13 columnas y cuatro filas inválidas
intencionales. Conserva destinos nuevos exclusivos y guardas de directorio.

```powershell
# Desde apps/ia/, en el entorno exclusivo de IA:
python -B -m datasets.exportar_csv --filas 20 --semilla 7 --fecha-referencia 2026-11-05 --salida "C:\datos\muestra-nueva.csv"
```

El comando backend **ya no genera**. Se mantiene como adaptador para exportar
muestras previamente preparadas con manifiesto y parámetros coincidentes:

```powershell
# Desde apps/backend/, en su entorno exclusivo:
python -B -m scripts.exportar_csv --fuente "C:\datos\bundle-qa" --filas 3 --semilla 7 --fecha-referencia 2026-11-05 --salida "C:\datos\copia-nueva.csv"
```

`--fuente` también puede establecerse como `PREDICITAS_EXPORT_FIXTURES_DIR`.
Si falta la fuente o no coinciden fecha/semilla/cantidad, se detiene sin escribir;
no importa IA, invoca Docker ni ejecuta un generador por fallback. **Cambio
explícito de invocación offline:** para generación arbitraria se usa ahora el
entorno IA; no se conserva la generación implícita del antiguo CLI backend.
Las rutas HTTP y el funcionamiento del servidor backend no cambian.

### Fixtures y pruebas

- `datasets.qa_bundle` materializa escenarios reproducibles, con parámetros/fecha
  congelados y SHA-256. Cada destino debe ser un directorio absoluto nuevo fuera
  del código IA. No se ejecuta en startup ni en inferencia.
- Backend consume seis CSV versionados en `tests/fixtures/generados-v1/`:
  importación mixta **40 válidas + 4 inválidas**, rendimiento **5000** históricos,
  coherencia de **1000 históricos + 80 próximos** y tres muestras del exportador.
- Se conservaron los asserts de importación, rechazos, coherencia, F1 y
  explicabilidad, y el test de listado **≤3 s con 5000 citas**. El test antes
  llamado `test_generador_1000_historicas_y_80_proximas_coherentes` se llama ahora
  `test_fixture_1000_historicas_y_80_proximas_coherentes`: comprueba datos explícitos.
  La generación canónica continúa probada en IA, además de la paridad por escenario.
- Los CSV no incluyen features derivadas ni target. En la comprobación de
  coherencia, backend los deriva con su normalizador/reglas existentes, sin
  importar código IA. No se copia otra implementación matemática.
- Frontend QA consume tres CSV: **45+4**, **20+4 API**, **20+4 navegador**.
  Solo reasigna prefijos de IDs para aislar cada ejecución; no genera fechas,
  estados, especialidades o historiales. Se conservan las comprobaciones previas
  del runner y la transacción externa con rollback.
- `PREDICITAS_QA_FIXTURES_DIR` permite otro bundle absoluto explícito; por defecto
  se leen los fixtures versionados de QA. Importar el runner no lee datos, cambia
  CWD/sys.path ni conecta a BD. Primero se confirma la BD de pruebas; después se
  valida la entrada antes de crear resultados o abrir la conexión transaccional.

`scripts.csv_preparado` valida versión/rotulado sintético, escenario, SHA-256,
cantidad, cabecera, 2 MiB/5000 filas y rutas sin enlaces directos. No deserializa
modelos ni ejecuta código contenido en archivos. Los manifiestos son metadatos
versionados de QA, no firmas ni autorización para datos personales.

### Reproducción de los datos

```powershell
# En el entorno IA; directorio padre existente, destino NUEVO:
python -B -m datasets.qa_bundle --salida "C:\datos\bundle-qa-nuevo"
```

Los nueve escenarios tienen fechas de referencia históricas explícitas, no la
fecha actual del equipo; no usar esos fixtures como una nueva BD operacional.
La partición de rendimiento de 5000 filas **no cambia** el entrenamiento oficial
de 1000 históricos/semilla 42/split 70/15/15.

Los CSV usan CRLF como fija `.gitattributes`, y manifiesto con hashes de bytes;
no editar/reformatear los CSV a mano. La materialización se hizo en un proceso IA
aislado y se copiaron solo salidas sintéticas verificadas a carpetas nuevas de
tests; no se sobrescribieron fixtures anteriores ni CSV legacy.

## Excepción temporal

Se actualizaron las cinco entradas de la política tras migrar sus imports. Solo
quedan predictor integrado y reexport `citas.public`, según aprobación del usuario.
La guarda de cierre programado debe quedar en 0; la de retirada física sigue en 2.
No se elimina la copia legacy ni se cambia el predictor en esta entrega.

## Validación prevista y límites

`validar_migraciones_d.py` compara los nueve CSV **byte por byte** contra el
generador backend de la imagen preservada C y contra el canónico IA. Después
ejecuta regresiones IA/backend, seed C y pruebas del exportador. Recupera la
profundidad monorepo únicamente en tmpfs para ejecutar pruebas de archivos sin
montar el backend del host.

La sonda QA usa payloads del runner frontend migrado con ASGI/backend real y
PostgreSQL nuevo. Comprueba 45/4 y dos importaciones 20/4, repetición 0/24 y
rollback desde otra conexión. **No equivale a ejecutar navegador ni validar
visualmente toda la UI**. No se conecta al stack principal.

## Resultado aceptado — D completada como retirada programada

Ejecución vigente `migraciones-d-20261107-02` (07/11/2026 Lima; logs UTC del 08/11):

- **241/241 pruebas IA**, cobertura app/training/datasets/management **90,12 %**.
- **339/339 pruebas backend empaquetadas**, incluidas 9 nuevas de migración y
  las 21 de seed C. Cobertura app+seed **88,40 %**, superior al umbral vigente 75 %.
- **33/33 pruebas adicionales de archivos/CLI y guardas QA**, con geometría
  monorepo reconstruida desde imagen en tmpfs, salvo el test de invariantes
  históricos de datos (no ejecutado en esa reconstrucción).
- **19/19 autopruebas stdlib de inventario** aprobadas.
- Los **9 CSV / 6241 filas QA / 941885 bytes** coinciden byte por byte con la
  proyección operacional del generador backend preservado y el canónico IA.
  Se conserva íntegro el escenario de rendimiento de 5000 citas y su test ≤3 s.
- Sonda QA: **45 aceptadas/4 rechazadas**, API y archivo destinado a navegador
  **20/4 cada uno**, repetición **0/24**, sin cambios visibles tras rollback
  desde conexión independiente. No se ejecutó navegador ni servidor QA persistente.
- Revalidación de seed C: 1080 citas iniciales, rerun sin cambios en todas las
  tablas, reconciliación explícita, rechazo de conflictos/segundo seed y rollback
  tras flush aprobados en PostgreSQL nuevo.
- Inventario: **solo las dos excepciones aprobadas**, cero migraciones pendientes;
  cierre programado código **0**. Retiro físico sigue prohibido (código 2).

Imágenes ejecutadas por ID: backend
`sha256:e86f96ad2844531222bd865b749860bd47400f009e28076122bb9cc649f8bffa`,
IA `sha256:758c037a41c7b09e462244c0a3763b2860f13e9c717581993b47b4d9d9881504`.
Backend sin fuentes montadas del host; solo scripts/fixtures QA RO. CSV de
aplicaciones, modelos y archivos privados preservados; 18 comprobaciones A/B/C
intactas. Los dos laboratorios nuevos quedaron detenidos, sin tocar principal.

**Error encontrado y corregido:** el intento 01 pasó IA/backend/paridad pero la
sonda QA falló con `IndexError` porque el montaje `/qa` era demasiado superficial
para `rutas_validacion.py`. Se corrigió la geometría del runner y se repitió todo
en un laboratorio nuevo (02). No se modificaron reglas para hacer pasar pruebas.

La colección completa backend conserva S-02 y el verificador de evidencia
dependiente de monorepo. No se declara suite completa verde. Los 339 casos y los
33 adicionales tienen scopes explícitos; los 21 focales C ya están incluidos en
339, no se suman otra vez. La menor cobertura backend respecto a C refleja que
las pruebas dejaron de ejecutar el generador legacy; la generación se prueba
en IA y por paridad independiente. La cobertura no agrega subprocess ni mide
los nuevos scripts backend de lectura/exportación con el scope app+seed.

No hay error de migración abierto para el alcance D aprobado. Se registra D
**COMPLETADA COMO RETIRADA PROGRAMADA**, no eliminación física. **E sigue
PENDIENTE, fase 6 EN CURSO y fase 7 PENDIENTE**. No se hizo commit automático,
verificación en clon limpio ni paquete completo portable de evidencias.

[Resumen vigente y hashes locales](evidencia/migraciones-d-20261107-02/resumen.json),
[índice de fuentes/fixtures](evidencia/migraciones-d-20261107-02/fuentes.json).
Los resultados completos permanecen en runtime local y en su sublaboratorio.

```powershell
# Los IDs deben ser NUEVOS para otra ejecución; bundle preparado previamente.
python -B docs/migracion/fase-06/validar_migraciones_d.py --run-id migraciones-d-20261107-02 --ia-image sha256:758c037a41c7b09e462244c0a3763b2860f13e9c717581993b47b4d9d9881504 --bundle runtime/test-results/fase-06/d-migraciones-20261107-01/bundle
```

Retorno: recuperar solo los cambios de estos consumidores y las nuevas
herramientas/fixtures de D, sin descartar A/B/C. No restaurar BD ni borrar datos.
