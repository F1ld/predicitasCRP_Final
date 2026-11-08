# Fase 9 — bootstrap local

Punto de partida: `d5d1dbd`. El primer bloque implementa el modo `Verify`.

Desde PowerShell 7, con Docker Desktop en modo Linux:

```powershell
./scripts/bootstrap.ps1 -Mode Verify
```

Si el stack usa una capa Compose local de redes, pásala con
`-ComposeOverride <ruta>`. Para un archivo de entorno alternativo, usa
`-EnvFile <ruta>`. La configuración expandida se procesa en memoria.
El resultado muestra el nombre del proyecto, el volumen, la presencia
del artefacto y el estado de los contenedores.

`Verify` consulta Docker y el sistema de archivos. Comprueba que el
volumen externo existe, que backend e IA comparten una clave y que el
artefacto está montado de solo lectura en el servicio interno. La
presencia del archivo es una comprobación de configuración. El estado
de IA en Docker indica si el servicio en ejecución superó su healthcheck.

Se verificó en el stack actual y se rechazaron un archivo de entorno
ausente y un volumen inexistente. La primera prueba negativa reveló que
PowerShell podía lanzar la excepción nativa de Docker antes del mensaje
del script. Se corrigió y se confirmó que los contenedores y sus horas de
arranque se conservaron.

## Salud y disponibilidad

`/health` conserva su respuesta. `/health/ready` consulta PostgreSQL
con `SELECT 1` y devuelve 503 si falla. Compose usa esa ruta y el frontend
espera al backend saludable. El backend sigue pudiendo arrancar sin IA.
Pasaron tres pruebas focales con el acceso a base simulado y la validación
de la configuración Compose.

El ensayo integrado del 08/11/2026 usó redes internas, un volumen nuevo
y el Compose oficial con una capa de aislamiento. PostgreSQL y las
migraciones permitieron arrancar backend y frontend sin IA. El frontend
respondió 200 y el lote devolvió 503. Al arrancar IA, el lote respondió
200. Al detener PostgreSQL, salud devolvió 200 y readiness 503. La misma
instancia de backend recuperó readiness 200 al reiniciar PostgreSQL, con
las dos citas sintéticas y sus dos predicciones intactas.

Se detuvieron los contenedores del laboratorio y se conservó su volumen.
El conjunto de contenedores activos permaneció igual.

[Evidencia del ensayo](integrado-20261108-01.json).

## Existing

Usa las imágenes aprobadas ya disponibles localmente. Confirma por nombre
el volumen configurado y usa la misma capa de redes que el stack, si aplica.

```powershell
./scripts/bootstrap.ps1 -Mode Existing -ConfirmVolume predicitas-crp_pgdata
```

El modo comprueba el clúster del volumen con un montaje de solo lectura y
consulta la revisión esperada en la imagen local. Solo arranca el backend,
IA y frontend si la revisión PostgreSQL coincide. Conserva los contenedores
existentes y exige la imagen local del backend. Si hay una diferencia de
revisión, el operador debe revisar el respaldo y autorizar la migración
como paso separado. `Existing` no aplica migraciones, carga de datos ni
entrenamiento.

Para un ensayo aislado, `-Project predicitas-f9-<nombre>` exige un volumen
del mismo proyecto, redes internas y una capa sin puertos publicados ni
nombres fijos de contenedores.

El ensayo del 08/11/2026 ejecutó Existing dos veces sobre una copia del
volumen sintético. Se conservaron los IDs de contenedores, los recuentos
y huellas de las filas de citas y predicciones y el hash del modelo. El
nombre incorrecto se rechazó. Para simular una migración pendiente se
cambió solo el marcador de revisión en la copia y se restauró después.
Existing lo rechazó antes de arrancar la aplicación. Se detuvo el
laboratorio y el conjunto de contenedores operativos quedó intacto.

El primer ensayo falló antes del arranque porque la versión local de
Compose no admite `--no-build` en `compose run`. Se sustituyó por una
consulta a la imagen local, en un contenedor sin red y de solo lectura.

[Evidencia de Existing](existing-20261108-01.json).

## FreshDemo

