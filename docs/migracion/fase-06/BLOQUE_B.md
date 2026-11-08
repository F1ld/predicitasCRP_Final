# Fase 6 — bloque B: releases aprobadas y rollback

Implementación autorizada por el usuario. Se preserva el bloque A sin commit;
baseline Git `d6e9b1c`. No se promueve ningún modelo del host ni se modifica
Compose, el backend, frontend, seed, credenciales o BD. Pruebas solo en tmpfs.

## Diseño y frontera de confianza

- Registry **administrativo local** con `releases/<version>/` inmutables,
  `state.json` con activo/anterior y `.writer.lock` de escritor exclusivo.
- Promoción requiere aprobación explícita de versión y SHA-256 del manifiesto
  candidato, obtenido por el operador desde su pipeline interno confiable.
  El hash no es firma ni vuelve seguro un pickle de origen desconocido.
  No hay endpoint de upload/promoción ni datos/modelos recibidos de usuarios.
- Antes de `joblib.load`: contrato del manifiesto, hash del modelo/dataset/métricas,
  dependencias exactas, identidad dataset, métricas y gate F1≥0,82. Se lee una sola
  copia de los bytes a deserializar. Se preserva el manifiesto candidato original.
- La aprobación instalada fija hash, dataset, compatibilidad, versión de features
  y un smoke con probabilidad/nivel/explicación. La carga existente vuelve a
  comprobar pipeline, categorías, features, umbrales, conteos y smoke antes de ready.
- `/v1/dataset` admite la variante `TRAINING_RUN` ya prevista en el contrato v1,
  además de la variante legacy; no se etiqueta un dataset nuevo como legacy para
  eludir validación. Las rutas, autenticación y contratos backend no cambian.
- Se escribe en staging exclusivo; se comprueba la release completa con el mismo
  cargador serving, se renombra y **solo entonces** se reemplaza `state.json`
  atómicamente en el mismo filesystem. No hay symlinks para activo/anterior.
- Rollback comprueba la versión anterior antes de intercambiar las referencias;
  todos los modelos anteriores siguen conservados, sin sobreescritura.
  También permite seleccionar una versión instalada (incluido legacy) con su hash
  de aprobación explícito, sin instalarla otra vez ni reutilizar su nombre.
- `--esperado` protege frente a un cambio concurrente del activo; el lock rechaza
  otro escritor. Un lock anterior no se borra automáticamente. Si el proceso muere,
  su revisión/retirada requiere intervención del operador.

No se promete durabilidad ante corte eléctrico en todos los filesystems: se hace
flush/fsync de archivos y rename/replace local, no una transacción distribuida ni
garantía de directorios en discos remotos/OneDrive. Preferir un registry local
fuera de OneDrive y montar su directorio padre, no un archivo individual.

## Serving y reinicio controlado

**Sin variables nuevas, el arranque legacy queda igual.** La selección de una
release requiere ambas variables explícitas al reiniciar:

- `MODEL_REGISTRY_DIR`: raíz administrada montada RO en inferencia.
- `IA_RELEASE_VERSION`: versión tomada de `state.json.active.release`.
- `IA_APPROVAL_SHA256`: hash tomado de `state.json.active.approval_sha256`.

La versión/hash se fijan al arrancar y se transmiten al worker aislado sin API-key
ni secretos. Cambiar `state.json` **no recarga** el proceso vivo. Incluso un worker
que se reinicie sigue usando esa selección; no lee un activo nuevo a mitad de lote.
No hay fallback silencioso al legacy si falla el modelo/hash seleccionado.

Procedimiento: detener el servicio IA de destino, promover/rollback offline,
leer el nuevo estado, configurar ambos valores y arrancar; verificar ready y
predicción. En una instalación existente **no ejecutar** sin autorización de
despliegue. El bloque B se comprueba solo en un registry aislado.

El legacy puede importarse al registry nuevo con su aprobación incluida en el
software (hash histórico obligatorio), conservando `LEGACY_IMPORT` y linaje
incompleto honesto; no se inventa un dataset reproducible para ese modelo.

## Comandos (entorno Python exclusivo de IA)

Desde `apps/ia/`; directorio padre del registry nuevo ya existente. Ejemplos con
rutas ficticias: no ejecutarlos sobre el registry del entorno demo.

```powershell
python -B -m management.cli importar-legacy --registry "C:\datos\registry-aislado" --modelo "C:\datos\legacy\modelo_predicitas_v1.joblib" --esperado VACIO
python -B -m management.cli promover --registry "C:\datos\registry-aislado" --candidato "C:\datos\candidatos\candidato-demo-v1" --manifest-sha256 <HASH_INTERNO_APROBADO> --aprobar-version candidato-demo-v1 --esperado legacy-v1 --contracts-dir "C:\proyecto\contracts"
python -B -m management.cli estado --registry "C:\datos\registry-aislado"
python -B -m management.cli rollback --registry "C:\datos\registry-aislado" --esperado candidato-demo-v1
# Alternativa: volver directamente a un legacy instalado, con su hash aprobado.
python -B -m management.cli rollback --registry "C:\datos\registry-aislado" --esperado candidato-demo-v1 --a-version legacy-v1 --approval-sha256 <HASH_APROBACION_LEGACY>
```

