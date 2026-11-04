# Contratos de datos v1 — especificación, no migración aplicada

## CSV operacional: conservar lo que valida hoy el backend

Referencia ejecutable actual: `app/modules/citas/router.py`, `schemas.CitaImportIn`, `importer.validar_fila` y `reglas.derivar_variables` del backend. El schema `cita-import-normalizada.v1.schema.json` representa **la fila después de convertir tipos, quitar espacios, normalizar catálogos y asignar zona**, no los bytes de un CSV ni un nuevo validador obligatorio de producción.

Cabecera canónica para ejemplos/exportador:

```text
id_cita_externa,paciente_anon_id,sede,especialidad,medico,fecha_hora_cita,fecha_registro_cita,tipo_paciente,canal_origen,inasistencias_previas,reprogramaciones_prev,asistencias_previas,estado_actual
```

- Son 13 columnas canónicas; **no afirmar que las 13 son obligatorias hoy**. Los nueve datos básicos sí son requeridos por CitaImportIn; inasistencias/asistencias permiten omitido/null, reprogramaciones usa 0 y estado usa RECIBIDA por defecto.
- Las celdas vacías se omiten antes de Pydantic; contadores omitidos se calculan desde desenlaces previos a fecha de registro. El schema `default` documenta, no inserta valores por sí mismo.
- Strings de catálogo se normalizan a mayúsculas; sede única, tres especialidades, estados importables sin LIBERADA. Columnas extra se ignoran; una columna target no establece el desenlace ni entra en X.
- Fechas sin zona se interpretan en Lima en la implementación actual. El formato normalizado es ISO 8601 con offset. Días y franja en Lima, MANANA si hora `<13`, TARDE en otro caso.
- UTF-8 con BOM opcional, coma, máximo 2 MiB/5.000 filas. `fila` en rechazos empieza en 1 para primera fila de datos, no número físico de línea incluyendo cabecera.
- Duplicados existentes o dentro del archivo se rechazan; validación parcial antes de insertar válidas. No se garantiza tolerancia a cualquier fallo SQL por fila; persistencia/historial/auditoría son transaccionales.
- ATENDIDA→target 0 y NO_SHOW→1; estados sin desenlace→null. No aceptar desenlace en fecha futura del calendario Lima. No tratar CANCELADA como target 1.

**Diferencia temporal registrada:** hoy se compara fecha calendario de registro/cita para antelación; registro a las 10:00 y cita a las 09:00 del mismo día no se rechaza por esa comprobación. Se incluye fixture de compatibilidad. La intención de «registro anterior» más estricta requiere una corrección separada; no introducirla en fase 2.

Ejemplos `../examples/importacion_valida.csv`: dos filas aceptables; el segundo usa minúsculas que el parser normaliza. `importacion_mixta.csv`: una válida, una duplicada, una domingo y una desenlace futuro. Referencia fija **2026-11-03 08:00 Lima**, IDs inexistentes en BD de prueba: esperado 1 aceptación y 3 rechazos. No importarlos al principal para probarlos.

## Features y dataset IA

`features.v1.schema.json`: objeto canónico de nueve entradas obligatorias no nulas. No acepta extras, etiquetas, estados, identificadores o diagnósticos. Los contadores omitidos del CSV se resuelven en backend antes de llamar IA; no enviarlos como null.

| Campo | Dominio |
|---|---|
| especialidad | CARDIOLOGIA / TRAUMATOLOGIA / PEDIATRIA |
| tipo_paciente | NUEVO / CONTINUADOR |
| canal_origen | WEB / CALL_CENTER / PRESENCIAL |
| franja_horaria | MANANA / TARDE |
| dia_semana | LUNES..SABADO |
| antelacion_dias | Entero ≥0 |
| inasistencias_previas, asistencias_previas, reprogramaciones_prev | Enteros ≥0; bool/string no son enteros canónicos |

`snapshot-features.v1.schema.json` añade:

- `tasa_no_show_previa = round(inasistencias / (asistencias + inasistencias + 1.0), 4)`.
- `es_reserva_lejana = 1 si antelacion_dias >=15, en otro caso 0`.

Preservar orden del pipeline actual: antelacion, inasistencias, asistencias, reprogramaciones, tasa previa, reserva lejana, especialidad, tipo, canal, franja, día. El orden JSON no es un contrato de columnas: el pipeline selecciona nombres explícitos. No reentrenar por reorganizar el objeto.

