# Fase 6 — pipeline explícito (COMPLETADA)

Inicio autorizado el 07/11/2026. Punto de retorno: `d6e9b1c`;
árbol inicialmente limpio. No se hacen commits automáticos.

**Estado vigente: fase 6 COMPLETADA** con los bloques A/B/C/D y el
[camino limpio E validado en aislamiento](BLOQUE_E.md). El backend sigue usando
el predictor integrado y no consume IA por HTTP: esa conexión es fase 7, que
permanece **PENDIENTE** y no se inicia por esta entrega.

## Bloque A: generación, validación y candidato offline

- Nuevo CLI `python -B -m training.cli`, ejecutado desde `apps/ia/` en su
  entorno aislado (o en la imagen IA). No requiere API-key ni servidor vivo.
- Fuente obligatoria `SINTETICO_GENERADO`, 1000 históricos, semilla 42,
  tasa 0,20, split estratificado 70/15/15; no se alteran modelos ni parámetros.
- Versión, fecha de corte, fecha de ejecución con offset y directorios explícitos.
  Las próximas operativas se solicitan explícitamente y no entran en entrenamiento.
- Salidas nuevas exclusivamente fuera del código y registry de inferencia.
  No reutiliza versiones existentes, aunque estén incompletas tras un fallo.
  En ese caso se conserva el diagnóstico y se elige una versión nueva, no se borra
  automáticamente. Las fechas diferentes deben recibir versiones diferentes.
- JSONL histórico canónico separado del CSV operacional de 13 columnas.
  Manifiesto dataset y candidato validados contra contratos v1 congelados.
  Particiones persistidas con hashes de contenido e IDs; validación previa a
  entrenar comprueba hash raw, duplicados, temporalidad, catálogos, target,
  distribución, leakage y coincidencia exacta de las particiones reproducidas.
- El candidato contiene Joblib, copia del manifiesto dataset, métricas de ambos
  modelos, equidad/importancias y manifiesto con hashes/dependencias/umbrales.
  Gate F1≥0,82 conservado: si no se alcanza, se detiene sin publicar candidato.
- No se deserializan modelos externos ni se carga el candidato en inferencia.

### Uso nativo, en entorno Python exclusivo de IA

Los directorios padre de salida deben existir. Sustituir rutas absolutas por
rutas locales aprobadas; no usar el registry activo como salida. Las fechas de
este ejemplo son de reproducción histórica, no un seed de futuras para hoy.

```powershell
# Desde apps/ia/, con sus dependencias fijadas instaladas.
python -B -m training.cli --contracts-dir "C:\proyecto\contracts" generar --version-dataset demo-20261029-v1 --semilla 42 --fecha-corte 2026-10-29 --generado-en 2026-11-07T12:00:00-05:00 --fuente SINTETICO_GENERADO --proximas 80 --directorio "C:\datos\datasets"
python -B -m training.cli --contracts-dir "C:\proyecto\contracts" validar --dataset "C:\datos\datasets\demo-20261029-v1"
python -B -m training.cli --contracts-dir "C:\proyecto\contracts" entrenar --dataset "C:\datos\datasets\demo-20261029-v1" --version-modelo candidato-demo-v1 --fecha 2026-11-07T12:00:00-05:00 --directorio "C:\datos\candidatos"
```

No ejecutar el seed automáticamente: desde C requiere CSV/hash/destino explícitos
y se usa solo en una BD nueva autorizada, no sobre el entorno existente.
El camino existente conserva datos/modelo y no requiere ninguno de estos comandos.
El camino limpio de extremo a extremo fue validado en el
[bloque E](BLOQUE_E.md), siempre en un laboratorio aislado; no se ejecutó sobre
la BD ni el compose operativos.

### Estado de los pendientes

1. Promoción/rollback: implementados en [bloque B](BLOQUE_B.md), con selección
   explícita de release/hash al reiniciar. Sin estas variables, serving conserva
   el manifiesto legacy aprobado. Validación y límites se registran en ese bloque;
   no hay promoción ni despliegue sobre el entorno existente.
2. Seed backend: implementación y pruebas aisladas en [bloque C](BLOQUE_C.md),
   con CSV/hash/destino explícitos, clave local y reconciliación sin sobrescritura.
   El resultado vigente y las limitaciones se registran en ese bloque.
3. Retirada del generador duplicado solo tras migrar todos sus consumidores
   (predictor integrado conservado hasta fase 7). [Bloque D](BLOQUE_D.md): inventario
   y gate probados; [retirada programada aprobada](DECISION_D_RETIRADA_PROGRAMADA.md).
   **D COMPLETADA como retirada programada**: [cinco consumidores migrados y
   validados](MIGRACIONES_D.md); solo quedan predictor/reexport hasta 7. E ya
   validó el camino limpio y la fase 6 quedó cerrada. El retiro físico no está
   autorizado ahora; no se eliminan generadores ni CSV legacy.