Prepara un archivo de entorno privado separado del operativo. Define
`PGDATA_VOLUME_NAME` con el nombre del proyecto seguido de `_pgdata`,
dos subredes libres en `DEMO_DB_SUBNET` y `DEMO_IA_SUBNET`, y claves
propias para PostgreSQL, backend, IA y los usuarios de la demo
(`POSTGRES_PASSWORD`, `APP_DB_PASSWORD`, `SECRET_KEY`, `IA_API_KEY` y
`SEED_PASSWORD`). Indica un CSV sintético aprobado con `SEED_CSV_PATH`
absoluto, su SHA-256 en `SEED_CSV_SHA256` y `SEED_CONFIRMAR_BD=predicitas`.
El CSV puede prepararse con el generador canónico (`con_invalidas=False`)
y el exportador operacional de IA. El modelo debe existir en `IA_MODEL_DIR`.

```powershell
./scripts/bootstrap.ps1 -Mode FreshDemo -Project predicitas-f9-demo-mi-prueba `
    -ConfirmVolume predicitas-f9-demo-mi-prueba_pgdata -EnvFile 'C:/ruta/privada/demo.env' `
    -ComposeOverride docs/migracion/fase-09/freshdemo.compose.yaml
```

La capa de laboratorio usa redes internas y evita publicar puertos en
el host. FreshDemo exige un nombre de volumen sin uso previo, verifica
el hash antes de crear el volumen y ejecuta migraciones y seed como
tareas puntuales. Espera readiness de backend e IA y valida una
predicción sintética. Usa el modelo aprobado sin entrenar. Si falla
tras crear el volumen, detiene sus servicios y conserva el volumen para
diagnóstico. Para volver a usar una demo ya preparada, usa `Existing`.

El ensayo 02 creó diez citas sintéticas y las cuentas de Administrador,
Recepción y Técnico IA. Backend e IA superaron sus healthchecks, el
frontend respondió 200 por HTTP interno y la inferencia sintética pasó.
Un hash incorrecto se rechazó antes de crear el volumen. Repetir FreshDemo
con ese volumen se rechazó. Los contenedores del laboratorio se
detuvieron y el conjunto operativo quedó igual.

Durante los intentos previos, se corrigió un nombre fijo de contenedor
en la capa de aislamiento y se regeneró el CSV sin las filas inválidas
que el generador añade por defecto para QA. El volumen del ensayo fallido
quedó separado para diagnóstico.

[Evidencia de FreshDemo](freshdemo-20261108-02.json).

## Tareas explícitas de operación

El perfil Compose `seed-manual` habilita el seed. FreshDemo lo invoca
después de migrar su propio volumen. Los comandos equivalentes a los
perfiles de preparación, entrenamiento y pruebas se ejecutan por
separado desde una imagen IA local aprobada:

```powershell
./scripts/tareas-ia.ps1 -Tarea Preparar -Imagen predicitas-crp-ia -Ejecucion demo-datos-01 -FechaCorte 2026-11-08
./scripts/tareas-ia.ps1 -Tarea Entrenar -Imagen predicitas-crp-ia -Ejecucion demo-modelo-01 -DatasetDe demo-datos-01
./scripts/tareas-ia.ps1 -Tarea Probar -Imagen predicitas-crp-ia
```

Las tareas usan contenedores efímeros sin red, con raíz de solo lectura y
sin acceso a PostgreSQL. Preparar escribe y valida un dataset sintético.
Entrenar lee ese dataset en solo lectura y escribe un candidato en un
directorio nuevo bajo `runtime/fase-09/tareas-ia`. Probar monta el modelo
aprobado en solo lectura. La promoción del candidato sigue siendo una
operación explícita aparte.

El ensayo del 08/11/2026 ejecutó `docker compose up` sin seleccionar
servicios ni perfiles. Arrancaron solo DB, migraciones, backend, IA y
frontend. La base del laboratorio siguió con cero usuarios, citas y
predicciones. El inventario de Compose incluyó seed únicamente al
habilitar `seed-manual`; su ejecución explícita se verificó en FreshDemo.

La preparación validó el dataset, el entrenamiento produjo un candidato
y la suite de IA aprobó 241 pruebas. El hash del modelo aprobado se
conservó. Al comparar contenedores por etiquetas se detectó que las
tareas efímeras heredaban la etiqueta de proyecto de la imagen Compose.
Se asignaron etiquetas propias a las tareas y se repitió el arranque
normal comprobando por ID y hora de inicio que los cuatro servicios
operativos permanecieron intactos.

