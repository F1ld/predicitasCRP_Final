# PrediCitas CRP

## Reestructuración — IA separada

El backend usa el servicio de inferencia de `apps/ia/` por HTTP. Compose
conecta ambos mediante una red interna. IA carga un modelo aprobado desde
un directorio de solo lectura. El backend arranca aunque IA esté apagada y
las operaciones de inferencia devuelven 503 hasta que el servicio se recupera.

[Plan por fases](PLAN_REESTRUCTURACION_POR_FASES.md) ·
[Validaciones previas al retiro](docs/migracion/fase-07/BLOQUE_7F.md).

## Arranque local

Usa PowerShell 7 y Docker Desktop con contenedores Linux. Ejecuta los
comandos desde la raíz del repositorio. En un clon nuevo, prepara un
archivo de entorno privado según `.env.example` y obtén del responsable
el modelo aprobado `modelo_predicitas_v1.joblib`. El modelo se entrega
por separado. Comprueba su SHA-256 contra
[el manifiesto aprobado](apps/ia/manifests/legacy-approved.json) antes de
colocarlo en `artifacts/models/legacy-import` o configurar `IA_MODEL_DIR`.

- **Verify** comprueba la configuración, la existencia del volumen externo
  y la presencia del modelo en un montaje de solo lectura. Muestra los
  contenedores del proyecto, si existen.
- **Existing** usa las imágenes locales aprobadas y el volumen existente.
  Las contraseñas del archivo privado deben coincidir con las de ese
  volumen. Usa el nombre de volumen y la capa Compose del stack aprobado.
- **FreshDemo** crea una demo aislada con un proyecto y volumen nuevos.
  Sigue la [preparación de la demo sintética](docs/migracion/fase-09/README.md#freshdemo)
  para configurar redes, credenciales y el CSV con su SHA-256.

```powershell
./scripts/bootstrap.ps1 -Mode Verify
./scripts/bootstrap.ps1 -Mode Existing -ConfirmVolume predicitas-crp_pgdata
```

Si usas un archivo de entorno alternativo o una capa Compose local,
pásalos a ambos comandos con `-EnvFile` y `-ComposeOverride`. Si el
volumen, la imagen, el modelo o la revisión de Alembic difieren de lo
esperado, comprueba la configuración aprobada antes de continuar.
Consulta la [guía de bootstrap](docs/migracion/fase-09/README.md) y el
[procedimiento de corte y retorno](docs/migracion/fase-11/README.md).

- Interfaz en http://localhost:5173
- API en http://localhost:8000/docs
- Disponibilidad de PostgreSQL desde el backend en http://localhost:8000/health/ready
- [Contratos de integración](contracts/README.md)

Para detener el stack y conservar los datos, usa `docker compose stop`
con el mismo proyecto, archivo de entorno y capas Compose del arranque.

## Desarrollo y pruebas

- Frontend, desde `apps/frontend/`: `npm ci`, `npm run typecheck`, `npm run lint`, `npm run build`, `npm test`.
- Backend, desde `apps/backend/`: crear un venv Python 3.12 nuevo e instalar `requirements.txt`. No reutilizar un venv con rutas antiguas. El `.env` local conservado es histórico y diverge de la BD oficial: revisar configuración y rol antes de usar ejecución nativa. No se certifica aún el arranque nativo completo (fase 9).
- `pytest` solo con `DATABASE_URL` y URL de migraciones explícitas hacia **PostgreSQL de pruebas aislado**, configuradas antes de importar la aplicación. No ejecutar las fixtures sobre demo/principal.
- Se conservan `Skills/` vacías dentro de ambas aplicaciones. Git no guarda carpetas vacías: recrearlas si se clona el repositorio.

Las pruebas de inferencia necesitan una instancia IA de laboratorio,
`IA_HTTP_TEST_URL` y la clave correspondiente en `IA_API_KEY`.
