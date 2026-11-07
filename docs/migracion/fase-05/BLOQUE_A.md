# Fase 5 — bloque A: extracción offline de entrenamiento y evaluación

Autorizado por el usuario. Baseline/retorno `3e561b2`, árbol inicialmente limpio.
Solo bloque A: no se extrae generador/CSV (B), no se cambia concurrencia/timeout
de inferencia (C), ni se inicia pipeline/promoción de fase 6 o conexión fase 7.

## Diseño y límites

- `apps/ia/training/`: preprocesado, particiones/controles, métricas/equidad,
  entrenamiento en memoria y serialización explícita de candidatos separados.
- Extracción del predictor preservado. Mismos algoritmos e hiperparámetros,
  categorías, orden de features, semilla 42, split estratificado 70/15/15, métricas,
  equidad/importancias y gate F1≥0.82. Evaluación usa `>= 0.450`, clasificación
  de riesgo usa `> 0.450`; se preserva esta distinción histórica.
- Entrenamiento requiere registros explícitos, versión de candidato/dataset y
  fecha con zona horaria. No BD, generador por fallback, import de backend, ruta
  activa por defecto, escritura implícita o modificación del registry de serving.
- Se rechaza reutilizar la versión activa legacy. Serialización solo a directorio
  nuevo solicitado expresamente, archivo exclusivo `candidate.joblib`, fuera del
  registry configurado. No hay CLI productivo ni manifiesto de promoción.
- El backend conserva su copia integrada hasta retirar sus consumidores. No se
  modifica su fuente ni su comportamiento de fallback durante esta entrega.
- Se reutiliza layout/catálogos de features del código IA común, pero serving no
  importa entrenamiento/evaluación offline. La normalización legacy offline se
  preserva separada de la validación estricta HTTP, sin endurecerla silenciosamente.

## Gates congelados antes de validación formal

1. Backend/frontend/contratos, serving IA (`app/` y manifiesto aprobado), modelos,
   CSV y dependencias no modificados. Registro de implementación antes de validar.
2. Pruebas de split, preprocesado, parámetros, métricas (incluido borde exacto),
   equidad, controles anti-leakage, F1 insuficiente y serialización exclusiva.
   Prueba real de entrenamiento en memoria con fixture sintética exclusiva de QA.
3. Procesos frescos prueban: importar offline no carga/entrena/escribe modelos ni
   exige clave; arrancar serving no importa offline, llama `fit` ni `joblib.dump`.
4. Comparación experimental adicional: fixture temporal de 1000 históricas creada
   por el generador legacy preservado **solo para QA**, no extraído en A. Ejecutar
   entrenamiento original y extraído en contenedores independientes sin red,
   filesystem RO y scratch `/tmp` nuevo. Ambos reciben exactamente los mismos
   registros y reloj. No tocar modelo activo ni guardar/promover candidatos en host.
5. Exigir igualdad de normalización/matriz, índices de split, preprocesadores
   ajustados, parámetros, probabilidades crudas de ambos estimadores sobre las
   1000 filas, métricas, equidad, importancia y metadata. Únicas diferencias de
   identidad previstas: versión modelo y dataset QA (no reutilizar versión activa).
   Serializar/releer candidatos temporales sin alterar predicciones ni el activo.
6. Regresión previa completa IA, cobertura total ≥80 % y cobertura offline ≥80 %
   medidas de JSON, además de paridad de inferencia 207 casos y sonda HTTP real.
7. Nueva imagen por ID, fuentes empaquetadas comprobadas incluyendo `training/`,
   resultados exclusivos y sanitizados; publicar separado y verificar clon limpio.

No se compara hash binario entre candidatos (identidades distintas); sí se exige
igualdad exacta de resultados numéricos y estadísticas aprendidas. Los modelos de
prueba se crean y eliminan solo en scratch del contenedor; input/logs/reportes QA
e imagen permanecen en runtime para trazabilidad, sin publicar filas o Joblib.
Los controles anti-leakage conservan su alcance legacy; esto no diseña nuevos
controles, particiones por paciente ni un pipeline de calidad de fase 6.

## Ejecución prevista

```powershell
python -B docs/migracion/fase-05/validar_ia.py ejecutar --scope A --run-id ia-bloque-a-20261106-01
python -B docs/migracion/fase-05/validar_ia.py publicar --run-id ia-bloque-a-20261106-01
python -B docs/migracion/fase-05/validar_ia.py verificar --run-id ia-bloque-a-20261106-01
```

## Resultado aceptado

**Bloque A VALIDADO**, ejecución `ia-bloque-a-20261106-01` (06/11/2026).
Implementación `83a96a6`, runner probado `22c6788`, evidencia separada `9f6636b`.

- **105/105 pruebas**: 83 previas conservadas y 22 nuevas; cobertura conjunta
  **96,88826025459689 %**, offline **100 %** (líneas, no certificación universal).
  Tres autopruebas stdlib del runner también aprobadas.
- Entrenamiento real de referencia y extraído: **700/150/150** con mismos índices,
  mismas estadísticas/preprocesado, hiperparámetros y probabilidades crudas de
  ambos estimadores sobre las **1000 filas**. Metadata, métricas, auditoría de
  equidad e importancias iguales salvo las identidades QA previstas.
- F1 LightGBM **0,8621**, baseline **0,7451**, iguales a la referencia. No se
  reentrenó ni promocionó el artefacto activo: ambos candidatos existieron solo
  en scratch, con roundtrip de serialización aprobado y registry intacto.
- Regresión serving: **207 casos diferenciales** idénticos, HTTP real con lote
  máximo de 100 en **0,947 s**, sin cargar entrenamiento desde el servicio.
- Nueva imagen ejecutada por ID:
  `sha256:93b75b1f7d095dbdeb3c5d478cdf209026fb7ea6faf4822f834a0612fe329892`.
  Red none, 2 CPU/1 GiB, UID 1000, filesystem/modelo RO; no BD ni fuentes backend.
- Código serving, manifiesto aprobado, dependencias, backend/frontend/contratos,
  modelos y CSV intactos. Fuentes empaquetadas comprobadas y hashes del índice Git
  verificados. Paquete A y corrección anterior verifican desde clon limpio Windows
  con autocrlf de `9f6636b`; eso no reejecuta tests ni incorpora modelos privados.
- Ningún contenedor de validación queda ejecutándose; recursos/evidencias previas
  conservados, servicio ajeno intacto. No hubo despliegue al principal.

[Resumen sanitizado](evidencia/ia-bloque-a-20261106-01/resumen.json),
[JUnit](evidencia/ia-bloque-a-20261106-01/pytest.xml) y
[manifiesto](evidencia/ia-bloque-a-20261106-01/manifest.json).

Entradas offline disponibles (no son un pipeline productivo):

```python
from training.trainer import entrenar
from training.serialization import guardar_candidato

# Registros, identidades y fecha con zona deben ser proporcionados explícitamente.
resultado = entrenar(registros, version_modelo=version_candidato,
                    version_dataset=version_dataset, fecha_entrenamiento=fecha)
# Opcional; el padre ya existe y el destino debe ser NUEVO y fuera del registry.
ruta = guardar_candidato(resultado, directorio_nuevo=destino_nuevo)
```

**Fase 5 sigue EN CURSO**: faltan B (generador/datasets/CSV/retirada temporal) y C
(timeout/concurrencia de inferencia). No se iniciaron por esta entrega ni se
marcó completo el ítem combinado de entrenamiento/datasets del plan. S-02 backend
y frontend no revalidados; el alcance probado es IA aislada y extracción A.
