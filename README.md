# PrediCitas CRP

## Reestructuración — fase 3

Aplicaciones en `apps/backend/` y `apps/frontend/`. La IA **sigue integrada en el backend**: su extracción corresponde a fases posteriores. No se han cambiado reglas de negocio, endpoints, CSV, modelo ni revisiones Alembic por esta mudanza.

**Estado y limitaciones:** [evidencia de fase 3](docs/migracion/fase-03/README.md), [fase 2](docs/migracion/fase-02/README.md) y [plan por fases](PLAN_REESTRUCTURACION_POR_FASES.md). Los informes de fases anteriores describen sus rutas y resultados históricos; no se reescriben sus evidencias.

**Archivos canónicos:** muestras en [`data/samples/importacion/`](data/samples/importacion/), [inventario y exportación segura](data/README.md), [modelo legacy y resultados QA](docs/operacion/ARCHIVOS_Y_RESULTADOS.md). Los CSV antiguos quedan solo como compatibilidad; el modelo activo mantiene su ruta integrada. No se activó retención de uploads/descargas, entrenamiento ni promoción.

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

El bootstrap, servicio IA autónomo, pipeline de entrenamiento y smoke final del plan todavía no están implementados. No ejecutar sus comandos objetivo como si ya existieran.