[Evidencia del arranque normal y las tareas](perfiles-20261108-01.json).

## Preparación local y ejecución nativa

Con PowerShell 7, desde la raíz, crea las carpetas vacías si faltan:

```powershell
New-Item -ItemType Directory -Force -Path apps/backend/Skills,apps/frontend/Skills | Out-Null
```

Usa PostgreSQL 16 con una base aprobada y los roles separados. El script
`apps/backend/db/init/01_rol_app.sh` se ejecuta al inicializar un volumen
nuevo. En un volumen existente, si falta `predicitas_app` o su acceso,
detén el arranque. Un administrador debe verificar roles, permisos y la
revisión Alembic con respaldo, y autorizar la reparación por separado.
Reiniciar PostgreSQL no vuelve a ejecutar el init.

Para ejecución nativa, prepara entornos Python 3.12 distintos en
`apps/backend` y `apps/ia` con `python -m venv .venv` e instala el
`requirements.txt` de cada aplicación. Configura las variables de cada
terminal en privado.

1. **Migraciones.** Desde backend, configura la conexión al rol dueño solo
   en una terminal de administración. Comprueba la revisión con
   `alembic current` y `alembic heads`. Ejecuta `alembic upgrade head`
   únicamente sobre un destino aprobado y respaldado.
2. **IA.** Desde `apps/ia`, configura `IA_API_KEY` y `MODEL_REGISTRY_DIR`
   hacia el directorio absoluto del modelo aprobado. Ejecuta
   `python -m uvicorn app.main:app --host 127.0.0.1 --port 8100`.
   Para preparar un dataset nuevo, usa la tarea Preparar de esta guía.
3. **Backend.** En otra terminal desde `apps/backend`, configura
   `DATABASE_URL` con el rol operativo, `SECRET_KEY`, la misma
   `IA_API_KEY` e `IA_URL=http://127.0.0.1:8100`. Ejecuta
   `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
   Comprueba `/health/ready`.
4. **Frontend.** Desde `apps/frontend`, ejecuta `npm ci`, configura
   `VITE_API_URL=http://127.0.0.1:8000` y ejecuta
   `npm run dev -- --host localhost --port 5173 --strictPort`. El origen
   debe coincidir con `CORS_ORIGENES` del backend.

Libera primero los puertos ocupados por otro stack. Esta guía nativa
describe la configuración. El ensayo integrado de esta fase usa Compose.

## Revisión de operación Compose

PostgreSQL recibe sus credenciales de inicialización y el migrador recibe
la URL del dueño. Backend y seed usan el rol operativo. IA recibe la clave
interna y el modelo de solo lectura. El frontend recibe la URL pública
del backend. Se mantienen las tareas puntuales con `restart: "no"`.
Se revisaron la política de reinicio de servicios persistentes, los
tiempos de parada, límites y logs. Se conservan los valores actuales de
Docker para el demo local. El dimensionamiento y la rotación se difieren
hasta contar con mediciones de operación.

## Cierre operativo (08/11/2026)

Se comprobó la configuración expandida sin publicar credenciales. Se
verificó un respaldo privado de PostgreSQL mediante lectura completa
con pg_restore y comparación SHA-256 después de copiarlo. El respaldo
está en `%LOCALAPPDATA%/Temp/opencode/predicitas-fase9-cierre-20261108-01`.

Se promovió el backend con readiness y se reanudó el mismo frontend
sobre el volumen aprobado. Ambos respondieron HTTP 200. La revisión de
Alembic y las huellas de usuarios, citas y predicciones coincidieron
antes y después. PostgreSQL e IA conservaron sus contenedores y horas
de arranque. El punto de retorno es `d5d1dbd` y la imagen local
`predicitas-backend-retorno:d5d1dbd`, con el healthcheck anterior
`/health` y el mismo volumen aprobado.

Se cierra la fase con salvedades. El init conserva su ubicación y
montaje ya validados. El dimensionamiento de servicios y la rotación
de logs quedan diferidos. La ejecución nativa queda documentada y
el ensayo operativo se realizó con Compose.

[Evidencia del corte](cierre-20261108-01.json).
