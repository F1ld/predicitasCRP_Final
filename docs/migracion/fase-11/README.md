# Fase 11 — Corte y cierre

## Verificación desde un clon limpio

El 8 de noviembre de 2026, el modo Verify pasó desde un clon local
de `862b099` con un archivo de entorno de laboratorio, un volumen
temporal propio y una copia del modelo con SHA-256 cotejado contra el
manifiesto versionado. La prueba previa rechazó el volumen ausente.
Verify no dejó contenedores del proyecto de laboratorio. Se eliminó el
volumen temporal después de la comprobación. El comando de comparación
de inventarios falló al recibir un inventario inicial vacío. La repetición confirmó que el inventario completo de contenedores quedó idéntico.

Verify también pasó sobre la configuración operativa. PostgreSQL,
backend, frontend e IA ya estaban detenidos al consultarlos.

## Corte operativo

1. Acordar la ventana con el equipo. Registrar el proyecto, volumen,
   capas Compose y los IDs de las imágenes de la versión vigente.
2. Detener los escritores durante la ventana. Registrar revisión de
   Alembic, conteos de usuarios, citas y predicciones y SHA-256 del
   modelo. Crear un respaldo privado de PostgreSQL y verificar su
   lectura completa y SHA-256. Mantenerlo fuera del repositorio.
3. Usar Verify y Existing con la configuración aprobada. Si se requiere
   una migración, aplicarla por separado con respaldo validado. Revisar
   disponibilidad, ejecutar el recorrido autenticado con Administrador,
   Recepción y Técnico IA y comparar persistencia tras reiniciar.
4. Conservar la versión anterior y el respaldo hasta la aceptación del
   equipo según la política de retención acordada.

## Retorno

Detener las escrituras. Registrar cualquier operación posterior al
respaldo. Confirmar que la revisión de la BD es compatible con la
versión de retorno y volver a sus imágenes y configuración, usando el
mismo volumen aprobado. Comprobar disponibilidad, conteos y recorridos
por rol antes de reabrir las escrituras. Si hace falta recuperar un
respaldo, validar primero la restauración en otro volumen y acordar cómo
preservar las operaciones posteriores.

La fase 9 documenta el retorno de su promoción de backend con
`predicitas-backend-retorno:d5d1dbd` y el healthcheck anterior `/health`.
Consúltalo junto con la [evidencia del corte de fase 9](../fase-09/cierre-20261108-01.json).

## Salvedades de la entrega

Siguen diferidos los 56 fallos históricos de Citas, la revisión del botón
de cálculo por lote y la incidencia de asignación de cupo liberado desde
la interfaz. Consulta la [validación de fase 10](../fase-10/README.md).

## Capa local de redes

En esta máquina, la recuperación usa `runtime/fase11-red-local.yaml`.
Conservar una copia de esta capa junto con la configuración local. Si
falta, recrearla con las subredes registradas abajo y comprobar que
Docker no tenga redes superpuestas. Para otro equipo, seleccionar
subredes libres según su inventario.

```yaml
networks:
  default:
    ipam:
      config:
        - subnet: 10.253.247.176/28
  inferencia:
    ipam:
      config:
        - subnet: 10.253.247.192/28
```

```powershell
$layer = 'runtime/fase11-red-local.yaml'
./scripts/bootstrap.ps1 -Mode Verify -ComposeOverride $layer
./scripts/bootstrap.ps1 -Mode Existing -ConfirmVolume predicitas-crp_pgdata -ComposeOverride $layer
docker compose --env-file .env -f compose.yaml -f $layer stop
```

El primer intento de Existing usó el Compose base. La capa anterior,
guardada en un directorio temporal, ya no estaba disponible. Compose
retiró la red principal y falló al crear su reemplazo. El intento
dejó el stack detenido. Se conservó la red interna de IA. Para recuperar
la red principal se recrearon PostgreSQL, backend y frontend con las
mismas imágenes y el volumen respaldado.

## Documentación vigente e histórica

El [README raíz](../../../README.md), los [contratos](../../../contracts/README.md)
y esta guía son las entradas de operación. Los expedientes de fases
anteriores documentan su contexto y evidencias. Los Compose anteriores
siguen archivados en fase 2. Se conservaron los informes de cronograma y
diseño en sus rutas para mantener sus referencias.

## Resultado del corte local del 8 de noviembre de 2026

- El respaldo privado se leyó completo con `pg_restore` y su SHA-256
  coincidió con la copia local. Está en
  `%LOCALAPPDATA%/Temp/predicitas-fase11-d464c943baa4457f9433cbeb05ae555f/predicitas.dump`.
  La lectura del respaldo verificó el archivo. El corte utilizó el
  volumen existente `predicitas-crp_pgdata`.