Si falla antes del replace, el estado previo permanece; una release o staging
huérfano puede conservarse para diagnóstico. No se borra automáticamente y no se
reutiliza su nombre. Tras una interrupción alrededor del replace, consultar
`estado` y validar su release antes de reintentar: no asumir que no hubo éxito.
Copiar/guardar modelos, dataset raw o secretos nunca forma parte de la evidencia
pública. Solo el proceso administrativo puede escribir; inferencia recibe RO.

## Gates de validación

1. Modelo legacy del host con el mismo SHA-256; sin nuevos consumidores backend.
2. Candidato real → release temporal: mismas predicciones, niveles, snapshots y
   explicaciones; manifiesto dataset conserva linaje completo.
3. Importar legacy → promover → rollback → volver al candidato sin borrar bytes.
4. Hash alterado, dependencia/feature/umbral/versión incompatible, F1 insuficiente,
   versión duplicada, activo inesperado y segundo escritor rechazados.
5. Fallo en replace y rollback a modelo corrupto no cambian el estado activo.
6. Arranque nuevo con versión/hash fijos y predicción mediante worker real; hash
   equivocado no carga ni recurre al legacy. Sin entrenamiento desde serving.
7. Regresión IA completa y cobertura medida, imagen nueva por ID, salida aislada.

Reproducción desde raíz (PowerShell):

```powershell
docker build --build-context contracts=./contracts --tag predicitas-ia:fase6-b ./apps/ia
$image = docker image inspect predicitas-ia:fase6-b --format '{{.Id}}'
$modelo = (Resolve-Path artifacts/models/legacy-import).Path
docker run --rm --network none --read-only --cpus 2 --memory 1g --tmpfs /tmp:rw,size=512m --mount "type=bind,source=$modelo,target=/models,readonly" $image python -B -m pytest tests -q -p no:cacheprovider
```

La ejecución archivada añade montaje de salida exclusivo para JUnit/cobertura en
`runtime/test-results/fase-06/`. Los registries y candidatos de QA quedan solo
en `/tmp` efímero. No se importó legacy a ningún registry persistente del host.

## Resultado (07/11/2026)

**Bloque B implementado y validado en aislamiento.** Ejecución vigente
`bloque-b-20261107-03`: **228/228 pruebas**, 24 nuevas respecto de A; cobertura
conjunta **92,85 %** (1467/1580 líneas). Imagen ejecutada por ID
`sha256:41ca225ddcb1a930e5232e747d6e5e2527f605f3f8154c1611e201dff03ead73`.

- Candidato real, 25 comparaciones con igualdad en probabilidad/nivel/snapshot/
  explicación; importación legacy y rollback sin modificar el modelo del host.
- Arranque ASGI y predicción con worker real sobre release fijada; metadata
  `TRAINING_RUN` y métricas válidas. Tras cambiar el puntero y reiniciar el worker,
  la versión servida permanece fijada. Hash incorrecto impide cargar, sin fallback.
- Corrupción e incompatibilidades, lock de escritor, activo inesperado,
  sobreescritura, fallo de replace y rollback corrupto rechazados según los gates.
- Filesystem y modelo host RO, red none, usuario `predicitas`, 2 CPU/1 GiB;
  registries y candidatos solo en tmpfs efímero. Legacy conserva SHA-256 histórico.
- Fuentes del bloque A comprobadas por sus hashes; backend/frontend/contratos,
  Compose, dependencias y aprobación legacy sin cambios. Sin despliegue ni BD.

Runs 01/02 se conservan como intermedios (227/227 cada uno); el 03 incorpora
rollback dirigido con hash obligatorio y es el único resultado vigente.
[Resumen y hashes de fuentes/resultados](evidencia/bloque-b-20261107-03/resumen.json).
JUnit/cobertura completos permanecen en runtime local; no se afirma paquete
portable ni verificación de clon limpio. La cobertura no agrega subprocess;
persisten los avisos previos Starlette y configuración `cache_dir`, sin actualizar
librerías. No se reejecutó backend/frontend.

Fase 6 sigue **EN CURSO**; seed/reconciliación, retirada de consumidores y camino
limpio integral no se implementan como parte de B. Retorno: recuperar solo los
archivos nuevos/cambios de B conservando A; no hay datos o modelos del entorno
que restaurar. No ejecutar downgrade ni tocar volúmenes.
