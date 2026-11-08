# PrediCitas CRP

## Reestructuración — IA separada

El backend usa el servicio de inferencia de `apps/ia/` por HTTP. Compose
conecta ambos mediante una red interna. IA carga un modelo aprobado desde
un directorio de solo lectura. El backend arranca aunque IA esté apagada y
las operaciones de inferencia devuelven 503 hasta que el servicio se recupera.

[Plan por fases](PLAN_REESTRUCTURACION_POR_FASES.md) ·
[Validaciones previas al retiro](docs/migracion/fase-07/BLOQUE_7F.md).

## Arranque local con los datos existentes

Requisitos: Docker Desktop con contenedores Linux y Docker Compose. Ejecutar desde esta raíz en PowerShell.

1. Comprobar que existe un respaldo privado verificable y que ningún stack anterior está escribiendo sobre la misma base.
2. Conservar el `.env` privado existente. Si se prepara otro equipo, usar `.env.example` como referencia y completar las **credenciales reales de su volumen**; no sobrescribir un `.env` existente. Cambiar el archivo no rota contraseñas PostgreSQL.
3. Definir una clave interna propia en `IA_API_KEY` en el `.env` privado y comprobar que `IA_MODEL_DIR` contiene el modelo aprobado. El valor predeterminado es `./artifacts/models/legacy-import`.
4. Confirmar el volumen aprobado (por defecto `predicitas-crp_pgdata`). `compose.yaml` lo declara externo: si no existe, el arranque debe fallar, no crear una base vacía.

```powershell
docker volume inspect predicitas-crp_pgdata
docker compose -f compose.yaml --env-file .env config --quiet
docker compose -f compose.yaml --env-file .env up -d --build db migraciones backend frontend ia
docker compose -f compose.yaml --env-file .env ps -a
```

`migraciones` ejecuta el historial existente; el retiro del predictor no introduce revisiones. No ejecutar sobre datos sin respaldo o con revisiones pendientes no aprobadas. La tarea `seed` queda fuera del arranque normal, tras un perfil explícito; **no ejecutarla sobre la base existente durante esta fase**. El arranque carga el modelo aprobado en IA y no ejecuta entrenamiento.

`IA_API_KEY` es un secreto local compartido. Usa un valor aleatorio de 32 bytes
codificado en hexadecimal en el `.env` de la raíz. Compose lo entrega a
backend e IA, y el backend lo envía en `X-IA-API-Key` por la red interna.
Para comprobar la configuración sin mostrar el secreto, usa `config --quiet`
como en el ejemplo.

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

Las pruebas de inferencia necesitan una instancia IA de laboratorio,
`IA_HTTP_TEST_URL` y la clave correspondiente en `IA_API_KEY`.