- El smoke de disponibilidad de backend, PostgreSQL y frontend pasó
  antes y después del reinicio completo con Existing. Se comprobó la
  salud de IA. Coincidieron la revisión Alembic
  `m01_001_indices_auditoria`, el SHA-256 del modelo aprobado y las
  huellas de las filas de 4 usuarios, 1.124 citas y 108 predicciones.
- En navegador, Administrador abrió Usuarios. Recepción abrió Citas,
  vio Importar CSV y no vio Usuarios. Técnico IA abrió Modelo IA y
  no vio Usuarios ni Importar CSV. Se cerraron las tres sesiones.
  El recorrido se limitó al acceso y la navegación.
- Se verificó que `apps/backend/Skills/` y `apps/frontend/Skills/`
  existen y están vacías. Se conservó el respaldo y las imágenes
  existentes. PostgreSQL, backend, frontend e IA quedaron activos.

El resultado del cierre y la retención se registran en V3A.

## V1A — Verificación técnica

Se reprodujo el recorrido del README revisado en un clon de `862b099`
con la documentación de trabajo, una copia del modelo cotejada contra
el manifiesto y un CSV sintético de fase 9. El proyecto aislado
`predicitas-f9-demo-v1a-c3fbd660` pasó FreshDemo, Verify y Existing.
El frontend respondió por HTTP interno y las diez citas sintéticas
persistieron tras reiniciar. Se detuvo el laboratorio y se confirmaron
los mismos IDs y horas de arranque del stack operativo.

Dos intentos preparatorios fallaron por la forma de pasar parámetros
en PowerShell y por usar `.env` como nombre del entorno de FreshDemo.
Se corrigieron con parámetros nombrados y un `demo.env` independiente.
El primer intento de restauración se detuvo al tratar PostgreSQL
todavía no listo como un error fatal. La repetición esperó a readiness.

El 8 de noviembre de 2026 se restauró el respaldo final en PostgreSQL
aislado y sin red. Se compararon huellas de las diez tablas del esquema
public, 25 restricciones de clave y nueve secuencias. Coincidieron las
claves y ocho secuencias, y coincidieron las huellas de las tablas salvo
la de auditoría. La comparación por ID confirmó que los 91 eventos del
respaldo conservan sus huellas. La base operativa agregó tres eventos
LOGIN y tres LOGOUT, y la secuencia avanzó de 91 a 97.

Se examinaron 1.028 objetos de texto alcanzables desde las referencias
locales de Git mediante patrones de claves privadas, tokens de
proveedores y JWT. La búsqueda por esos patrones no arrojó coincidencias.
También se compararon cuatro valores del archivo de entorno operativo.
Tres coinciden con valores versionados de ejemplo, correspondientes a
`POSTGRES_PASSWORD`, `APP_DB_PASSWORD` y `SECRET_KEY`. La revisión no
publicó sus valores. El criterio de secretos queda abierto hasta
sustituir esas credenciales operativas y verificar la configuración
resultante.

## V2A — Pruebas

El 8 de noviembre de 2026 se repitieron las suites con las imágenes
construidas desde `862b099`. La suite backend usó una base exclusiva
dentro del PostgreSQL de laboratorio. El recorrido HTTP utilizó las
cuentas y citas sintéticas de la demo aislada.

- Backend confirmó 399 pruebas distintas aprobadas entre dos
  ejecuciones, con 93,97 % de cobertura de la ejecución general y dos
  omisiones de laboratorio, arranque con IA caída y medición de carga.
  La ejecución general aprobó 378 y mostró 21 fallos o errores del
  verificador de archivos de fase 3 al faltar el árbol del repositorio.
  Con el clon completo montado en solo lectura, ese archivo aprobó sus
  34 pruebas, incluidas las 21 anteriores. El umbral global de cobertura
  quedó por debajo del mínimo en la ejecución focal de un solo archivo.
- Frontend pasó typecheck, lint y build. La primera ejecución de
  Vitest mostró 76 fallos. La repetición con dos procesos registró
  455 aprobadas, 56 fallos y 92,15 % de cobertura de líneas.
  Los 56 coinciden por archivo y nombre con fase 10. Los otros 20
  no se reprodujeron en la repetición. V2B conserva las salvedades.
- IA aprobó 241 pruebas y obtuvo 89,95 % de cobertura, igual que en
  fase 10.
- El recorrido HTTP verificó acceso anónimo rechazado, identidad y
  permisos de los tres roles, consultas de citas, métricas y resumen
  del dataset, predicción individual y lote de seis citas elegibles.
  El frontend respondió por HTTP. Tras reiniciar se conservaron diez
  citas y seis predicciones. Se detuvo el laboratorio y los IDs y horas
  de arranque de los contenedores operativos coincidieron.
- El primer recorrido solicitó una predicción para una cita no
  elegible y recibió HTTP 409. Se repitió con el conjunto de citas
  elegibles para el lote.

