# Fase 5 — bloque B: generador autónomo y CSV futuro

Autorizado por el usuario. Baseline/retorno `bfcad63`, árbol inicialmente limpio.
No se cambia serving, entrenamiento A, modelo, dependencias, backend/frontend,
contratos, seed ni CSV existentes. No se inicia C ni pipeline/promoción fase 6/7.

## Diseño

- `apps/ia/datasets/`: generador y derivación temporal extraídos sin algoritmo
  nuevo ni cambios en orden de PRNG, parámetros, pesos, calibración o defaults.
  Defaults legacy se preservan para paridad; para un seed válido indicar fecha,
  cantidades, semilla y **con_invalidas=False** explícitamente.
- CSV canónico UTF-8 sin BOM, LF, coma y 13 columnas del contrato. Lectura acepta
  BOM. Escritura exclusiva en ruta absoluta nueva; rechaza destino simbólico y
  rutas resueltas dentro del código IA. No crea directorios ni sobreescribe archivos.
- None -> celda vacía -> omitido al leer; backend calcula defaults/contadores.
  Target y tres variables derivadas no se exportan como autoridad: backend los
  deriva de estado/fechas. No cambiar esta política para lograr roundtrip textual.
- Mapping explícito a `training-row.v1` separa metadata/target de nueve features,
  valida acreditación sintética, coherencia temporal y corte explícito; conserva
  orden. No escribe JSONL, manifiestos ni particiones: eso sigue en fase 6.
- Lectura del CSV nuevo es una utilidad offline del formato canónico, no reemplaza
  ni endurece el parser HTTP actual. No se introducen rutas o entrenamiento HTTP.
- [Registro de copia temporal y consumidores](LEGACY_GENERADOR.md): fecha objetivo
  provisional 20/11/2026, condicionada a gates de fases 6/7, nunca borrado automático.

## Gates congelados antes de validación formal

1. Igualdad de **todos los campos y orden de filas** entre generador preservado y
   extraído en nueve escenarios: defaults, carga completa, históricos/próximas
   solos, vacío, cantidades mínimas/prefijo custom, inválidas, fecha bisiesta y
   otra semilla/tasa. Sin uso/mutación de PRNG global.
2. Contratos congelados verifican filas operacionales normalizadas y 1000 filas
   lógicas de entrenamiento. CSV roundtrip con nulos, UTF-8/BOM, comillas, comas,
   nueva línea, offsets, límites, cabecera y exclusividad; independencia de imports.
3. Nueva BD PostgreSQL limpia en red interna sin puertos host, volumen exclusivo,
   migraciones existentes, rol app limitado y backend empaquetado sin montar fuentes.
   Subir por HTTP CSV nuevo de 1000 históricas + 80 próximas: 1080 aceptadas, todos
   los campos generados iguales a filas persistidas (incluyendo derivados/target),
   historial/auditoría coherentes. Repetir CSV: 0 aceptadas / 1080 duplicadas, mismas
   citas/historial, sin adivinar una nueva política de idempotencia del endpoint.
4. CSV suplementario con cuatro filas para nulos/defaults, counters de desenlaces
   previos, BOM/Unicode/comillas/newline y fechas UTC/sin zona. Target sigue derivado
   del estado. Fallo inducido tras flush de importación no debe dejar cambios,
   comprobado desde conexiones nuevas independientes. Detener y conservar lab
   incluso ante fallo; no reusar recursos ni tocar volúmenes originales.
5. Regresión IA previa completa, paridad de inferencia 207 casos y HTTP real.
   Repetir comparación experimental de entrenamiento A. Cobertura total, offline y
   datasets ≥80 %, medidas, sin modificar scripts/source del backend.
6. Implementación registrada antes de validar, imagen nueva por ID y fuentes
   empaquetadas comprobadas. Protegidos intactos. Evidencia sanitizada separada,
   sin filas/CSV/modelos/secretos publicados, hashes del índice y clon limpio.

Las invariantes heredadas se mantienen aunque no sean un diseño ideal de pipeline;
no se acredita que la nueva generación sea el raw que entrenó el modelo legacy.
Esto prepara el CSV, pero no cambia el seed ni resuelve sus cargas parciales.

```powershell
python -B docs/migracion/fase-05/validar_ia.py ejecutar --scope B --run-id ia-bloque-b-20261106-01
python -B docs/migracion/fase-05/validar_ia.py publicar --run-id ia-bloque-b-20261106-01
python -B docs/migracion/fase-05/validar_ia.py verificar --run-id ia-bloque-b-20261106-01
```

## Resultado aceptado y reanudación

