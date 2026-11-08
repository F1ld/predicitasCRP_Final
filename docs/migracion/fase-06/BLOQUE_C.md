# Fase 6 — bloque C: seed explícito, repetible y transaccional

Autorizado por el usuario el 07/11/2026. Baseline Git `d6e9b1c`; cambios A/B
sin commit preservados y comprobados por sus hashes. No hay commit automático.

## Alcance y seguridad

- `apps/backend/scripts/seed.py` ya no importa ni ejecuta el generador: consume
  un CSV operacional explícito de 13 columnas, UTF-8/BOM, hasta 2 MiB/5000 filas.
- Exige ruta absoluta regular, SHA-256 aprobado (64 dígitos hex en minúsculas) y `--confirmar-bd` igual
  al nombre real que devuelve PostgreSQL. No hay dataset, ruta o destino por defecto.
- El perfil Compose sigue siendo manual y fuera del arranque habitual; CSV RO,
  `create_host_path: false` y variables explícitas. No se pasa contraseña por argv,
  no hay contraseña fija YAML ni credenciales owner en el proceso seed.
- `SEED_PASSWORD` local o getpass oculto **solo si faltan usuarios**. La clave
  nueva sigue la política backend; las cuentas existentes no cambian contraseña,
  nombre, rol, estado ni revocación de sesiones. Rol incompatible/inactivo aborta.
- Bootstrap de usuarios por ORM como el seed anterior, con hash backend y auditoría
  append `SEED_CREATE` sin claves/hashes. No usa `usuarios.service.crear`, porque
  requiere actor existente y hace commit propio, incompatible con la transacción
  única de bootstrap. No se modifica ese servicio ni la API de usuarios.
- Una única transacción contiene usuarios+citas+historial+auditoría. Las citas se
  insertan exclusivamente por `citas.public.importar_citas_interno`, sin SQL de
  inserción paralelo ni commits ocultos. Cualquier rechazo inesperado aborta todo.
  PostgreSQL puede dejar saltos de secuencia tras un rollback; no se reinician
  secuencias para ocultarlos ni se promete que sus valores sean transaccionales.
- Validación de negocio por el mismo `validar_fila` backend; los contadores vacíos
  se omiten, fechas/offsets se normalizan y target se deriva del desenlace.
  Se admiten únicamente IDs sintéticos `CIT-SIM-*`/`PAC-SIM-*` para este seed;
  esto no modifica el contrato de importación HTTP general.

## Repetición y cargas parciales

Se examinan **todas** las filas del archivo, no la existencia de algún `CIT-SIM-*`:

1. Ninguna existe: importar el conjunto completo.
2. Todas existen y coinciden: no insertar ni reauditar citas; no solicitar clave
   si ya están las cuentas demo. El rerun queda sin escrituras si no falta nada.
3. Parte existe y coincide: error `CARGA_PARCIAL_REQUIERE_RECONCILIAR` con conteos.
   Solo `--reconciliar` permite insertar exclusivamente las faltantes.
4. Alguna difiere, ya avanzó operativamente o no tiene su historial inicial:
   abortar sin sobrescribir. `--reconciliar` **no** autoriza corregir filas existentes.

La comparación incluye fields normalizados, derivadas, target e historial de
importación. Si un contador fue omitido, se calcula su expectativa RN17 usando
desenlaces persistidos + históricos faltantes del CSV. Una carga desordenada que
haya dejado contadores incompletos se **reporta como conflicto**: no se declara
reconciliada ni se reescribe ese dato silenciosamente. Requiere revisión aparte.
Los datos ajenos al archivo no se eliminan ni se fusionan por prefijo.

El seed toma un advisory lock transaccional no bloqueante exclusivo para otros
seeds y locks de filas existentes en orden estable. Un segundo seed falla con
`OTRO_SEED_EN_CURSO`; la unicidad de la BD protege frente a importaciones/altas
ajenas. No se desactivan triggers, RLS o constraints ni se crean migraciones.

## Uso manual (solo una BD nueva autorizada)

Primero generar el `seed.csv` con la CLI IA de bloque A. La fecha de referencia
debe elegirse conscientemente: una demo histórica no se convierte en futuras
al cambiar el reloj. Verificar el hash de `seed-manifest.json` y confirmar la BD.

Desde `apps/backend/`, en entorno Python exclusivo del backend:

```powershell
# Variables locales ya configuradas hacia la BD NUEVA elegida; no usar .env demo.
# SEED_PASSWORD se establece localmente sin registrarla en historial/logs.
python -B -m scripts.seed --csv "C:\datos\dataset-aprobado\seed.csv" --sha256 <HASH_APROBADO> --confirmar-bd <BD_NUEVA>
# Solo después de revisar el informe de carga parcial:
python -B -m scripts.seed --csv "C:\datos\dataset-aprobado\seed.csv" --sha256 <HASH_APROBADO> --confirmar-bd <BD_NUEVA> --reconciliar
```