`training-row.v1.schema.json` es formato lógico objetivo, no CSV operacional: metadata/fechas/target fuera de `features`. Exportador fase 6 adapta el formato plano actual al formato de entrenamiento o publica su mapping explícito. Solo históricos cerrados, etiquetas coherentes y seudónimos sintéticos. Validación semántica exige fecha registro ≤ cita ≤ corte, antelación/franja/día consistentes y NUEVO sin historial en dataset sintético acreditado. Esta regla de acreditación no endurece silenciosamente CitaImportIn.

## Manifiestos y procedencia

`dataset-manifest.v1.schema.json` contiene versión de features/dataset, semilla 42, corte/generación, clases, particiones, hashes y resultado de controles. **No basta con declarar `sin_interseccion_ids=true`: fase 6 debe comprobar archivos/IDs reales.** El validador de contratos comprueba coherencia de metadatos y fixtures, no prueba existencia de datasets.

- `TRAINING_RUN`: linaje completo, raw/splits/IDs con hashes reales, fuente sintética explícita y split reproducible estratificado 70/15/15. Para N=1.000: 700/150/150. Las clases y particiones deben sumar total; no-show de splits suma no-show global.
- `LEGACY_IMPORT`: solo metadata recuperada del artefacto existente, `linaje_completo=false`, fuente `LEGACY_METADATA_ONLY`, hashes raw/splits/IDs **null**, nunca inventados. Fecha de corte **null** si no se recuperó evidencia; no inferirla del default actual del generador. Los controles antiguos se identifican como declarados por el artefacto, no revalidados con archivos ausentes. Solo uso simulado tras aprobación específica de fase 6. `TRAINING_RUN` sí exige corte conocido y hashes reales.
- `CONTRACT_FIXTURE`: ejemplo estructural/semántico hipotético, no entrenamiento probado. Hashes repetidos en ejemplos no acreditan archivos; los modelos fixture siempre CANDIDATO.

Los manifiestos de modelo y dataset se enlazan por versión y hash del archivo de manifiesto real. Un legacy puede conservar bytes/version del modelo y a la vez declarar honradamente el linaje faltante; no obliga a reemplazar pesos sin autorización. Ninguna de estas rutas/promociones se ejecuta en fase 1.

## Formatos físicos elegidos para las fases 3 y 6

| Archivo objetivo | Formato/propósito |
|---|---|
| `data/samples/importacion/*.csv` | Muestras operativas pequeñas versionadas; cabecera canónica de 13 columnas |
| `data/raw/<version_dataset>/historicas.jsonl` | Una fila por línea conforme a training-row, metadata/target separados de features; solo históricos |
| `data/raw/<version_dataset>/seed_operacional.csv` | Entrada demo explícita al backend, históricos y próximas según flags; sin target autoritativo |
| `data/processed/<version_dataset>/train.jsonl`, `val.jsonl`, `test.jsonl` | Filas normalizadas con mismo contrato; particiones congeladas, no columnas one-hot serializadas como fuente independiente |
| `data/processed/<version_dataset>/train.ids.json`, `val.ids.json`, `test.ids.json` | Listas ordenadas de IDs para demostrar split/intersección; metadata, no features |
| `data/manifests/<version_dataset>.json` | Manifiesto dataset v1 y hashes de bytes reales cuando disponibles |
| `artifacts/models/<version_modelo>/modelo.joblib` | Pipeline confiable completo, preprocesado incluido |
| `artifacts/models/<version_modelo>/manifest.json`, `metrics.json` | Contrato de manifiesto y reporte compatible con MetricasModeloOut; sin regenerar métricas al servir |
| `artifacts/models/active.json` | Puntero activo atómico conforme a active-model v1 |

JSONL nuevo se escribe UTF-8 sin BOM, LF y una nueva línea final; JSON canónico por fila con claves ordenadas, sin NaN/Infinity. **No reordenar las filas por comodidad:** preservar orden de entrada acreditado y registrar sus bytes/IDs, porque un cambio de orden puede cambiar el split con la misma semilla. Loader de entrenamiento toma solo `row.features` para X y `target_no_show` para y, con columnas seleccionadas por nombre y orden del pipeline; metadata nunca entra en X.

No crear Parquet/Excel como otra fuente canónica en esta migración. Si se conserva un CSV exportado original, mantenerlo inmutable con procedencia y convertir explícitamente a JSONL; no renombrar extensión. Versiones usadas en paths se validan como nombres seguros y se resuelven confinadas al directorio configurado; nunca concatenar entradas arbitrarias a rutas.

Un legacy sin archivos originales solo crea manifiesto de metadata con corte/hashes desconocidos nulos y reportes recuperados; **no** crear un `historicas.jsonl` ficticio afirmando que entrenó ese modelo. Candidatos se preparan en staging separado del registry activo; promoción mueve una versión completa y luego sustituye el puntero, preservando versión anterior.
