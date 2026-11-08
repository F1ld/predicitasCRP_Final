# PrediCitas CRP

## Reestructuración — fase 7 en curso (7A/7B)

Aplicaciones en `apps/backend/`, `apps/frontend/` y `apps/ia/`. La aplicación IA
autónoma fue validada y el camino limpio de fase 6 está cerrado en aislamiento,
pero el backend **todavía usa el predictor integrado**; su conexión HTTP y
retirada corresponden a fase 7, ahora en curso por las subentregas 7A/7B.

**7A/7B:** puerto/adaptador y cableado conservador en servicios/metadata. El
integrado sigue por defecto; HTTP requiere activación explícita y no se ha
desplegado. [Alcance y límites](docs/migracion/fase-07/README.md).

**Estado y limitaciones:** fases 0–6 completadas según el
[plan vigente](PLAN_REESTRUCTURACION_POR_FASES.md); [fase 6 COMPLETADA](docs/migracion/fase-06/README.md).
Pipeline, promoción/rollback, seed explícito y camino limpio E tienen validación
aislada. La [retirada programada D fue aprobada](docs/migracion/fase-06/DECISION_D_RETIRADA_PROGRAMADA.md)
y sus [cinco migraciones están validadas](docs/migracion/fase-06/MIGRACIONES_D.md).
El [bloque E](docs/migracion/fase-06/BLOQUE_E.md) generó, entrenó, promovió, sirvió,
sembró y verificó el backend en un laboratorio nuevo sin tocar la BD ni el modelo
activos. El predictor y su reexport conservan temporalmente el generador legacy
hasta fase 7. No se certifica suite completa verde; permanecen los límites
documentados en cada evidencia. Los informes previos son históricos y no se
reescriben para aparentar una ejecución nueva.

**Archivos canónicos:** muestras en [`data/samples/importacion/`](data/samples/importacion/), [inventario y exportación segura](data/README.md), [modelo legacy y resultados QA](docs/operacion/ARCHIVOS_Y_RESULTADOS.md). Los CSV antiguos quedan solo como compatibilidad; el modelo activo mantiene su ruta integrada. Entrenamiento y promoción nuevos son procesos offline explícitos: no se activan al arrancar el entorno existente. No se habilitó retención de uploads/descargas.

## Arranque local con los datos existentes

Requisitos: Docker Desktop con contenedores Linux y Docker Compose. Ejecutar desde esta raíz en PowerShell.

1. Comprobar que existe un respaldo privado verificable y que ningún stack anterior está escribiendo sobre la misma base.
2. Conservar el `.env` privado existente. Si se prepara otro equipo, usar `.env.example` como referencia y completar las **credenciales reales de su volumen**; no sobrescribir un `.env` existente. Cambiar el archivo no rota contraseñas PostgreSQL.
3. Confirmar el volumen aprobado (por defecto `predicitas-crp_pgdata`). `compose.yaml` lo declara externo: si no existe, el arranque debe fallar, no crear una base vacía.

```powershell
docker volume inspect predicitas-crp_pgdata
docker compose -f compose.yaml --env-file .env config --quiet
docker compose -f compose.yaml --env-file .env up -d --build db migraciones backend frontend
docker compose -f compose.yaml --env-file .env ps -a
```

`migraciones` ejecuta el historial existente; no hay revisiones nuevas en fase 2. No ejecutar sobre datos sin respaldo o con revisiones pendientes no aprobadas. La tarea `seed` queda fuera del arranque normal, tras un perfil explícito; **no ejecutarla sobre la base existente durante esta fase**. No se entrena ni se regenera el modelo al mover aplicaciones; conservar el `.joblib` confiable respaldado en `apps/backend/app/modules/ia/artifacts/`.

**Seed manual actualizado en fase 6 C:** requiere CSV sintético explícito, SHA-256
y nombre real de una BD nueva autorizada. No genera datos internamente ni admite
recarga destructiva; las cargas parciales requieren revisión y `--reconciliar`.
Ver [uso, pruebas y límites del bloque C](docs/migracion/fase-06/BLOQUE_C.md).
Esta actualización no autoriza sembrar el volumen existente.

- Interfaz: http://localhost:5173
- API: http://localhost:8000/docs
- Salud actual: http://localhost:8000/health (no sustituye una prueba funcional de BD).
- BD: `localhost:5432`, o `DB_PUERTO_HOST` configurado explícitamente si el puerto está ocupado.

Parada sin eliminar datos:

```powershell
docker compose -f compose.yaml --env-file .env stop
```

No usar `down -v`, reinicializar volúmenes, sembrar o reentrenar para resolver un problema de rutas. Compose conserva el nombre de proyecto `predicitas-crp`. Los dos Compose anteriores están archivados, **no son entradas operativas**: `docs/migracion/fase-02/historico/*.reference`.

## Desarrollo y pruebas

- Frontend, desde `apps/frontend/`: `npm ci`, `npm run typecheck`, `npm run lint`, `npm run build`, `npm test`.
- Backend, desde `apps/backend/`: crear un venv Python 3.12 nuevo e instalar `requirements.txt`. No reutilizar un venv con rutas antiguas. El `.env` local conservado es histórico y diverge de la BD oficial: revisar configuración y rol antes de usar ejecución nativa. No se certifica aún el arranque nativo completo (fase 9).
- `pytest` solo con `DATABASE_URL` y URL de migraciones explícitas hacia **PostgreSQL de pruebas aislado**, configuradas antes de importar la aplicación. No ejecutar las fixtures sobre demo/principal.
- Se conservan `Skills/` vacías dentro de ambas aplicaciones. Git no guarda carpetas vacías: recrearlas si se clona el repositorio.

El bootstrap local único y smoke final corresponden a fases posteriores; no se
presentan como implementados. La IA autónoma y el camino limpio de fase 6 tienen
comandos y límites en su bitácora: no implican que el backend ya consuma IA por
HTTP. La fase 6 se cerró con E validado en aislamiento; fase 7 empieza por el
puerto/adaptador 7A y cableado 7B opt-in. La activación HTTP del entorno
existente y la retirada del predictor siguen pendientes.