En Compose: definir `SEED_CSV_PATH` existente, `SEED_CSV_SHA256`, `SEED_CONFIRMAR_BD`
y la contraseña local si se crearán cuentas. El perfil `seed-manual` NO se invoca
en esta implementación ni sobre el volumen principal. `docker compose config --quiet`
valida configuración sin imprimir secretos; no equivale a haber ejecutado el seed.
El camino existente sigue sin sembrar por defecto. No existe opción de reset.

## Pruebas y evidencia

Runner host stdlib `validar_seed_c.py`: imagen backend empaquetada nueva; PostgreSQL
nuevo con red interna, sin puertos host, volumen exclusivo y passwords aleatorios
en Temp privado con ACL del usuario. Rol de prueba operativo, owner solo para
crear rol/migrar. Nunca usa `.env` reales, principal ni contenedores previos.
Conserva recursos para diagnóstico y detiene solo su propio contenedor verificado.

```powershell
python -B docs/migracion/fase-06/validar_seed_c.py --run-id bloque-c-20261107-03 --ia-image sha256:41ca225ddcb1a930e5232e747d6e5e2527f605f3f8154c1611e201dff03ead73
```

Ese ID de ejecución debe ser NUEVO; el runner rechaza carpetas/recursos/imágenes
preexistentes. La imagen IA corresponde a B, con fuentes A preservadas.

Gates: CSV inválido/hash/duplicados/fechas/IDs, nulos/BOM/Unicode, confirmación BD,
usuarios incompatibles, no rotación, rerun, parcial explícito, conflicto sin
sobrescritura, contadores inferidos incompletos y no import de generador. Sonda
CLI adicional con CSV canónico de 1080 filas: commit real, repetición, reconciliación,
lock concurrente y fallo tras flush observado desde otra conexión.

La colección completa se caracteriza por separado. `tests/ia` conserva S-02;
`test_evidencia_fase3.py` y `test_archivos_fase3.py` dependen del árbol monorepo
fuera de `/app`, no de una imagen backend autónoma: se excluyen expresamente
de la regresión empaquetada, no se corrigen ni se presentan como aprobados.
No se certifica suite completa verde, frontend ni fase 6 cerrada.

En el intento 02, la colección completa registró exactamente dos errores:
`app.modules.ia.cliente` ausente (S-02) e `IndexError` en el verificador de evidencia
fase 3 por profundidad de rutas en `/app`. No son fallos del seed nuevo; los dos
archivos dependientes de monorepo se dejan fuera del diagnóstico empaquetado.

## Resultado vigente (07/11/2026)

**Bloque C implementado y validado en aislamiento**, ejecución
`bloque-c-20261107-03`:

- **21/21 pruebas específicas**, **330/330 regresión empaquetada** (incluye las
  21 nuevas, no se suman dos veces). Cobertura app+seed **91,07 %**, seed **88,07 %**.
- Pipeline IA canónico generó CSV explícito; CLI backend importó **1080 citas,
  2080 historiales y 3 usuarios** con rol `predicitas_app`.
- Rerun con otra contraseña local: cero filas nuevas y **todas las tablas
  idénticas**, incluidos hashes de usuarios e historial/auditoría.
- Parcial detectado sin escritura; reconciliación explícita agregó solo 2 filas
  faltantes. Conflicto y seed concurrente rechazados. Contadores inferidos
  incompletos cubiertos por prueba específica de rechazo sin sobrescritura.
- Fallo inducido después del flush de usuarios+citas+historial+auditoría: ningún
  registro visible desde observador independiente, ni después del rollback.
- Cierre de sonda: **1083 citas, 2086 historiales, 3 usuarios y 6 auditorías**;
  todo exclusivamente sintético y en laboratorio nuevo.

Imagen backend ejecutada por ID
`sha256:421227ed06dabde3f18c67692a97aa573283731aa51204ecd74a80b795871bd8`,
sin fuentes backend del host montadas. Rootfs/CSV RO, PostgreSQL en red interna,
sin puertos publicados ni volúmenes originales. Laboratorios 01/02/03 detenidos,
recursos conservados. No se sembró el entorno existente. `compose config --quiet`
salida 0, sin arrancar el stack principal. Modelos integrado/legacy con SHA-256
histórico; fuentes A/B preservadas y código funcional backend/API sin cambios.

Intento 01: 20 focales, diagnóstico bloqueado por estructura de imagen. Intento
02: 21 focales y 330/0, sonda no arrancó por `PYTHONPATH` del runner externo;
corregido en 03 sin modificar la aplicación. Solo 03 es resultado vigente.

[Resumen sanitizado y hashes](evidencia/bloque-c-20261107-03/resumen.json).
Resultados completos en runtime local, no un paquete portable ni clon limpio
certificado. La colección completa conserva los dos errores caracterizados;
no se presenta como suite completa verde. La cobertura no agrega los subprocess
de la sonda. Frontend no reejecutado. Fase 6 **EN CURSO**, sin iniciar D/E/7.

Retorno: recuperar solo seed/Compose/.env.example de antes de C, preservando A/B;
no regenerar BD ni revertir datos. Pruebas únicamente en laboratorio nuevo;
no hay seed realizado sobre la BD del entorno existente.