4. Snapshot backend autorizado si se habilita esa fuente: **no soportada** aquí;
   la CLI la rechaza y no hace fallback ni consulta BD.
5. Validación integrada final y camino limpio completo: **E validado**
   ([BLOQUE_E.md](BLOQUE_E.md)); fase 6 completada. La conexión backend/IA y la
   retirada del predictor integrado siguen en fase 7, no iniciada.

El control de leakage preserva separación por cita y features pre-cita; no
certifica separación por paciente ni validez clínica sobre pacientes reales.
Los resultados están rotulados como simulados. No se afinan umbrales con test.

## Validación

**Bloque A validado parcialmente en su alcance offline (07/11/2026):**
20/20 pruebas nuevas y regresión completa IA **204/204 aprobadas**, sin errores
ni omisiones; cobertura conjunta **93,18 %** (1244/1335 líneas). Generación
repetida idéntica byte a byte, split 700/150/150, entrenamiento real y gate
F1≥0,82, hashes/manifiestos y no sobrescritura comprobados. No se afirma una
medición nueva de F1 específica ni equivalencia binaria entre Joblib distintos.

Imagen ejecutada por ID
`sha256:8df350a96e09df6cd3767897334eaa3f2027989e01d953eba4838b593dcfab36`,
con fuentes empaquetadas, sin montar fuentes del host. El modelo legacy mantiene
el hash histórico `89297942f603dc040c9954d534ae6dae97590203f0345925c12fc4e0a90e9074`.
La primera invocación usó el ID config de BuildKit y no pudo arrancar contenedor;
se corrigió usando el ID de imagen local. No se cuenta ese intento como prueba.

CLI probado en subprocess (generar/validar/rechazo de sobrescritura); esas líneas
no figuran cubiertas porque no se habilitó cobertura multiproceso. Permanecen
avisos de deprecación Starlette y `cache_dir` de la configuración existente;
no se actualizaron librerías para eliminarlos.

[Resumen y hashes](evidencia/bloque-a-20261107-01/resumen.json). JUnit y cobertura
completos permanecen en runtime local, no se publica aquí un paquete portable
ni se certifica clon limpio. Backend/UI no reejecutados; no se tocó su código,
Compose, dependencias, credenciales ni base de datos.

### Bloque E — camino limpio integrado (07/11/2026)

Ejecución `e-20261107-01`: **243 fuentes** empaquetadas y reconstruidas sin
artefactos, `.joblib`, secretos ni `runtime`; imágenes IA/backend construidas
solo desde ese árbol. La imagen backend limpia no contiene modelo y la IA no
incluye SQLAlchemy. En PostgreSQL nuevo: dataset de 1000 históricas/1080 filas
de seed, dos entrenamientos con métricas y predicciones iguales, promoción,
rechazo de corrupción y rollback; serving con release/hash explícitos (lote de
60) y escenario sin modelo 503; seed 1080/2080/3 con repetición idempotente;
backend real con `/health`, login, `/citas` 1080, `/usuarios` 3, catálogos y
reportes 02/03. Gate D en 2 excepciones aprobadas, cierre programado 0 y retiro
físico no permitido. Archivos protegidos y contenedores en ejecución sin cambios.
**No** se conectó backend/IA, no se desplegó Compose y no se ejecutó navegador.
Detalle, límites y evidencia en [BLOQUE_E.md](BLOQUE_E.md).

Comandos reproducibles (PowerShell desde raíz; solo modelo confiable local en RO):

```powershell
docker build --build-context contracts=./contracts --tag predicitas-ia:fase6-a ./apps/ia
$image = docker image inspect predicitas-ia:fase6-a --format '{{.Id}}'
$modelo = (Resolve-Path artifacts/models/legacy-import).Path
docker run --rm --network none --read-only --cpus 2 --memory 1g --tmpfs /tmp:rw,size=512m --mount "type=bind,source=$modelo,target=/models,readonly" $image python -B -m pytest tests -q -p no:cacheprovider
```

La ejecución con evidencia añade un montaje de salida exclusivamente en
`runtime/test-results/fase-06/bloque-a-20261107-01/` para JUnit y cobertura.
Los candidatos y datasets de QA solo existen en el tmpfs efímero del contenedor.
No hay conexión a BD, montajes backend/frontend ni despliegue Compose.

Retorno: retirar exclusivamente las adiciones de este bloque si fuera necesario;
no restaurar BD, borrar volúmenes ni modificar modelos/credenciales existentes.
