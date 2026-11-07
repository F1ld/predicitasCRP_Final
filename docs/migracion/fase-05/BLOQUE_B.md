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
  BOM. Escritura exclusiva en ruta absoluta nueva, fuera del código IA, sin
  seguir enlaces simbólicos; no crea directorios ni sobreescribe archivos.
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

Estado: implementación en revisión, todavía no validada formalmente. Fase 5 EN CURSO.
