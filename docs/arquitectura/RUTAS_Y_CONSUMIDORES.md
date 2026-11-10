# Rutas, permisos y consumidores actuales

Inventario de fase 1, 03/11/2026. A=ADMINISTRADOR, R=RECEPCION, T=TECNICO_IA. Fuente de verdad pública: snapshot y `docs/migracion/fase-01/endpoints_actuales.json` (55 operaciones). La matriz describe roles declarados; no sustituye pruebas RBAC.

## Rutas frontend reales

Entrada `src/main.tsx` → App → ranuras `modulos/*/rutas.tsx`, menú en `modulos/*/menu.ts`. Inventario AST TypeScript: `docs/migracion/fase-01/frontend_rutas_menu_alcance.json`.

| Ruta de módulo | Roles | Pantalla | Menú |
|---|---|---|---|
| `/login` | Público | Login | No |
| `/mi-cuenta` | A/R/T | MiCuenta | Mi cuenta |
| `/usuarios` | A | Usuarios y formularios/modales | Usuarios |
| `/citas` | A/R/T | Bandeja | Citas |
| `/citas/nueva` | A/R | Registrar cita ya agendada | Botón en bandeja |
| `/citas/importar` | A/R | Importar | Importar CSV |
| `/citas/:id` | A/R/T | Detalle | Enlace desde bandeja |
| `/citas/:id/trazabilidad` | A/R/T | TrazabilidadCita | Enlace desde detalle |
| `/intervenciones` | A/R/T | Intervenciones | Intervenciones |
| `/intervenciones/:id` | A/R/T | Seguimiento | Desde historial |
| `/reportes/intervenciones` | A/R | Reporte REP-02 | Reporte de intervenciones |
| `/lista-espera` | A/R | ListaEspera | Lista de espera |
| `/cupos` | A/R | Cupos | Cupos liberados |
| `/cupos/:id` | A/R | DetalleCupo | Enlace desde cupos |
| `/reportes/reasignaciones` | A/R | Reporte REP-03 | Reporte de reasignaciones |

Son **15 rutas de módulos en modo no-test** y nueve entradas de menú productivas. `/prueba-ranura` y su menú existen **solo en MODE=test**, según el código actual: no es un módulo expuesto en producción que haya que retirar de nuevo.

Rutas de composición adicionales: `/` autenticada redirige por `inicioPorRol` (hoy `/citas` para todos); `/importar` redirige a `/citas/importar` y el destino vuelve a controlar permiso; `*` muestra página no encontrada. No hay `/panel` registrado actualmente ni ruta de módulo IA dedicada, aunque existan referencias/documentos de diseño.

El análisis de imports relativos desde entrada/ranuras no encontró dependencia activa hacia los **21 archivos de código** de `src/pages`, `src/auth`, `src/components`, `src/lib`. Es evidencia estática, no autorización para borrar: comprobar consumidores externos, tests directos y funcionalidad antigua antes de consolidar en fase 8. En especial `pages/ModeloIA.jsx` no es pantalla activa en este árbol.

## Matriz de consumidores: todas las familias de operaciones públicas

Cada fila cubre las rutas indicadas del inventario, sin asumir que clientes externos no listados no existan. Las rutas parametrizadas conservan su nombre real en el JSON; aquí `{id}` abrevia el identificador correspondiente.

