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

Estado: implementación en revisión, sin aceptación formal todavía. Fase 5 EN CURSO.
