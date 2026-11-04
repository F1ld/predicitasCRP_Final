# Endpoints y permisos actuales

Generado de AST y contrastado contra OpenAPI de fase 0. A=Administrador, R=Recepción, T=Técnico IA. Los roles reflejan dependencias declaradas, no una nueva certificación RBAC. Docs/Redoc/OpenAPI son rutas técnicas públicas adicionales fuera de este conteo.

| Método | Ruta | Roles | Entrada | Respuesta declarada | Fuente |
|---|---|---|---|---|---|
| POST | `/auth/cambiar-clave` | A,R,T | application/json | TokenOut | `backend-predicitas/app/modules/auth/router.py:48` |
| POST | `/auth/login` | Público | application/x-www-form-urlencoded | TokenOut | `backend-predicitas/app/modules/auth/router.py:17` |
| POST | `/auth/logout` | A,R,T | query/path o sin body | sin contenido | `backend-predicitas/app/modules/auth/router.py:34` |
| GET | `/auth/me` | A,R,T | query/path o sin body | UsuarioOut | `backend-predicitas/app/modules/auth/router.py:28` |
| POST | `/auth/renovar` | A,R,T | query/path o sin body | TokenOut | `backend-predicitas/app/modules/auth/router.py:41` |
| GET | `/citas` | A,R,T | query/path o sin body | PaginaCitasOut | `backend-predicitas/app/modules/citas/router.py:36` |
| POST | `/citas` | A,R | application/json | CitaDetalleOut | `backend-predicitas/app/modules/citas/router.py:59` |
| GET | `/citas/catalogos` | A,R,T | query/path o sin body | CatalogosOut | `backend-predicitas/app/modules/citas/router.py:71` |
| POST | `/citas/importar` | A,R | multipart/form-data | ResultadoImportacionOut | `backend-predicitas/app/modules/citas/router.py:77` |
| GET | `/citas/{id_cita}` | A,R,T | query/path o sin body | CitaDetalleOut | `backend-predicitas/app/modules/citas/router.py:109` |
| POST | `/citas/{id_cita}/check-in` | A,R | application/json | CheckInOut | `backend-predicitas/app/modules/citas/router.py:128` |
| POST | `/citas/{id_cita}/estado` | A,R | application/json | CitaDetalleOut | `backend-predicitas/app/modules/citas/router.py:115` |
| POST | `/citas/{id_cita}/prediccion` | A,R | query/path o sin body | objeto | `backend-predicitas/app/modules/citas/router.py:142` |
| GET | `/ia/dataset-resumen` | A,R,T | query/path o sin body | DatasetResumenOut | `backend-predicitas/app/modules/ia/router.py:59` |
| GET | `/ia/metricas` | A,R,T | query/path o sin body | MetricasModeloOut | `backend-predicitas/app/modules/ia/router.py:52` |
| POST | `/ia/predecir-lote` | A,R,T | query/path o sin body | ResultadoPrediccionLoteOut | `backend-predicitas/app/modules/ia/router.py:33` |
| POST | `/ia/predecir/{id_cita}` | A,R,T | query/path o sin body | PrediccionIAOut | `backend-predicitas/app/modules/ia/router.py:23` |
| GET | `/ia/predicciones/{id_cita}` | A,R,T | query/path o sin body | array | `backend-predicitas/app/modules/ia/router.py:43` |
| GET | `/citas/{id_cita}/intervenciones` | A,R,T | query/path o sin body | array | `backend-predicitas/app/modules/intervenciones/router.py:273` |
| POST | `/citas/{id_cita}/intervenciones` | A,R | application/json | app__modules__intervenciones__schemas__IntervencionOut | `backend-predicitas/app/modules/intervenciones/router.py:282` |
| GET | `/intervenciones` | A,R,T | query/path o sin body | PaginaIntervencionesOut | `backend-predicitas/app/modules/intervenciones/router.py:78` |
| POST | `/intervenciones` | A,R | application/json | app__modules__intervenciones__schemas__IntervencionOut | `backend-predicitas/app/modules/intervenciones/router.py:137` |
| GET | `/intervenciones/elegibles` | A,R | query/path o sin body | PaginaElegiblesOut | `backend-predicitas/app/modules/intervenciones/router.py:49` |
| GET | `/intervenciones/plantillas` | A,R | query/path o sin body | array | `backend-predicitas/app/modules/intervenciones/router.py:41` |
| GET | `/intervenciones/{id_intervencion}` | A,R,T | query/path o sin body | app__modules__intervenciones__schemas__IntervencionOut | `backend-predicitas/app/modules/intervenciones/router.py:241` |
| PATCH | `/intervenciones/{id_intervencion}` | A,R | application/json | app__modules__intervenciones__schemas__IntervencionOut | `backend-predicitas/app/modules/intervenciones/router.py:253` |
| POST | `/intervenciones/{id_intervencion}/estado` | A,R | application/json | app__modules__intervenciones__schemas__IntervencionOut | `backend-predicitas/app/modules/intervenciones/router.py:164` |
| POST | `/intervenciones/{id_intervencion}/liberar-cupo` | A,R | application/json | CupoLiberadoOut | `backend-predicitas/app/modules/intervenciones/router.py:221` |
| POST | `/intervenciones/{id_intervencion}/optout` | A,R | query/path o sin body | app__modules__intervenciones__schemas__IntervencionOut | `backend-predicitas/app/modules/intervenciones/router.py:205` |
| POST | `/intervenciones/{id_intervencion}/respuesta` | A,R | application/json | app__modules__intervenciones__schemas__IntervencionOut | `backend-predicitas/app/modules/intervenciones/router.py:184` |
| GET | `/cupos` | A,R,T | query/path o sin body | PaginaCupoOut | `backend-predicitas/app/modules/lista_espera/router.py:124` |
| GET | `/cupos-liberados` | A,R,T | query/path o sin body | PaginaCupoOut | `backend-predicitas/app/modules/lista_espera/router.py:138` |
| GET | `/cupos-liberados/{id_cupo}` | A,R,T | query/path o sin body | CupoDetalleOut | `backend-predicitas/app/modules/lista_espera/router.py:161` |
| GET | `/cupos-liberados/{id_cupo}/candidatos` | A,R,T | query/path o sin body | PropuestaCandidatosOut | `backend-predicitas/app/modules/lista_espera/router.py:180` |
| POST | `/cupos-liberados/{id_cupo}/reasignar` | A,R | application/json | app__modules__lista_espera__schemas__ReasignacionOut | `backend-predicitas/app/modules/lista_espera/router.py:200` |
| GET | `/cupos/{id_cupo}` | A,R,T | query/path o sin body | CupoDetalleOut | `backend-predicitas/app/modules/lista_espera/router.py:152` |
| GET | `/cupos/{id_cupo}/candidatos` | A,R,T | query/path o sin body | array | `backend-predicitas/app/modules/lista_espera/router.py:170` |
| POST | `/cupos/{id_cupo}/ofertas` | A,R | application/json | CupoDetalleOut | `backend-predicitas/app/modules/lista_espera/router.py:211` |
| POST | `/cupos/{id_cupo}/ofertas/desistimiento` | A,R | query/path o sin body | CupoDetalleOut | `backend-predicitas/app/modules/lista_espera/router.py:249` |
| POST | `/cupos/{id_cupo}/ofertas/rechazo` | A,R | query/path o sin body | CupoDetalleOut | `backend-predicitas/app/modules/lista_espera/router.py:233` |
| POST | `/cupos/{id_cupo}/reasignar` | A,R | application/json | app__modules__lista_espera__schemas__ReasignacionOut | `backend-predicitas/app/modules/lista_espera/router.py:189` |
| GET | `/lista-espera` | A,R,T | query/path o sin body | PaginaCandidatoOut | `backend-predicitas/app/modules/lista_espera/router.py:34` |
| POST | `/lista-espera` | A,R | application/json | CandidatoOut | `backend-predicitas/app/modules/lista_espera/router.py:66` |
| PATCH | `/lista-espera/{id_candidato}` | A,R | application/json | CandidatoOut | `backend-predicitas/app/modules/lista_espera/router.py:76` |
| GET | `/reportes/intervenciones` | A,R | query/path o sin body | Rep02Out | `backend-predicitas/app/modules/reportes/router.py:115` |
| GET | `/reportes/reasignaciones` | A,R | query/path o sin body | Rep03Out | `backend-predicitas/app/modules/reportes/router.py:138` |
| GET | `/reportes/rep-02` | A,R | query/path o sin body | Rep02Out | `backend-predicitas/app/modules/reportes/router.py:20` |
| GET | `/reportes/rep-03` | A,R | query/path o sin body | Rep03Out | `backend-predicitas/app/modules/reportes/router.py:87` |
| GET | `/health` | Público | query/path o sin body | objeto | `backend-predicitas/app/main.py:43` |
| GET | `/usuarios` | A | query/path o sin body | PaginaUsuariosOut | `backend-predicitas/app/modules/usuarios/router.py:20` |
| POST | `/usuarios` | A | application/json | UsuarioOut | `backend-predicitas/app/modules/usuarios/router.py:35` |
| GET | `/usuarios/{id_usuario}` | A | query/path o sin body | UsuarioOut | `backend-predicitas/app/modules/usuarios/router.py:42` |
| PATCH | `/usuarios/{id_usuario}` | A | application/json | UsuarioOut | `backend-predicitas/app/modules/usuarios/router.py:48` |
| POST | `/usuarios/{id_usuario}/estado` | A | application/json | UsuarioOut | `backend-predicitas/app/modules/usuarios/router.py:55` |
| POST | `/usuarios/{id_usuario}/restablecer-acceso` | A | query/path o sin body | ClaveTemporalOut | `backend-predicitas/app/modules/usuarios/router.py:62` |
