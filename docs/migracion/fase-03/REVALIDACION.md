# Revalidación de trazabilidad de fase 3

## Criterios congelados antes de ejecutar

1. Implementación, pruebas, muestras, manifiestos y herramientas registrados en un commit, árbol limpio antes de construir/probar. Un segundo commit contiene solo documentación y evidencia.
2. Una ejecución nueva identificada por `--run-id`, sin sobrescrituras, sin fallback a `_final` y sin mezclar generaciones. Los archivos de cierre anteriores son históricos inmutables.
3. Imagen construida desde `apps/backend` y ejecutada por su Image ID inmutable. Se registran commit, blobs canónicos Git de las fuentes (toleran checkout CRLF/LF), Python, `pip freeze --all` y su SHA-256. Esto identifica el entorno observado, no promete reconstrucción bit a bit de la imagen base ni de dependencias transitivas. Evidencia pública y muestras conservan sus comprobaciones SHA-256 de bytes.
4. Unitarias de archivos/harness aprobadas; diagnóstico backend con los mismos casos/estados previos y todas las pruebas nuevas aprobadas; cobertura ≥ 75 %. La suite completa conserva y declara el error de colección IA previo: no se presenta como verde.
5. Integración real solo en el laboratorio registrado: muestras 40/0 y 20/4, BOM, duplicados, rollback, OpenAPI y predicciones. Empaquetado probado separadamente, sin montar fuentes.
6. Importar QA no cambia CWD ni `sys.path` ni crea resultados; prueba positiva de `main()` con conexión simulada y corte antes de BD/servidor reales. No sustituye al E2E visual legacy.
7. Paquete público con JUnit sanitizados (identidad/estado, sin tracebacks, stdout ni propiedades), cobertura resumida, resultados funcionales y hashes. Verificación desde un clon del commit final sin Docker, `.env`, modelo ni archivos ignorados.
8. Frontend: baseline citado, **no reejecutado**. Deuda D-01 a D-04 conservada; no tocar reglas de negocio, CSV, modelo, credenciales ni volúmenes originales.

## Ejecución (PowerShell, desde la raíz)

Ejemplo de ID: `cierre-20261105-01`. Elegir otro para una ejecución nueva o fallida; nunca borrar la anterior para liberar nombres.

```powershell
python -B docs/migracion/fase-03/validar.py build --run-id cierre-20261105-01
python -B docs/migracion/fase-03/validar.py unitarias --run-id cierre-20261105-01
python -B docs/migracion/fase-03/probar_imagen.py --run-id cierre-20261105-01
python -B docs/migracion/fase-03/validar.py reanudar --run-id cierre-20261105-01
python -B docs/migracion/fase-03/validar.py integracion --run-id cierre-20261105-01
python -B docs/migracion/fase-03/validar.py regresion --run-id cierre-20261105-01
python -B docs/migracion/fase-03/validar.py detener --run-id cierre-20261105-01
python -B docs/migracion/fase-03/verificar_cierre.py --run-id cierre-20261105-01
```

Detener **siempre** el laboratorio después de pruebas, incluso si estas fallan. No usar `down -v`, no recrear ni eliminar recursos. `reanudar` comprueba etiqueta, volumen, red interna, ausencia de puertos y destinos de las dos URLs privadas. Los tests usan rollback; no se promete revertir secuencias PostgreSQL. No aprovisiona laboratorios ni busca uno alternativo.

`regresion` termina con código 1 por los fallos conocidos; solo `verificar_cierre.py` decide su aceptación comparando casos y estados con baseline. Un fallo diferente bloquea el cierre. Las cantidades se derivan del JUnit, no se prefijan.

## Prerrequisitos privados y límites del clon

- Construir la imagen requiere el **modelo activo no versionado** en su ruta histórica, con hash registrado en el inventario. No se copia al paquete público, no se entrena ni se cambia su ubicación.
- Integración/regresión requieren Docker, el laboratorio registrado y el env privado existente. Un clon público no provisiona esos recursos ni puede repetir esas pruebas por sí solo.
- El clon limpio sí debe poder verificar fuentes, muestras, manifiestos y el paquete de resultados públicos, solo con Python estándar y Git. Esa verificación no equivale a reejecutar la aplicación ni a reconstruir el modelo.

```powershell
python -B docs/migracion/fase-03/verificar_cierre.py --run-id cierre-20261105-01 --verify-only
```

## Disposición de evidencia

- `runtime/test-results/fase-03/<run-id>/`: logs/JUnit originales, cobertura y metadatos. Privados/ignorados; apertura exclusiva.
- `runtime/exports/fase-03/<run-id>/`: exportación empaquetada de prueba, destino exclusivo.
- `docs/migracion/fase-03/evidencia/<run-id>/`: resultados sanitizados y verificables que se incluyen en la entrega.
- `docs/migracion/fase-03/evidencia/actual.json`: índice documental de la ejecución aceptada. Se actualiza explícitamente con la documentación, nunca por un test.

Los archivos anteriores `_final` y sin sufijo conservan su ubicación. El nuevo verificador nunca los usa como alternativa si falta un resultado. El paquete conserva hashes del material crudo, pero su comprobación pública depende solo de los archivos sanitizados incluidos.
