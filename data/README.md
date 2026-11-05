# Datos y muestras — fase 3

**Única fuente operacional: PostgreSQL, administrado por el backend.** Estos archivos no son otra base de negocio. El piloto usa datos sintéticos/seudonimizados; no guardar DNI, teléfonos, diagnósticos ni datos reales aquí.

| Ruta | Responsabilidad | Git |
|---|---|---|
| `samples/importacion/` | CSV canónicos pequeños, con sus bytes/fechas históricos intactos | Sí, revisados |
| `fixtures/` | Solo fixtures realmente compartidos; los exclusivos de frontend no se trasladan | Sí, si se aprueban |
| `raw/<version>/` | Snapshots de entrenamiento inmutables, preparación explícita futura | No por defecto |
| `processed/<version>/` | Train/val/test reproducibles, fase 6 | No por defecto |
| `manifests/` | Inventario real, procedencia y hashes sin secretos | Sí |

`raw` y `processed` están vacías: **no se generó un dataset ni se atribuye su linaje al modelo existente**. No inventar semillas, fechas de generación ni hashes de entrenamiento a partir de estos CSV. Sus metadatos desconocidos se registran como null.

## Importación desde UI/API

- Elegir `samples/importacion/citas_para_importar_variado.csv`: 40 filas de demostración, fechas originales de noviembre de 2026.
- `samples/importacion/citas_demo.csv`: 24 filas, con cuatro rechazos intencionales: sede inválida, especialidad inválida, ID repetido y registro posterior a cita.
- En BD de pruebas vacía y reloj **2026-11-05 08:00 America/Lima**, los resultados de referencia son **40/0** y **20/4** (aceptadas/rechazadas). Duplicados ya existentes cambian los resultados; no probar escribiendo en principal.
- Se preserva la cabecera operacional de 13 columnas, UTF-8/BOM opcional, límites y validación de la API. No se cambiaron fechas, IDs ni filas para aparentar citas futuras.
- Las copias antiguas en raíz y `apps/backend/data/` se conservan por compatibilidad, con hash registrado. **No son canónicas, no se regeneran allí ni se sincronizan automáticamente**. Su retirada posterior requiere revisar consumidores externos y conservar respaldo; esta fase no borra CSV.

Ver [inventario](manifests/inventario-fase-03.v1.json) y [contrato operacional](../contracts/data/README.md). La referencia del reloj para validación **no** afirma cuál fue la fecha original de generación.

## Generar otra muestra sin modificar las existentes

Desde `apps/backend/`, con su entorno Python 3.12 preparado:

```powershell
$salida = [IO.Path]::GetFullPath((Join-Path $PWD '../../runtime/exports/demo-ref-2026-11-05-seed-7.csv'))
python -m scripts.exportar_csv --salida "$salida" --fecha-referencia 2026-11-05 --filas 20 --semilla 7
```

El nombre/ruta deben ser nuevos. Salida y fecha son obligatorias; rutas relativas y sobrescritura se rechazan. Dentro del repositorio solo se permiten `runtime/exports`, `runtime/tmp`, `runtime/test-results`, nunca código, muestras, artefactos o backups. Una ruta absoluta externa permite almacenamiento fuera de OneDrive. Se imprimen fecha, semilla y hash; cambiar la fecha produce otra muestra, no una actualización silenciosa de la anterior.

El exportador mantiene el generador existente y sus cuatro rechazos intencionales, pero proyecta **solo las 13 columnas operacionales** (sin target ni features calculadas). No es seed, snapshot BD ni pipeline de entrenamiento. La validación de importación sigue siendo responsabilidad de la API.

### Docker, sin BD ni montajes de código escribibles

Construir primero la imagen desde el contexto actual. Desde la raíz:

```powershell
docker compose -f compose.yaml --env-file .env build backend
$exports = [IO.Path]::GetFullPath((Join-Path $PWD 'runtime/exports'))
New-Item -ItemType Directory -Force -Path $exports | Out-Null
docker run --rm --network none --mount "type=bind,source=$exports,target=/runtime/exports" predicitas-crp-backend python -m scripts.exportar_csv --salida /runtime/exports/demo-ref-2026-11-05-seed-7.csv --fecha-referencia 2026-11-05 --filas 20 --semilla 7
```

Solo el destino de exportación es escribible. No montar PostgreSQL, backups, CSV completos ni `.env`; este comando no necesita credenciales de negocio. Las muestras se suben desde el navegador y no requieren montajes permanentes en el backend. Los contextos Docker no incluyen `data/` raíz; la copia legacy de `apps/backend/data/` también se excluye.

Los uploads y descargas de la API continúan en memoria/streaming. **No se activó retención**, TTL, limpieza automática ni `runtime/imports/`. Los archivos generados voluntariamente por CLI/QA son responsabilidad del operador; no hay tareas que borren respaldos o resultados.