| API actual | Consumidor modular actual | Consumidores antiguos / otros | Observación |
|---|---|---|---|
| POST `/auth/login`, GET `/auth/me`, POST `/auth/logout` | `nucleo/auth/AuthProvider.tsx`, sesión/inactividad | `auth/AuthContext.jsx`, clientes API | Form URL encoded; sesión/401 tardío a preservar |
| POST `/auth/renovar` | `nucleo/sesion/controlador.ts` | Cliente API | Token con misma política de sesión |
| POST `/auth/cambiar-clave` | `modulos/sesion/MiCuenta.tsx` | Cliente API | JSON; no log de body |
| GET/POST `/usuarios` | Usuarios y FormularioUsuario | Cliente Admin | GET paginado, POST crea |
| GET/PATCH `/usuarios/{id}` | FormularioUsuario | Cliente Admin | Consulta/edición |
| POST `/usuarios/{id}/estado`, `/restablecer-acceso` | AccionesUsuario | Cliente Admin | Clave temporal una vez, no capturar respuesta en evidencia |
| GET `/citas`, `/citas/catalogos` | Bandeja, Registrar, filtros | pages/Citas y scripts | PaginaCitasOut y catálogos |
| POST `/citas` | Registrar | Cliente API | Incorpora cita externa, no agenda en HIS |
| POST `/citas/importar` | Importar | pages/Importar, seed/scripts | Multipart `archivo` y CSV canónico |
| GET `/citas/{id}` | Detalle, TrazabilidadCita | pages/CitaDetalle | Contiene historial/predicciones/cupo/intervenciones |
| POST `/citas/{id}/estado` | Detalle | pages/CitaDetalle | JSON y efectos según estado |
| POST `/citas/{id}/check-in` | Detalle | Cliente API | Observación de entrada no forma parte del DTO de salida actual |
| POST `/citas/{id}/prediccion` | Fallback de Detalle | Cliente API A/R | Mismo servicio que IA, distinto permiso |
| POST `/ia/predecir/{id}` | Detalle | pages/CitaDetalle | Fuente primaria de inferencia UI |
| POST `/ia/predecir-lote` | Sin acción dedicada en módulo actual | pages/Intervenciones y clientes técnicos | Endpoint vigente aunque no tenga pantalla modular específica |
| GET `/ia/predicciones/{id}` | Detalle usa proyección `/citas/{id}` | pages/CitaDetalle, clientes técnicos | Lista histórica sigue disponible sin IA externa |
| GET `/ia/metricas`, `/ia/dataset-resumen` | Sin ruta modular IA dedicada | pages/ModeloIA y clientes técnicos | No afirmar pantalla de técnico IA integrada |
| GET `/intervenciones` | Intervenciones, historial | Clientes API | PaginaIntervencionesOut y campos adicionales |
| GET `/intervenciones/elegibles`, `/plantillas` | Intervenciones/NuevaIntervencion para A/R | Clientes API | T puede leer módulo, no estas operaciones de escritura/preparación |
| POST `/intervenciones` | NuevaIntervencion | Clientes API | Ruta nueva, consentimiento/elegibilidad/catálogo |
| GET `/intervenciones/{id}` | Seguimiento | Clientes API | Lectura A/R/T |
| POST `/intervenciones/{id}/estado`, `/respuesta`, `/optout`, `/liberar-cupo` | Seguimiento | Clientes API | Acciones explícitas; respuesta POST no confirma cita automáticamente |
| GET `/citas/{id}/intervenciones` | Detalle usa respuesta compuesta de cita | Clientes legacy | Lista, no paginación nueva |
| POST `/citas/{id}/intervenciones` | Alias de alta | Pruebas de compatibilidad | Mismas reglas de alta que `POST /intervenciones`, con ID en la URL y HTTP 200. |
| PATCH `/intervenciones/{id}` | Fuera del flujo modular habitual | Pruebas legacy | Ruta de respuesta histórica con efectos propios. |
| GET/POST `/lista-espera`, PATCH `/lista-espera/{id}` | ListaEspera | pages/Reasignacion para creación | API GET A/R/T, UI solo A/R; no revocar T en API por mover carpetas |
| GET `/cupos`, `/cupos/{id}` | Cupos, DetalleCupo | Clientes API | PaginaCupoOut y CupoDetalleOut |
| GET `/cupos-liberados`, `/cupos-liberados/{id}` | No consumidor modular principal | pages/Reasignacion, pruebas/cliente API | Rutas vigentes, GET paginado |
| GET `/cupos/{id}/candidatos` | DetalleCupo | Cliente API | Lista directa |
| GET `/cupos-liberados/{id}/candidatos` | No consumidor modular principal | pages/Reasignacion, test_reasignacion | Objeto PropuestaCandidatosOut |
| POST `/cupos/{id}/reasignar` | DetalleCupo | Cliente API | Confirmación humana |
| POST `/cupos-liberados/{id}/reasignar` | No consumidor modular principal | pages/Reasignacion, test_reasignacion | Misma operación, ruta distinta |
| POST `/cupos/{id}/ofertas`, `/ofertas/rechazo`, `/ofertas/desistimiento` | DetalleCupo | Cliente API | Mutaciones hoy en router; deuda de transacción/trazabilidad |
| GET `/reportes/rep-02`, `/rep-03` | Reporte de cada módulo y sus adaptadores de descarga | Clientes API | Filtros `formato` JSON/CSV/XLSX; limitaciones en COMPATIBILIDAD.md |
| GET `/reportes/intervenciones`, `/reasignaciones` | UI homónima usa **rep-02/rep-03**, no estos alias HTTP | Clientes API potenciales | Alias intervenciones tiene llamada estáticamente incompatible |
| GET `/health` | Healthcheck/manual/scripts | Operación | No depende actualmente de BD |

No confundir una ruta del navegador `/reportes/intervenciones` con una llamada API del mismo texto: la pantalla pide `/reportes/rep-02`. Los 165 literales extraídos en `referencias_frontend.json` mezclan navegación, consultas, paths dinámicos y legacy; no se presentan como 165 peticiones verificadas.

## Matriz entre aplicaciones objetivo

| Productor → consumidor | Contrato | Implementación |
|---|---|---|
| Navegador → backend | OpenAPI actual + formas HTTP/errores/descargas documentadas | Ya existe, preservar |
| Backend → IA | OpenAPI objetivo v1 + schemas + correlación | Pendiente fases 5–7 |
| IA → backend | Predicción, métricas y metadata del dataset sin BD | Pendiente fases 5–7 |
| Generador/operador → importador backend | CSV operacional, sin target autoritativo | Existe formato; rutas/generador se ordenan fases 3/6 |
| Exportador backend → entrenamiento IA | Snapshot sintético versionado, linaje manifiesto | Pendiente fase 6 |
| Pipeline → serving IA | Registry, manifiestos, puntero activo/hashes | Pendiente fase 6 |

No compartir repositorios ORM o paquetes Python de apps distintas como «contrato común». Los tipos UI pueden derivarse más adelante de OpenAPI, pero ningún archivo generado debe sustituir revisión de diferencias o pruebas reales.