## V2B — Salvedades

- El botón de cálculo por lote evaluó una cita sintética nueva desde
  Intervenciones. Al repetirlo, mostró cero citas pendientes.
- La oferta de un cupo sintético reprodujo en navegador el error de
  recurso no encontrado. La interfaz enviaba rutas distintas de las
  expuestas por el backend. Se corrigieron las rutas de oferta, cierre
  por rechazo, cierre sin respuesta y reasignación. En el laboratorio
  se completaron los cuatro pasos. El diálogo exigió confirmación y
  medio antes de habilitar el registro. El cupo siguió reasignado al
  recargar y la cita de origen conservó su estado cancelado e historial.
  Pasaron typecheck, lint y las 58 pruebas focalizadas de cupos e
  intervenciones. La corrección se verificó en la demo aislada.
- Los 56 fallos de V2A se concentran en dos archivos de Citas.
  `Detalle.test.tsx` aporta 40 casos de lectura, cambios de estado,
  llegada, predicción y enlace a intervenciones. `citas.test.tsx`
  aporta 16 casos de detalle, transición, importación y permisos.
  La demo verificó el detalle de la cita cancelada y su historial,
  y la fase 10 verificó la importación desde navegador. El responsable
  aceptó diferir los 56 casos para cerrar el alcance de la entrega.

## V3A — Cierre formal

- **Operación y validación.** [README principal](../../../README.md),
  [guía de pruebas](../../historico/pruebas/GUIA_DE_PRUEBAS_PARA_EL_EQUIPO.md),
  [inventario de archivos](../../operacion/ARCHIVOS_Y_RESULTADOS.md)
  y [contratos vigentes](../../../contracts/README.md).
- **Diseño y contexto histórico.** [Diseño de BD](../../historico/diseno/DISEÑO_BD_PREDICCION_CITAS.md),
  [diagnóstico y diseño del dataset](../../historico/diseno/DIAGNOSTICO_BD_Y_DISENO_DATASET_IA.md),
  [especificación inicial](../../historico/diseno/ESPECIFICACION_SISTEMA_Y_ESTADO_ACTUAL.md)
  e [instrucciones de la distribución ZIP](../../historico/operacion/INSTRUCCIONES_RAPIDAS_ZIP.md).
- **Seguimiento histórico.** [Auditoría del 4 de noviembre](../../historico/seguimiento/AUDITORIA_CRONOGRAMA_04_NOVIEMBRE.md),
  [conformidad del 5 de noviembre](../../historico/seguimiento/INFORME_CONFORMIDAD_CRONOGRAMA_05_NOVIEMBRE.md),
  [pruebas CSV](../../historico/seguimiento/ESTADO_CONFORMIDAD_CRONOGRAMA_Y_PRUEBAS_CSV.md),
  [entrenamiento y pesos](../../historico/diseno/EXPLICACION_ENTRENAMIENTO_DATASET_Y_PESOS_IA.md)
  y [resumen ejecutivo](../../historico/seguimiento/RESUMEN_EJECUTIVO_TRABAJO_REALIZADO.md).

En el cierre V3A se conservaron las rutas y fechas. Los enlaces anteriores apuntan a las ubicaciones posteriores a la limpieza documental. Los Compose históricos
se conservan como referencias de fase 2. La búsqueda de
`contratos/comun.json` en Markdown encontró únicamente el propio
checklist. El índice operativo apunta a `contracts/README.md`.

El 8 de noviembre de 2026 se aplicó la corrección de cupos al
frontend principal. Se reconstruyó y recreó solo ese servicio con la
capa local de redes. El archivo desplegado coincidió por SHA-256 con
el código validado en V2B. El smoke confirmó frontend, salud de API
y disponibilidad de PostgreSQL. Coincidieron los IDs y las horas
de arranque de PostgreSQL, backend e IA.

Se conservó una copia privada del respaldo final en
`%LOCALAPPDATA%/PrediCitasCRP/Backups/fase11-20261108/predicitas.dump`,
con el mismo SHA-256 que el respaldo de corte. Las imágenes de retorno
quedaron identificadas como `predicitas-frontend-retorno:v3a` y
`predicitas-backend-retorno:d5d1dbd`. Se conservarán como mínimo
hasta la aprobación del curso. Su retirada será manual.

Para revertir únicamente el frontend, desde la raíz:

```powershell
docker image tag predicitas-frontend-retorno:v3a predicitas-crp-frontend:latest
docker compose -p predicitas-crp --env-file .env -f compose.yaml -f runtime/fase11-red-local.yaml up -d --no-deps --no-build --pull never frontend
./scripts/smoke.ps1
```

La fase 11 queda cerrada para la entrega académica. Los 56 casos
automatizados de Citas se mantienen como trabajo diferido.