**Bloque B VALIDADO**, ejecución `ia-bloque-b-20261106-01`. Implementación
`58c9288`, runner probado `30f576b`, evidencia separada `16d663c`. Captura formal
del 07/11/2026 a las 01:16 UTC (06/11 en Lima); cierre documental del 07/11/2026.

| Gate | Resultado de la ejecución archivada |
|---|---|
| Regresión IA | **135/135** pruebas: 105 previas + 30 nuevas; tres autopruebas del runner aprobadas |
| Cobertura conjunta / entrenamiento / datasets | **97,18004338394793 % / 100 % / 98,13953488372093 %** |
| Generador preservado vs nuevo | **9 escenarios, 3450 filas**; todos los campos y orden iguales, también hashes de JSON completos |
| CSV operacional | 13 columnas, roundtrip físico y semántico mediante backend; 1000 filas lógicas de entrenamiento conformes al contrato |
| Importación CSV/ASGI + PostgreSQL nuevo | **1080 aceptadas / 0 rechazadas**, todos los campos generados, historial y auditoría comprobados |
| Repetición del mismo CSV | **0 aceptadas / 1080 duplicadas**, sin modificar citas/historial; evento IMPORT conservado según contrato actual |
| Nulos/BOM/Unicode/comillas/newline/zonas | **4 aceptadas**, defaults y contadores previos correctos, target derivado del estado |
| Rollback tras flush | Sin cambios persistidos, observado desde conexiones nuevas independientes |
| Regresión entrenamiento A / inferencia | Entrenamientos equivalentes conservados; **207 casos de inferencia idénticos**, HTTP IA real, lote de 100 en **1,032 s** |
| Aislamiento y parada | Rol app, volumen nuevo, red interna sin puertos host, backend empaquetado sin montar fuentes; parada archivada con salida 0 |

Imagen IA ejecutada por ID:
`sha256:ecbe5845ec10f4832b3a86cd0a095fd5068c57ed5b8b830bf4fcee90ee05134d`.
Serving, entrenamiento A, dependencias, modelo aprobado, backend/frontend,
contratos, credenciales y CSV existentes permanecen intactos. El seed actual
**no consume todavía** el CSV nuevo; no hubo promoción ni despliegue al principal.

El CSV se probó contra el endpoint existente mediante ASGI/TestClient con sesiones
de producción y PostgreSQL TCP. La sonda HTTP IA sí levantó un servidor dentro
del contenedor. No se presenta como E2E frontend ni prueba de carga sostenida.
Las celdas se vuelven strings/omitidos al leer; no se promete identidad de tipos
crudos antes de la normalización del backend ni recuperar target del CSV.

### Comprobaciones al reanudar (07/11/2026)

La interrupción ocurrió después de publicar evidencia, no a mitad del código.
Se revisó la implementación y se comprobó que las fuentes actuales coinciden
exactamente con las probadas, protegidos intactos, JUnit/cobertura y hashes de
logs de las acciones aprobadas, paridad de generadores y entrenamiento, hash del
CSV y registro de parada. Se repitieron las tres autopruebas stdlib del runner.

Paquetes B, A y seed verificados desde clon limpio Windows/autocrlf de `16d663c`.
Esto comprueba integridad, **no reejecuta** las 135 pruebas ni PostgreSQL. Docker
no estaba disponible durante esta reanudación; no se arrancó el daemon, se reusó
el laboratorio ni se alteraron recursos anteriores. Su estado detenido corresponde
a la ejecución archivada, no a una nueva consulta al daemon.

[Resumen sanitizado](evidencia/ia-bloque-b-20261106-01/resumen.json),
[JUnit](evidencia/ia-bloque-b-20261106-01/pytest.xml) y
[manifiesto](evidencia/ia-bloque-b-20261106-01/manifest.json).
Crudos/CSV/filas QA y volumen del laboratorio se conservan fuera del paquete público.

Entradas disponibles, sin CLI productivo ni escrituras por import:

```python
from datetime import date
from datasets.synthetic import generar_citas
from datasets.operational_csv import guardar_csv_operacional, leer_csv_operacional

# Ejemplo QA reproducible, no ejecución contra datos existentes.
filas = generar_citas(historicas=1000, proximas=80, semilla=42,
                     desde=date(2026, 11, 6), tasa_no_show=0.20, con_invalidas=False)
ruta = guardar_csv_operacional(filas, ruta_nueva=destino_csv_absoluto_nuevo)
filas_csv = leer_csv_operacional(ruta)
```

**Fase 5 continúa EN CURSO:** queda C (timeout/cómputo y concurrencia). La retirada
efectiva de la copia legacy y el consumo del CSV por el seed requieren los gates
de fases 6/7 del registro temporal; no se ejecutan por cerrar B. S-02 backend y
frontend no revalidados por esta entrega.
