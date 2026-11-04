# Cierre técnico de fase 0 — 03/11/2026

**Estado: COMPLETADA en su alcance de inventario, respaldo, recuperación y establecimiento de línea base.** No significa que la aplicación pase todas las pruebas ni que ya esté reestructurada.

## Decisiones confirmadas

1. El usuario confirmó `predicitas-crp_pgdata` como volumen principal. Base `predicitas`, revisión `m01_001_indices_auditoria`, 1.122 citas, 4 usuarios y 4 predicciones al tomar el respaldo. Los volúmenes Backend y QA se conservan sin fusionar.
2. El usuario eligió **«Aceptar evidencia funcional»** en sustitución de capturas bloqueadas por ventana no visible. Se conserva navegación comprobada, extractos del snapshot y smoke API. No se declara validación visual completa.
3. Se conserva el repositorio raíz existente y su snapshot `69c686f21fd1938dc76d679f4c6b33270f10a6d7`. No existen repositorios internos que integrar; no se hicieron commits ni cambios de historial.

Evidencias: `decision_bd_principal.json`, `decision_evidencia_visual.json`, `inventario_entorno.json` y `navegador_snapshot_extractos.md`.

## Pendientes técnicos resueltos en la continuación

- **Instalación limpia real del backend:** un venv nuevo, sin `system-site-packages`, dentro de un contenedor desechable Python 3.12.16. Se instalaron los requirements originales desde el índice sin modificarlos. Resultado: exit code 0, 164,36 segundos, las **54 versiones fijadas coinciden** y `pip check` terminó con código 0: `No broken requirements found.`
- El primer timeout de red queda como evidencia histórica; ya no es un bloqueo. Los paquetes transitivos no fijados pueden variar: por ejemplo, coverage 7.17.1 en el venv nuevo frente a 7.17.0 en la imagen anterior. No se cambiaron locks o requirements para ocultarlo.
- Las pruebas previamente medidas pertenecen a la imagen original con código actual RO; **no se afirma que se hayan vuelto a ejecutar en el venv limpio**. La nueva comprobación acredita instalación y consistencia de dependencias.
- **Credenciales demo identificadas:** las tres cuentas históricas existen, están activas y su hash coincide con la clave de seed del Compose original. Se verificó localmente en la copia restaurada, sin login HTTP, sin modificar claves y sin publicar passwords/hashes. No se duplica la clave en documentación. Ver `credenciales_demo_verificadas.json`.
- **Navegación revalidada:** login con usuario desechable, `/citas`, 1.122 resultados y tabla cargada. Se cerró sesión, la pestaña y el laboratorio temporal.
- **Respaldos duraderos revalidados:** los 11 archivos principales conservan sus hashes y siguen fuera de OneDrive y Temp. Ver `respaldo_revalidado_continuacion.json`.
- **Originales revalidados al cierre:** cero cambios en 302 archivos originales, excluyendo el plan y metadata Git; TAR de los tres volúmenes originales con los mismos SHA-256 iniciales. Ver `originales_verificados_cierre.json`.

## Línea base congelada con fallos conocidos

| Área | Estado conocido antes de reestructurar |
|---|---|
| Backend completo | Error de colección por import de `app.modules.ia.cliente` inexistente en `tests/ia/conftest.py` |
| Diagnóstico backend excluyendo únicamente `tests/ia` | 218 aprobadas, 1 fallida; cobertura 87,12%; no sustituye la suite completa |
| Reasignación | Test interpreta respuesta paginada como lista; falla en `tests/test_reasignacion.py:52` |
| Frontend | 451 aprobadas, 56 fallidas; siete diagnósticos TypeScript que bloquean typecheck/build; lint no llega a completar ESLint |
| Seguridad dependencias frontend | Nueve vulnerabilidades moderadas, ninguna alta/crítica; no se aplicaron arreglos automáticos |
| Configuración nativa | `.env` backend apunta a otra base y rol `postgres`; no representa el volumen principal aprobado |
| Reproducibilidad | Node host 24 frente a Dockerfile Node 22; dependencias transitivas Python no totalmente fijadas |

Estos problemas **no se corrigieron ni se aprobaron funcionalmente** por cerrar fase 0. Se registran para una entrega de estabilización separada: acordar en fase 1 contratos y comportamiento esperado antes de decidir si cambia implementación, test o ambos. No eliminar pruebas ni bajar cobertura para conseguir un verde artificial.

No iniciar mudanza mecánica con esos fallos presentados como éxito; la referencia de regresión es la línea base detallada, con sus excepciones explícitas.

## Alcance preservado y recuperación

- Sin cambios en aplicaciones, datos, CSV, modelo, `.env`, Compose, migraciones o pruebas originales.
- `Skills` frontend/backend siguen vacías.
- No se arrancó el volumen original principal. Solo copias de auditoría restauradas/aisladas.
- Ningún volumen o recurso ajeno se eliminó. Los servicios temporales de esta continuación quedaron detenidos; Docker Desktop sigue disponible.
- No se realizaron commits automáticos. Las evidencias y el plan permanecen como cambios locales revisables.
- El punto de retorno es el snapshot Git más el ZIP privado, los TAR y los dumps/globals verificados. El modelo mantiene su hash inicial.
- Los archivos nuevos se respaldan en un ZIP de cierre **adicional**, sin sobrescribir los archivos ni las evidencias iniciales.

Respaldo privado duradero: `C:\Users\arami\AppData\Local\PrediCitasBackups\fase0-20261103-2200`. Sigue en el mismo equipo: se recomienda copia cifrada externa para cubrir pérdida del disco; no se configuró transferencia remota.

## Siguiente fase

**Fase 1: contratos y decisiones de arquitectura.** Preparar ADRs, inventario completo de endpoints/rutas/permisos, contratos IA/CSV/features, mapa de dependencias y plan de estabilización. Sigue siendo trabajo documental/de contratos, **sin mover las aplicaciones ni cambiar lógica**.

La fase 1 permanece pendiente en esta entrega; no se han creado sus contratos ni se ha ejecutado fase 2.
