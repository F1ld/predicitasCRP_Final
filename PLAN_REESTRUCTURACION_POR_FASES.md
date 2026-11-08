# Plan integral de reestructuración por fases — PrediCitas CRP

## 0. Propósito, alcance y estado real

**Arquitectura objetivo:** monorepositorio con frontend independiente, backend monolítico modular por capas, servicio de inferencia IA independiente y PostgreSQL administrado por el backend.

Este documento es un plan ejecutable y una bitácora de seguimiento. **Su creación no significa que la migración esté aplicada, que las pruebas pasen o que el arranque objetivo exista actualmente.** Las rutas y comandos marcados como objetivo deben implementarse en la fase indicada antes de usarse.

### Entrega de planificación

- [x] Inspeccionar estructura, configuración y dependencias relevantes del proyecto.
- [x] Redactar este plan sin modificar el funcionamiento de las aplicaciones.
- [x] Crear `backend-predicitas/Skills/` y `frontend-predicitas/Skills/` vacías; verificar su existencia al finalizar la entrega.
- [ ] Ejecutar las fases de reestructuración.

Las carpetas `Skills` no contienen código, instrucciones ni archivos `.gitkeep`. Al mover las aplicaciones deberán conservarse como `apps/backend/Skills/` y `apps/frontend/Skills/`. Git no versiona directorios vacíos: los futuros scripts de preparación deben recrearlos, sin añadir contenido.

### Reglas de ejecución

1. No ejecutar todas las fases como una mudanza masiva. Cerrar y validar cada una antes de continuar.
2. Separar movimientos mecánicos, cambios de lógica y cambios de esquema en entregas distintas.
3. No borrar CSV, modelos, capturas, configuraciones, documentación ni código antiguo sin inventario y revisión de consumidores.
4. No usar `docker compose down -v`, `alembic downgrade base`, eliminación de volúmenes o reinicialización de la BD como procedimiento de migración.
5. Mantener endpoints, contratos públicos y comportamiento observable salvo cambio explícitamente aprobado.
6. Conservar el historial de Alembic; una mudanza de carpetas no requiere regenerar tablas.
7. No introducir simultáneamente actualizaciones de frameworks, librerías o algoritmo del modelo.
8. Ninguna fase se completa solo porque la aplicación compila: debe aportar evidencia funcional.
9. Si aparece una diferencia entre documentación y código, registrarla y decidirla; no cambiar silenciosamente las reglas del piloto.
10. Las fases que descubran defectos previos deben distinguirlos de regresiones. Un defecto crítico no queda aprobado por ser previo.

## 1. Diagnóstico de partida verificado

| Área | Situación observada | Implicación para el plan |
|---|---|---|
| Directorio raíz | `backend-predicitas/`, `frontend-predicitas/`, Compose, `.env`, documentos y un CSV | Ordenar aplicaciones, datos, infraestructura y documentación sin perder archivos |
| Control de versiones | La raíz de esta sesión no se identifica como repositorio Git | Confirmar repositorios internos y acordar estrategia antes de moverlos |
| Backend | FastAPI con `app/main.py`, `app/core/` y ocho módulos funcionales | Mantener un backend único; fortalecer encapsulación, no convertir cada módulo en microservicio |
| Persistencia | PostgreSQL 16, SQLAlchemy, Alembic y nueve tablas de negocio | Preservar nombres físicos, claves, secuencias, políticas y triggers |
| Migraciones | Revisiones `2cfdcb7d3da2`, `m00_002_rol_operativo`, `m01_001_indices_auditoria` | Conservar cadena de revisiones y comprobar el head real en fase 0 |
| Roles BD | `predicitas_owner` para administración y `predicitas_app` para operación | El backend operativo no debe recibir credenciales de propietario |
| IA | LightGBM local importado desde `app/modules/ia/service.py` | Hay que crear un cliente HTTP real; configurar `IA_URL` no extrae la IA por sí solo |
| Modelo | Existe `app/modules/ia/artifacts/modelo_predicitas_v1.joblib` | Respaldar y verificar compatibilidad antes de mover o sustituir |
| Entrenamiento | `obtener_artefacto_modelo()` entrena si falta el archivo | Eliminar este comportamiento del camino de inferencia mediante una fase explícita |
| Dataset | Generador en `citas/synthetic.py`; predictor puede consultar BD o generar sintéticos | Definir procedencia inequívoca y evitar fallback silencioso a otro dataset |
| CSV | Dos copias de `citas_para_importar_variado.csv` y ejemplos en `backend/data/` | Clasificar, verificar hashes y definir una ubicación canónica |
| Frontend | React/TypeScript, Vite; `modulos/` y `nucleo/` junto a `pages/`, `auth/`, `components/`, `lib/` | Revisar referencias antes de consolidar las dos estructuras |
| Rutas frontend | `App.tsx` descubre `modulos/*/rutas.tsx`; existe `prueba-ranura` usado por tests | No retirar la ranura sin sustituir su papel en las pruebas |
| Acoplamiento | Hay imports cruzados de modelos/repositorios y de `citas.router.reloj` | Formalizar contratos internos y mover dependencias técnicas fuera de routers |
| Escrituras | Citas e Intervenciones modifican citas y crean cupos; algunos routers hacen commits | Centralizar propietarios y transacciones sin duplicar historial/auditoría |
| Compose | Uno raíz con nombre `predicitas-crp` y otro backend con `predicitas-backend` | Pueden existir volúmenes diferentes; no asumir que ambos contienen los mismos datos |
| Configuración | Varios `.env`, referencias a contratos no localizados y puertos BD distintos | Crear una matriz de configuración y una única entrada Compose oficial |
| Pruebas | pytest con BD y cobertura mínima 75%; Vitest con mínimo 75% de líneas | Aislar la BD de pruebas y mantener umbrales durante la migración |
| Entorno local | Windows, ruta con espacios y carpeta bajo OneDrive | Considerar PowerShell, CRLF, permisos, sincronización y rutas montadas |

### Evidencias de archivos al redactar el plan

Las copias raíz y `backend-predicitas/data/citas_para_importar_variado.csv` tienen el mismo SHA-256:

`8EEBF37844262AC33EBBE2453E62EDC321AE67A2BCF0A9FDD43B6761FA328282`

El artefacto IA existente tiene SHA-256:

`89297942F603DC040C9954D534AE6DAE97590203F0345925C12FC4E0A90E9074`

Recalcular antes de migrar: estos valores describen esta inspección, no futuras modificaciones.

## 2. Arquitectura objetivo y límites

```text
Navegador
   │ HTTP + JWT (dirección visible desde el equipo)
   ▼
Frontend React ───────────────► Backend FastAPI modular
                                      │
                                      ├── SQL ─────► PostgreSQL
                                      │
                                      └── HTTP interno + clave ──► IA / inferencia
                                                                      │ lectura
                                                                      ▼
                                                               Artefacto versionado

Proceso manual de preparación/entrenamiento IA
   Dataset explícito ─► validación ─► entrenamiento ─► candidato ─► promoción

Migrador y seed: procesos puntuales; no son servidores permanentes.
```

### Decisiones obligatorias

- El navegador solo consume la API del backend; nunca PostgreSQL ni la API interna de IA.
- Los módulos de negocio del backend se llaman en memoria, mediante contratos; no mediante HTTP entre ellos.
- La IA no recibe JWT de pacientes/usuarios, no conoce tablas operativas y no tiene `DATABASE_URL`.
- La IA calcula; el backend autoriza, decide elegibilidad, persiste predicciones y audita.
- La IA no modifica estados de citas, envía mensajes ni reasigna cupos.
- Los datos del negocio viven en PostgreSQL; un CSV no se convierte en una segunda base operacional.
- El piloto sigue usando datos sintéticos y seudonimizados. No incorporar datos personales reales, teléfonos, DNI o diagnósticos por reorganizar el almacenamiento; cualquier uso real requiere autorización y un diseño de privacidad independiente.
- La caída de IA no bloquea login, consulta, registro, seguimiento ni atención de citas.
- Entrenamiento e inferencia son procesos separados, aunque compartan código dentro de `apps/ia/`.
- No incorporar Kubernetes, Redis, Kafka, Celery o microservicios adicionales como requisito de esta reorganización.
- No activar integraciones reales de WhatsApp/SMS/llamadas ni modificar consentimiento, opt-out o confirmación humana como parte de la extracción técnica.
- Docker Compose es la vía local oficial. La ejecución nativa es una alternativa documentada y probada.
- Los proyectos Python se ejecutan en entornos/contenedores distintos: ambos pueden usar un paquete local llamado `app` sin mezclar sus `PYTHONPATH`.

## 3. Árbol final propuesto

El árbol es objetivo, no un listado de directorios ya creados. Se crearán carpetas cuando tengan una responsabilidad efectiva; `Skills/` es la excepción solicitada.

```text
Proyecto_PredicitasCRP/
├── apps/
│   ├── frontend/
│   │   ├── Skills/                         # Vacía
│   │   ├── src/
│   │   │   ├── modulos/                    # Citas, sesión, usuarios, intervenciones, lista-espera, IA
│   │   │   ├── nucleo/                     # API, sesión, layout y UI compartida
│   │   │   ├── pruebas/                    # Setup y soporte de pruebas unitarias
│   │   │   ├── assets/
│   │   │   ├── App.tsx
│   │   │   └── main.tsx
│   │   ├── public/                         # Solo recursos públicos, nunca datasets o secretos
│   │   ├── tests/                          # Tests de navegador/diseño; fixtures propios si son exclusivos
│   │   ├── package.json
│   │   ├── package-lock.json
│   │   ├── vite.config.ts
│   │   ├── tsconfig.json
│   │   ├── Dockerfile
│   │   └── .env.example
│   ├── backend/
│   │   ├── Skills/                         # Vacía
│   │   ├── app/
│   │   │   ├── main.py                     # Composición de la aplicación
│   │   │   ├── bootstrap/                  # Registro ORM y cableado de adaptadores
│   │   │   ├── core/                       # Configuración, errores, BD, reloj, seguridad técnica
│   │   │   ├── workflows/                  # Casos de uso que coordinan varios módulos
│   │   │   └── modules/
│   │   │       ├── auth/
│   │   │       ├── usuarios/
│   │   │       ├── citas/
│   │   │       ├── ia/                     # Integración HTTP y predicciones persistidas, no LightGBM
│   │   │       ├── intervenciones/
│   │   │       ├── lista_espera/
│   │   │       ├── reportes/
│   │   │       └── auditoria/
│   │   ├── migrations/                     # Único historial Alembic del negocio
│   │   ├── scripts/                        # Seed, chequeo BD y exportación controlada
│   │   ├── tests/                          # Unitarias, integración, BD y arquitectura
│   │   ├── requirements.txt
│   │   ├── requirements-dev.txt            # Separación de tests si se implementa
│   │   ├── alembic.ini
│   │   ├── pytest.ini
│   │   ├── Dockerfile
│   │   └── .env.example
│   └── ia/
│       ├── app/
│       │   ├── main.py                     # Solo API de inferencia/metadatos
│       │   ├── api/
│       │   ├── core/                       # Configuración, autenticación interna y logging
│       │   ├── datasets/                   # Generación, validación y lectura; no los CSV físicos
│       │   ├── features/                   # Transformaciones canónicas pre-cita
│       │   ├── training/                   # Baseline, LightGBM, evaluación, manifest y promoción
│       │   └── inference/                  # Carga y uso del artefacto, sin entrenar
│       ├── scripts/                        # Comandos generar, entrenar, verificar y promover
│       ├── tests/
│       ├── requirements.txt
│       ├── requirements-dev.txt
│       ├── Dockerfile
│       └── .env.example
├── contracts/
│   ├── backend/                           # Snapshot OpenAPI + compatibilidad pública
│   ├── ia/                                # OpenAPI interno y ejemplos v1
│   └── data/                              # Esquemas CSV, features y manifiestos
├── data/
│   ├── README.md
│   ├── samples/                           # Ejemplos sintéticos revisados y versionables
│   │   └── importacion/
│   ├── fixtures/                          # Casos sintéticos compartidos deterministas
│   ├── raw/                               # Snapshots de entrada inmutables por versión
│   ├── processed/                         # Train/val/test y transformaciones reproducibles
│   └── manifests/                         # Linaje, hashes, semilla, fecha y esquema
├── artifacts/
│   ├── models/                            # Modelos por versión; no dentro del código
│   └── reports/                           # Métricas/equidad/calidad por ejecución IA
├── runtime/
│   ├── imports/                           # Solo si se aprueba retener archivos subidos
│   ├── exports/                           # Exportaciones persistidas por pedido explícito
│   ├── tmp/                               # Temporales con limpieza segura
│   └── test-results/                      # Cobertura, capturas y resultados generados
├── backups/                               # Local, ignorado; copia adicional fuera de esta carpeta
├── infrastructure/
│   ├── database/
│   │   └── init/                          # Creación inicial del rol operativo
│   └── docker/                            # Overrides auxiliares si realmente hacen falta
├── scripts/
│   ├── bootstrap.ps1                      # A implementar en fase 9
│   ├── smoke.ps1                          # A implementar en fase 10
│   └── README.md
├── tests/
│   ├── contracts/                         # Compatibilidad backend/IA/frontend
│   └── e2e/                               # Recorrido integrado completo
├── docs/
│   ├── arquitectura/
│   ├── requisitos/
│   ├── operacion/
│   ├── pruebas/
│   ├── migracion/                         # Evidencias y decisiones por fase
│   └── historico/                         # Informes previos preservados y fechados
├── PLAN_REESTRUCTURACION_POR_FASES.md        # Mantener aquí como índice/bitácora de la migración
├── compose.yaml                           # Única entrada oficial local
├── .env.example                           # Variables de orquestación, sin secretos reales
├── .gitignore
├── .gitattributes
└── README.md                              # Inicio rápido vigente y enlaces
```

### Organización interna de módulos backend

Mantener inicialmente los nombres actuales `router.py`, `schemas.py`, `service.py`, `repository.py`, `models.py`, `reglas.py`. Añadir `public.py`/contratos de operaciones donde haya consumidores externos al módulo. No generar cinco subcarpetas por módulo por formalidad.

- **Router:** protocolo HTTP, autorización y adaptación de entrada/salida. No SQL ni commits.
- **Servicio/caso de uso:** coordinación, políticas y transacción del caso de uso de nivel superior.
- **Reglas:** decisiones de negocio puras cuando sea posible; sin FastAPI ni conexiones externas.
- **Repositorio:** persistencia de entidades propias; `flush()` permitido, no commits ocultos.
- **Modelos:** representación ORM interna; no respuesta pública ni API entre aplicaciones.
- **Contrato público:** operaciones/consultas y DTO estables; no exportar `repository` entero.
- **Workflow:** operación que coordina Citas, Intervenciones y/o Lista de Espera en una sesión y transacción.

Las consultas de lectura compuestas pueden tener adaptadores explícitos de reporting. La excepción no autoriza escrituras en tablas ajenas ni imports circulares entre módulos.

## 4. Mapa de movimientos y responsabilidades

| Origen actual | Destino objetivo | Tratamiento |
|---|---|---|
| `backend-predicitas/` | `apps/backend/` | Mover mecánicamente conservando imports `app.*` y tests; excluir después solo lo extraído y validado |
| `frontend-predicitas/` | `apps/frontend/` | Mover conservando configuración y lockfile; consolidar interiores en otra fase |
| `backend-predicitas/Skills/` | `apps/backend/Skills/` | Mantener vacía |
| `frontend-predicitas/Skills/` | `apps/frontend/Skills/` | Mantener vacía |
| `backend/db/init/` | `infrastructure/database/init/` | Ajustar montaje Compose; preservar LF y comportamiento |
| `backend/db/README.md` y diseño SQL | `docs/arquitectura/` o `docs/operacion/` | Clasificar; Alembic continúa como fuente ejecutable del esquema |
| `backend/migrations/` y `alembic.ini` | Dentro de `apps/backend/` | No reescribir IDs ni nombres físicos |
| `backend/app/core/models.py` | `apps/backend/app/bootstrap/models.py` | Registro ORM, coordinado con `main.py`, Alembic, scripts y tests |
| `backend/app/modules/ia/predictor.py` | Responsabilidades dentro de `apps/ia/app/` | Extraer, no copiar como segunda implementación permanente |
| `backend/app/modules/citas/synthetic.py` | `apps/ia/app/datasets/` | Generador sintético único; seed backend pasa a consumir CSV explícito |
| Modelo `.joblib` actual | `artifacts/models/legacy-import/` | Guardar bytes y hash; promover solo tras verificación |
| CSV variado raíz y backend | `data/samples/importacion/citas_para_importar_variado.csv` | Hashes iguales al inspeccionar; retirar duplicado solo tras actualizar consumidores |
| `backend/data/citas_demo.csv` | `data/samples/importacion/citas_demo.csv` | Documentar que puede contener filas inválidas intencionadas |
| `frontend/tests/fixtures/*.csv` | Permanecen inicialmente en tests frontend | Promover a `data/fixtures/` solo si se comparten; conservar identidad por hash |
| Documentos Markdown raíz | `docs/` según categoría | Mantener informes históricos; actualizar enlaces y un índice |
| Dos Compose existentes | `compose.yaml` raíz | Unificar después de fijar volumen; archivar descripción previa sin dejar dos entradas ambiguas |
| Resultados/capturas existentes | `docs/pruebas/` si son evidencia curada | Nueva salida automática a `runtime/test-results/`, no reescribir evidencia antigua |

Las rutas `backend/...` y `frontend/...` abreviadas en esta tabla representan las carpetas actuales o sus equivalentes movidas según la fase. Registrar cada movimiento real con ruta completa en la evidencia.

### Propietario lógico de cada tabla

| Módulo | Entidades/escrituras propias |
|---|---|
| Usuarios | `usuarios`; Auth usa operaciones internas aprobadas para credenciales, bloqueo y sesión |
| Citas | `citas`, `historial_estados_cita`; incluye check-in y desenlace |
| IA backend | `predicciones_ia`, snapshots y trazabilidad de inferencia |
| Intervenciones | `intervenciones`, consentimiento, opt-out y respuestas |
| Lista de espera | `lista_espera`, `cupos_liberados`, `reasignaciones` |
| Auditoría | `auditoria_eventos` mediante append público, sin commit propio |
| Reportes | Lectura transversal explícita; ninguna entidad operativa propia |

Mover `Usuario` de Auth a Usuarios requiere actualizar imports y registro ORM conjuntamente, manteniendo la tabla `usuarios`. Auth y Usuarios forman un área de identidad y acceso; evitar que Usuarios siga importando repositorios privados de Auth. Si esta separación crea ciclos, resolver con contratos y cableado en bootstrap, no con imports tardíos como solución permanente.

## 5. Política de CSV, datasets, artefactos y archivos

### 5.1 Clasificación y versionado

| Tipo | Ubicación | ¿Versionar en Git? | Consumidor |
|---|---|---|---|
| CSV sintético pequeño de demostración | `data/samples/importacion/` | Sí, tras revisión | Persona que importa desde UI/API |
| Fixture determinista compartido | `data/fixtures/` | Sí si es pequeño | Tests de integración/E2E |
| Fixture exclusivo unitario | Junto al test de su aplicación | Sí si es pequeño | Solo ese test |
| Dataset bruto de entrenamiento | `data/raw/<dataset_version>/` | No por defecto; publicar paquete reproducible aparte | Preparación IA |
| Train/val/test | `data/processed/<dataset_version>/` | No por defecto | Entrenamiento/evaluación |
| Manifiesto sin datos sensibles | `data/manifests/` | Sí si es una versión aprobada | Auditoría y reproducción |
| Modelo Joblib | `artifacts/models/<model_version>/` | No por defecto; conservar entrega/backup con hash | Inferencia |
| Métricas y calidad | `artifacts/reports/<run_id>/` | Solo resumen curado en docs | Técnico IA |
| Upload recibido | En memoria como hoy; opcional `runtime/imports/<import_id>/` | No | Backend |
| CSV/Excel de descarga | Streaming como hoy; opcional `runtime/exports/` | No | Backend/usuario |
| Dump BD | `backups/<fecha>/` y copia externa | Nunca | Administrador local |
| Datos internos de PostgreSQL | Volumen Docker nombrado | Nunca | PostgreSQL |

No montar el volumen de PostgreSQL dentro de OneDrive ni guardar CSV/modelos en `frontend/public/`. Los directorios `data/raw`, `data/processed`, `artifacts`, `runtime` y `backups` deben tener reglas de ignore y exclusión de contextos Docker. Versionar únicamente excepciones explícitas revisadas, no subir toda la carpeta por accidente.

### 5.2 Contrato de importación operacional

Conservar el contrato actual de trece columnas del CSV de ejemplo:

```text
id_cita_externa,paciente_anon_id,sede,especialidad,medico,fecha_hora_cita,fecha_registro_cita,tipo_paciente,canal_origen,inasistencias_previas,reprogramaciones_prev,asistencias_previas,estado_actual
```

- UTF-8, admitir BOM como hace hoy `utf-8-sig`; separador coma y cabecera documentada.
- Mantener las reglas reales sobre celdas vacías/opcionales de `CitaImportIn`; no endurecerlas por una mudanza.
- Conservar límites actuales: 2 MiB y 5.000 filas, salvo cambio aprobado y probado.
- Fechas ISO 8601 con offset; reglas de negocio en `America/Lima`, no en la zona local de Windows.
- Respetar sede San Isidro, tres especialidades, días habilitados, duplicados y orden cronológico del historial.
- Mantener aceptación/rechazo parcial por validación y motivos por fila. La implementación actual valida antes de insertar; no asumir SAVEPOINT por fila porque lo diga un documento.
- `target_no_show` no se toma del CSV operacional: el backend lo deriva del desenlace permitido, y debe ser nulo en estados sin desenlace.
- Probar rollback ante errores de persistencia además de rechazos de validación; no prometer continuidad ante cualquier error SQL sin implementarla.
- Nunca usar el nombre original de upload como ruta de disco. Si se retiene, generar ID seguro, hash y metadatos, limitar tamaño y no permitir traversal.
- La reestructuración conserva el procesamiento en memoria por defecto; no introducir retención indefinida de archivos.
- Si se activa retención local: plazo inicial 7 días para imports/exports y 24 h para temporales, configurable, con limpieza restringida a esos directorios y trazabilidad. Backups quedan fuera de esa limpieza.
- Proteger exportaciones CSV/Excel frente a fórmulas de hojas de cálculo sin modificar el dato almacenado.

### 5.3 Dataset de entrenamiento y reproducibilidad

- Definir un esquema separado del CSV operacional. Puede incluir etiqueta y campos de trazabilidad, pero no utilizarlos como features.
- Registrar `dataset_version`, esquema, semilla, fecha de corte, origen, conteos, clases, SHA-256 y comando de generación/exportación.
- Mantener inicialmente la baseline de 1.000 históricos, semilla 42 y partición estratificada 70/15/15. No cambiar a 5.000 dentro de una extracción estructural.
- Separar fixtures históricos de fecha fija y demos operativas con fecha de referencia explícita. El seed actual usa por defecto `2026-10-29`; no asumir que sus citas seguirán siendo futuras en otro mes.
- Un dataset generado con distinta fecha de referencia recibe nueva versión/hash aunque conserve semilla.
- Congelar conjuntos de entrenamiento/validación/test; no ajustar umbrales repetidamente usando test reservado.
- Mantener control anti-leakage: identificadores, estado actual, target y otros campos post-cita no entran en X.
- La fuente de entrenamiento se elige explícitamente: sintético generado o snapshot exportado por el backend. No consultar BD y, si falla, entrenar silenciosamente con otros datos.
- El backend puede exportar un snapshot autorizado con un script local; IA lee el archivo, sin credenciales BD.
- Unificar el generador en IA. El seed backend consume un CSV operacional generado explícitamente, no importa código de `apps/ia`.
- Para generación de seed, emitir exactamente el esquema operacional; las etiquetas del entrenamiento van en un archivo separado. Conservar filas inválidas solo en fixtures de rechazo, no en el seed normal.

### 5.4 Artefactos IA

Cada versión promovida debe incluir modelo, manifiesto, métricas, esquema de features y dependencias usadas. El manifiesto registra al menos algoritmo, versión de modelo/dataset, fecha UTC, semilla, hash del modelo y dataset, Python/librerías, umbrales, métricas y rótulo de simulación.

- Servir únicamente artefactos internos confiables: `joblib.load` puede ejecutar código. No ofrecer upload arbitrario de modelos.
- Mantener candidato, activo y anterior; no sobrescribir el activo mientras se escribe un candidato.
- Usar promoción atómica y proceso documentado de reinicio/recarga. Montar el directorio padre de modelos, no únicamente un archivo que se sustituye por rename.
- El proceso de inferencia solo lee modelos; el proceso de entrenamiento escribe candidatos con permisos separados.
- Si no hay artefacto compatible, la IA no está lista y responde error controlado; nunca entrena en una petición.
- Cambiar features, preprocesado o umbrales exige nueva versión del modelo. La restricción actual `(id_cita, version_modelo)` impide distinguir dos modelos distintos con el mismo nombre.
- Al extraer, comparar predicciones del modelo antiguo y nuevo sobre un conjunto congelado, con tolerancia numérica acordada. Si hay reentrenamiento, tratarlo como nueva versión, no como movimiento equivalente.

## 6. Contratos de integración y tolerancia a fallos

### 6.1 API pública del backend

Inventariar OpenAPI completo antes de cambios y guardar snapshot en `contracts/backend/`. Preservar métodos, rutas, formularios de login, multipart de upload, respuestas, paginación, descargas y errores existentes.

En especial preservar las familias `/auth`, `/usuarios`, `/citas`, `/ia`, intervenciones, lista de espera/cupos y reportes; obtener los prefijos exactos de sus routers. No sustituirlas globalmente por `/api/v1` durante la mudanza.

La integración IA mantiene al menos los consumidores actuales:

- `POST /ia/predecir/{id_cita}`.
- `POST /ia/predecir-lote` y su parámetro `forzar`.
- `GET /ia/predicciones/{id_cita}`.
- `GET /ia/metricas`.
- `GET /ia/dataset-resumen`.
- `POST /citas/{id_cita}/prediccion`, que hoy llama al servicio local.

Las predicciones ya persistidas siguen consultables aunque la IA esté caída. El resumen de dataset combina explícitamente metadatos de IA y conteos operativos de BD; no inventa conteos cuando falta un componente. Preservar el DTO o versionar una extensión compatible.

### 6.2 API interna IA propuesta, a implementar en fase 5

| Endpoint objetivo | Función |
|---|---|
| `GET /health/live` | Proceso vivo, sin entrenar ni depender de BD |
| `GET /health/ready` | Modelo y manifiesto compatibles, cargados y utilizables |
| `GET /v1/model` | Versión, esquema, umbrales y metadata activa |
| `GET /v1/metrics` | Métricas aprobadas del artefacto activo |
| `GET /v1/dataset` | Metadatos del dataset, sin exponer filas |
| `POST /v1/predict` | Predicción individual sin persistir |
| `POST /v1/predict-batch` | Lote acotado, correlacionado por ID de petición |

Definir OpenAPI, ejemplos y pruebas antes de conectar el backend. Usar autenticación `X-IA-API-Key` en endpoints `/v1/*`; la clave nunca va al frontend ni a logs. Healthchecks internos no devuelven datos sensibles. El puerto IA se expone solo en loopback local, o se deja sin publicar cuando no sea necesario.

**Entrada de predicción:** versión de contrato, ID de correlación opaco y features crudas autorizadas: `especialidad`, `tipo_paciente`, `canal_origen`, `franja_horaria`, `dia_semana`, `antelacion_dias`, `inasistencias_previas`, `asistencias_previas`, `reprogramaciones_prev`. El esquema define tipo/rango/catálogos y tratamiento de nulos. No enviar nombres, teléfonos, DNI ni etiquetas de desenlace.

**Salida:** ID de correlación, versión de modelo y features, probabilidad finita entre 0 y 1, nivel, umbrales, features efectivas/snapshot, explicación y rótulo sintético. El backend verifica identidad de respuesta, versión, tipos y consistencia antes de guardar. Preservar explicabilidad y precisión numérica del contrato/columna actual.

**Fuente única de umbrales:** manifiesto del modelo. Mantener al principio BAJO `< 0.300`, MEDIO `0.300..0.450`, ALTO `> 0.450`; probar bordes exactos. La variable actual `IA_CORTE_MEDIO` no debe contradecir el modelo: deprecarla o validar igualdad, no clasificar dos veces con criterios distintos.

### 6.3 Lotes, concurrencia y errores

- Definir tamaño máximo del lote interno, timeout total y particionado backend. Fijarlos con medición local; no enviar 5.000 filas a un endpoint ilimitado ni mantener una transacción abierta durante toda la inferencia.
- Para esta migración, mantener el contrato de lote público síncrono con límite comprobado; colas/jobs quedan fuera. Si no cumple tiempo, aprobar un diseño de jobs antes de cambiar el contrato.
- Fijar la versión de modelo en toda la ejecución del lote. Si cambia o hay respuestas incompletas/duplicadas, abortar el guardado de esa ejecución con error controlado.
- Mantener atomicidad del guardado de un lote como comportamiento inicial. Si se desea éxito parcial, necesita contrato y pruebas específicas, no hacerlo implícitamente.
- Leer un snapshot, cerrar la transacción de lectura antes del HTTP externo y revalidar elegibilidad/features al guardar en una transacción corta. Si la cita cambió o pasó a ATENDIDA/NO_SHOW, no guardar una predicción obsoleta.
- Bloqueos o control de concurrencia solo en la etapa corta de validación/persistencia; orden consistente de locks en lote. Probar doble petición sobre `(id_cita, version_modelo)`.
- Timeouts de conexión/lectura explícitos. Sin reintentos infinitos; inicialmente sin retry automático o uno solo para errores transitorios seguros y dentro del presupuesto total.
- Timeout IA: backend devuelve error controlado, por ejemplo HTTP 504 con código estable. Servicio no disponible/modelo ausente: HTTP 503. Respuesta inválida/incompatible: HTTP 502. Documentar estos códigos nuevos y su representación en UI.
- No guardar riesgo cero o BAJO como fallback. No borrar una predicción previa al fallar una actualización.
- Los fallos técnicos se registran sin secretos; si se exige auditoría del fallo, usar una transacción explícita posterior al rollback del negocio.
- Agregar ID de correlación entre frontend/backend/IA y tiempos por operación. No registrar JWT, claves, contraseñas, CSV completos ni snapshots sensibles.

## 7. Configuración, almacenamiento y seguridad local

### 7.1 Matriz de variables

Las nuevas variables se implementan donde corresponda; escribirlas en `.env` no las vuelve funcionales por sí solo.

| Ámbito | Variables/decisiones | Criterio |
|---|---|---|
| Compose raíz | `COMPOSE_PROJECT_NAME`, `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD`, `APP_DB_PASSWORD`, `DB_PUERTO_HOST`, `PGDATA_VOLUME_NAME` | Mantener nombre estable y elegir volumen real en fase 0 |
| Backend operativo | `DATABASE_URL`, `SECRET_KEY`, JWT/login, `CORS_ORIGENES`, `INTERVENCION_MODO_SOMBRA` | Solo rol operativo; preservar comportamiento y expiración actual configurable |
| Migrador/seed admin | `DATABASE_URL_MIGRACIONES`, password seed y variables necesarias para importar settings | Credenciales owner únicamente en estos procesos; no inyectarlas al backend permanente |
| Cliente IA backend | `IA_URL`, `IA_API_KEY`, `IA_TIMEOUT_SEGUNDOS`; tamaño de chunk si se necesita | Docker `http://ia:8100`; nativo `http://127.0.0.1:8100` |
| Servicio IA | `IA_API_KEY`, `MODEL_REGISTRY_DIR`, manifiesto activo y configuración de logging | No JWT de negocio ni credenciales PostgreSQL |
| Proceso entrenamiento | Rutas dataset/modelos/reports, versión, semilla y fecha de referencia | Opciones explícitas; entrenamiento no depende de un servidor HTTP vivo |
| Backend archivos | Directorios de datos/runtime por variables o argumentos de scripts | No rutas de usuario absolutas ni basadas accidentalmente en CWD |
| Frontend | `VITE_API_URL` | URL que resuelve el navegador: `http://localhost:8000`, no `http://backend:8000` |
| Pruebas | URLs/credenciales para BD separada y servicios de prueba | Nunca reutilizar BD de demo por defecto |

Compose debe interpolar las variables realmente usadas. Hoy el Compose raíz fija algunos valores aunque aparezcan en `.env.example`; al unificar, elegir nombres fijos documentados o parametrización completa, sin aparentar soporte que no existe.

- `.env` raíz: entrada local de orquestación. No se copia a imágenes ni se publica.
- `.env.example`: valores ficticios/seguros de desarrollo y explicación de obligatorios.
- `.env` por aplicación: solo para ejecución nativa, con precedencia y CWD documentados. No depender de que Pydantic encuentre por casualidad el `.env` raíz.
- Las variables `VITE_*` son públicas. Ningún secreto de backend/IA se coloca en ellas.
- Con `vite dev`, se leen al iniciar; con build estático se fijan durante build salvo configuración runtime diseñada expresamente.
- Preservar rol operacional sin DELETE e inmutabilidad de historial/auditoría. No desactivar RLS o triggers para hacer pasar tests.
- La revisión leída crea políticas RLS permisivas para el rol app; no confundir RLS habilitado con autorización por rol de usuario. Verificar RBAC real y no afirmar aislamiento que no existe.
- El script init actual crea específicamente `predicitas_app`. Si se conserva `APP_DB_USER`, validar que coincide o parametrizar de forma segura; no cambiar solo `.env`.
- Rotar password de `.env` no cambia automáticamente el rol de un volumen existente. Documentar rotación SQL separada, con respaldo.

### 7.2 Puertos y volúmenes

- Frontend: 5173; backend: 8000; IA: 8100 opcional solo loopback; PostgreSQL interno: 5432.
- Elegir un único puerto host BD, por defecto 5432 si está libre; 5433 es alternativa por `DB_PUERTO_HOST`, no un segundo stack simultáneo.
- El nombre lógico `pgdata` puede resolver a volúmenes físicos diferentes según el nombre de proyecto Compose. Inspeccionar antes de mover/renombrar.
- Declarar nombre real del volumen mediante configuración explícita. Para datos existentes, usar volumen externo conocido o restaurar en uno nuevo; no crear uno vacío sin avisar.
- Separar volúmenes de desarrollo y pruebas. Un entorno de pruebas nunca comparte `pgdata` con demo.
- Datos/modelos en bind mounts del host pueden sincronizarse con OneDrive; preferir almacenamiento local no sincronizado para archivos grandes y PostgreSQL siempre en volumen Docker. Las rutas externas deben ser configurables y documentadas.
- Probar lectura/escritura con el UID no-root. Dataset/modelos de inferencia en solo lectura; outputs de entrenamiento/runtime en montajes escribibles autorizados.
- `.sh` de inicialización con LF, no CRLF. No introducir pasos que dependan de bash instalado en Windows.

## 8. Fases de ejecución

### Seguimiento general

Estados válidos: **PENDIENTE**, **EN CURSO**, **BLOQUEADA**, **COMPLETADA**. Una fase completada registra fecha, responsable, evidencia y punto de retorno. Todas las fases de implementación parten pendientes.

| Fase | Resultado | Dependencia | Estado |
|---|---|---|---|
| 0 | Inventario, baseline y recuperación comprobada | Ninguna | COMPLETADA |
| 1 | Contratos y decisiones congelados | 0 | COMPLETADA |
| 2 | Mudanza mecánica a monorepositorio operativo | 1 | COMPLETADA |
| 3 | Datos, CSV y archivos centralizados | 2 | COMPLETADA |
| 4 | Límites internos backend y transacciones | 3 | COMPLETADA |
| 5 | Aplicación IA autónoma probada | 1, 3, 4 | COMPLETADA (07/11/2026) |
| 6 | Preparación, entrenamiento y promoción explícitos | 5 | COMPLETADA (07/11/2026) |
| 7 | Backend conectado a IA por contrato | 4, 5, 6 | EN CURSO (7A/7B) |
| 8 | Frontend consolidado y resiliente | 2, 7 | PENDIENTE |
| 9 | Arranque local único y bootstrap reproducible | 3–8 | PENDIENTE |
| 10 | Regresión, contratos, seguridad y resiliencia | 9 | PENDIENTE |
| 11 | Corte final, documentación y cierre | 10 | PENDIENTE |

#### Fase 0 — Inventario, respaldo y línea base

**Objetivo:** saber qué existe, qué funciona y cómo volver atrás antes de tocar estructura.

**Qué se hace**

- [x] Inventariar archivos, repositorios internos, `.git`/worktrees si existen, rutas absolutas, servicios y versiones instaladas.
- [x] Definir estrategia conservadora del monorepositorio: conservar repositorio raíz y snapshot `69c686f` ya existentes; no hay repositorios internos que integrar. Sin commits automáticos ni borrado de historial.
- [x] Registrar Docker/Compose, Python, Node, PostgreSQL y hashes de dependencias/lockfiles.
- [x] Completar instalación limpia backend en venv aislado: 54 versiones fijadas coinciden y `pip check` correcto. Superado timeout inicial de red; `npm ci` frontend también completó.
- [x] Inventariar Compose activos, nombre de proyecto, contenedores, puertos y volúmenes con herramientas de inspección de solo lectura.
- [x] Registrar versión Alembic, nueve tablas, conteos, secuencias, índices, constraints, triggers, permisos y políticas RLS de los tres volúmenes candidatos.
- [x] Respaldar código completo, `.env` por canal privado, CSV, modelo y BD; conservar copia adicional fuera del árbol/OneDrive y de Temp.
- [x] Crear dumps custom y globals privados de las tres bases; restaurar y verificar CRP en entorno aislado. Si se elige otra base como principal, comprobar también su dump lógico antes del cierre.
- [x] Usar `pg_dump -Fc -f` dentro del contenedor y `docker cp`, sin redirección binaria PowerShell ni publicación de globals/passwords.
- [x] Ejecutar pruebas actuales en BD de pruebas aislada y registrar fallos previos y flujos que sí funcionan; no equivale a suite aprobada.
- [x] Usuario aceptó expresamente evidencia funcional alternativa a screenshots bloqueados por ventana no visible. No se certifica validación visual completa.
- [x] Guardar OpenAPI, ejemplos de respuesta sin secretos, conteos, hashes y predicciones sobre fixtures fijos.
- [x] Verificar credenciales históricas demo en una copia, sin publicar/cambiar passwords: tres cuentas activas coinciden con clave de seed del Compose original. Smoke/navegación con cuentas desechables.
- [x] Confirmar la existencia y vaciedad de ambas carpetas `Skills`.
- [x] Confirmar con el usuario volumen principal: `predicitas-crp_pgdata` (1.122 citas), aprobado el 03/11/2026; preservar los otros dos sin fusionar. Ver `docs/migracion/fase-00/decision_bd_principal.json`.
- [x] Congelar línea base con fallos previos y remitir estabilización separada a fase 1; no se declara sistema aprobado funcionalmente ni se mezclan arreglos con movimientos.

**Avance y evidencias (03/11/2026):** [Fase 0 — inventario, respaldos y línea base](docs/migracion/fase-00/README.md). Snapshot previo `69c686f`; tres originales verificados sin cambios por hash. Backend completo bloqueado en colección; diagnóstico adicional 218 aprobadas/1 fallida, cobertura 87,12%. Frontend 451 aprobadas/56 fallidas, build/typecheck bloqueados. No se modificó código funcional ni se avanzó a fase 1.

**Cierre técnico (03/11/2026):** [CIERRE_FASE_0.md](docs/migracion/fase-00/CIERRE_FASE_0.md). Usuario confirmó CRP como principal y aceptó evidencia funcional alternativa. Instalación limpia y credenciales demo verificadas; respaldos/originales revalidados. COMPLETADA significa inventario, recuperación y baseline establecidos, no corrección de fallos existentes.

**Se toca:** exclusivamente evidencias, backups, configuración aislada de pruebas y estrategia de control de versiones.

**No se toca:** código funcional, esquema activo, modelo, datos operativos, volúmenes y archivos originales.

**Configurar:** almacenamiento privado de backups y BD de prueba con nombres inequívocos. Las fixtures actuales usan el engine configurado globalmente: validar URL antes de importar tests.

**Aceptación:** inventario y baseline firmados; restauración aislada comprobada; se conoce inequívocamente qué volumen contiene los datos a conservar. Sin esto, bloquear fase 2.

**Retorno:** no hay cambio funcional que revertir. Conservar respaldos verificados.

#### Fase 1 — Contratos y decisiones de arquitectura

**Objetivo:** fijar el destino antes de mover implementaciones.

- [x] Documentar decisiones en `docs/arquitectura/`: ocho ADRs con componentes, propietarios, transacciones, datos IA, registry y errores; implementación posterior, no aplicada ahora.
- [x] Inventariar 55 operaciones API y 15 rutas UI de módulos, alias, descargas/formularios y roles; snapshot OpenAPI copiado byte a byte y contrastado con app actual.
- [x] Definir contratos IA v1, CSV operacional, dataset, features y manifiestos en `contracts/`: 12 schemas y 60 ejemplos positivos/negativos comprobados.
- [x] Documentar umbrales del manifiesto/perfil v1, redondeo a tres decimales antes de clasificar, tipos/nulos y correlación individual/lote.
- [x] Elegir uso del volumen existente aprobado `predicitas-crp_pgdata`, proyecto `predicitas-crp`, puerto host BD 5432 configurable explícitamente; sin restore/seed por defecto.
- [x] Mapear 74 imports cruzados, 90 sitios db.* y 27 commits; incluir import local `/citas/{id}/prediccion` y separar lecturas de escrituras.
- [x] Definir E2E futuro y alcance realmente comprobado, funcionalidades incompletas y entrega separada S-01..S-13 de estabilización.
- [x] Definir compatibilidad actual/objetivo y correcciones por separado; distinguir alias no equivalentes y no presentar defectos como garantías deseadas.

**Cierre documental (03/11/2026):** [Fase 1 — contratos y decisiones](docs/migracion/fase-01/README.md), [arquitectura](docs/arquitectura/README.md) y [contratos](contracts/README.md). Validaciones de schemas/fixtures y contraste offline con backend, sin tocar aplicaciones/BD. COMPLETADA no equivale a implementar IA externa ni corregir fallos de fase 0.

**Gate antes de cerrar fase 2:** resolver S-01 (TypeScript/build) en entrega independiente, preferiblemente antes de mover. Los demás fallos se conservan caracterizados con gates propios. No mezclar estabilización, movimiento mecánico y extracción IA ni declarar build aprobado con la línea base roja.

**Se toca:** documentación, esquemas de contrato y fixtures de referencia; pruebas de contrato pueden prepararse sin modificar producción.

**No se toca:** lógica, tablas, entrenamiento ni versiones de dependencias.

**Configurar:** política de compatibilidad y ubicación de evidencias de cada fase.

**Aceptación:** contratos con ejemplos válidos e inválidos, matriz de consumidores y decisiones sin pendientes críticos.

**Retorno:** ajustar decisiones/documentos sin alterar aplicaciones.

#### Fase 2 — Mudanza mecánica y primer arranque desde `apps/`

**Objetivo:** cambiar ubicaciones, no comportamiento.

**Inicio (04/11/2026):** solicitado por el usuario. Punto de retorno `80e3ce2` (incluye S-01 y cambios backend previos que se preservan). Evidencias nuevas en `docs/migracion/fase-02/`. Build/typecheck previos pasan; lint conserva fallo de `react-refresh/only-export-components` en `Registrar.tsx`. No mezclar su corrección con esta mudanza ni cerrar la fase con ese gate abierto. Pruebas exclusivamente en copias aisladas; volumen principal sin arrancar ni sembrar.

**Resultado (04/11/2026): COMPLETADA.** Mudanza y validaciones de paridad completadas en aislamiento: OpenAPI/predicciones/modelo idénticos, mismos fallos de baseline. El fallo de lint registrado durante la mudanza fue corregido separadamente en el commit `a5a1f5f`; lint/typecheck/build se revalidaron con salida 0 antes de fase 3 (05/11/2026). Stack nuevo arrancado y verificado por HTTP sobre clon; catálogo/datos/secuencias preservados incluso tras recreación. Tres volúmenes originales y tres `.env` idénticos; laboratorio detenido. Ver [evidencia de fase 2](docs/migracion/fase-02/README.md). Los logs anteriores del fallo se conservan como evidencia histórica, no como bloqueo actual.

- [x] Mover backend completo a `apps/backend/` y frontend completo a `apps/frontend/`; conservar `Skills/` vacías.
- [x] Mantener imports Python `app.*`, estructura interna y lockfiles. No extraer todavía LightGBM.
- [x] No copiar `.venv`/`node_modules` como instalación definitiva: recrear entornos cuando proceda; los entornos Python pueden contener rutas absolutas.
- [x] Crear entrada `compose.yaml` raíz que reproduzca el stack actual con contextos/rutas actualizados. No añadir dependencia obligatoria de IA todavía.
- [x] Revisar Dockerfiles/COPY, mounts, `alembic.ini`, scripts y pruebas afectados por rutas. Mantener `WORKDIR /app` por aplicación: Dockerfiles/Alembic/imports relativos no requirieron cambios; contextos y montaje init actualizados en Compose.
- [x] Fijar explícitamente el volumen físico elegido antes del primer arranque del nuevo Compose. Validación sobre clon externo explícito, nunca sobre principal.
- [x] No ejecutar a la vez stacks viejos y nuevos contra la misma BD; originales comprobados apagados, un solo PostgreSQL por clon.
- [x] Mantener configuraciones anteriores como referencia temporal, claramente marcadas; dos originales archivados como `*.reference`, README raíz único.
- [x] Ampliar `.gitignore` y `.gitattributes` raíz existentes con excepciones para ejemplos, LF de shell y exclusión de secretos/binarios generados.

**Se toca:** rutas de aplicaciones, configuración de build/orquestación y referencias a esas rutas.

**No se toca:** reglas, endpoints, algoritmo, formato de CSV, IDs Alembic o tablas. No consolidar código frontend antiguo aún.

**Configurar:** contexto Compose raíz, `.env` explícito, puertos y volumen estable. Con contextos `apps/backend`/`apps/frontend`, no intentar `COPY ../../data`: usar montajes para datos y contratos.

**Aceptación:** mismo recorrido baseline desde rutas nuevas; mismos datos/IDs/conteos; Alembic mantiene revisión; build frontend y pruebas conocidas no empeoran.

**Retorno:** restaurar configuración/rutas de fase anterior desde snapshot/commit, conservando el mismo volumen. No restaurar BD innecesariamente si no hubo cambios de datos.

#### Fase 3 — Centralización de archivos y datasets

**Objetivo:** que cada CSV/dataset/output tenga un propietario y ruta inequívocos.

**Inicio (05/11/2026):** autorizado por el usuario con confirmación previa exigida para acciones críticas/alto riesgo. Punto de retorno `a5a1f5f`, árbol limpio. Se preservan CSV/fixtures históricos y artefacto activo; solo copias canónicas/snapshot legacy, CLI de archivos y salidas futuras de QA. No borrar duplicados, promover/cargar copia legacy, reentrenar, cambiar esquema/credenciales ni intervenir el principal. Pruebas de persistencia únicamente en una BD nueva aislada. Evidencia en `docs/migracion/fase-03/`.

**Resultado (05/11/2026): COMPLETADA, con deuda D-01 a D-04.** Corrección de trazabilidad en `dd4ae83` y ajuste LF en `05716fe`, árbol limpio al validar; ejecución vigente `cierre-20261105-02`. Imagen ejecutada por ID `sha256:99b2976a7f143fce8c0d9813556612b4babe7b8f6612e7964674c5b5e6684cd3`. **43/43 pruebas nuevas aprobadas**, diagnóstico backend **261/1** (218 previas + 43 nuevas, mismo fallo previo), cobertura 87,13 %. Suite completa conserva error de colección IA; no se presenta como verde. Integración 40/0 y 20/4 con BOM/duplicados/rollback, OpenAPI/predicciones y empaquetado aprobados. Frontend: baseline citado, no reejecutado. Laboratorio existente reanudado tras comprobar aislamiento y detenido al terminar; originales intactos. Muestras y herramientas comprobadas en clon limpio; evidencia pública sanitizada y verificable sin modelo/env privados. [Criterios y comandos](docs/migracion/fase-03/REVALIDACION.md), [índice vigente](docs/migracion/fase-03/evidencia/actual.json) y [detalle de fase 3](docs/migracion/fase-03/README.md). Fase 4 no implementada.

##### Deuda técnica aceptada de fase 3

- **D-01 (Retiro de CSVs legacy):** Las copias en la raíz y `apps/backend/data/` se mantienen transitoriamente por compatibilidad; su eliminación queda programada para las Fases 6 y 7 al migrar importers y extraer IA. Responsable: Arquitectura de Datos.
- **D-02 (Mensaje informativo `+4` en CLI):** Conteo cableado en mensaje de salida de `exportar_csv.py`; no afecta lógica de generación/importación ni contrato operacional.
- **D-03 (Ubicación de `rutas_validacion.py`):** Helper auxiliar mantenido en `apps/frontend/tests/` hasta la armonización de herramientas de prueba en Fase 10.
- **D-04 (Ausencia de pin en `coverage`):** Versión de paquete `coverage` sin pin fijo en backend (7.17.0 vs 7.17.2), produciendo pequeñas variaciones decimales en cobertura sin comprometer el umbral exigido (≥ 75 %).

- [x] Crear estructura de `data/`, `artifacts/`, `runtime/` y política de ignore según sección 5; raw/processed vacíos, sin dataset ficticio.
- [x] Centralizar CSV canónico variado y demo con hash idéntico; localizar consumidores y actualizar guías. Por prudencia, copias antiguas preservadas como compatibilidad no canónica; retirada futura solo tras revisión externa, no borrar en esta entrega.
- [x] Mantener fixtures exclusivos de frontend y fixtures de contratos; no había fixtures nuevos realmente compartidos que trasladar.
- [x] Adaptar `scripts/exportar_csv.py`: salida absoluta y fecha explícitas, directorios autorizados, creación segura y apertura exclusiva; proyección a 13 columnas operacionales sin cambiar el generador.
- [x] Definir fecha explícita para muestras nuevas; originales sin cambios de fecha, origen/semilla/referencia desconocidos como null. Reloj de validación fijo 2026-11-05 08:00 Lima, no afirmación de fecha de generación.
- [x] Copiar artefacto a `artifacts/models/legacy-import/`, hash y atributo solo lectura registrados; inferencia integrada mantiene ruta y bytes anteriores, copia no cargada/promovida.
- [x] Crear inventario/manifiestos de preservación; 40 filas válidas del variado y 20 válidas/4 rechazos intencionales de demo comprobados en API con BD de prueba inicialmente vacía.
- [x] Mantener uploads/descargas en memoria/streaming. No activar retención, directorio de imports, TTL ni limpieza automática.
- [x] Actualizar QA para salidas nuevas exclusivas en `runtime/test-results/diseno/<id>/`; IDs/paths y guarda BD explícita probados; fixtures/manifiesto/capturas históricos intactos. No se certifica E2E visual legacy completo.

**Se toca:** rutas de archivos, argumentos de scripts, mounts y documentación de datos.

**No se toca:** reglas de importación, esquema DB, algoritmo ni corpus de referencia usado para comparar predicciones.

**Configurar:** paths absolutos efectivos mediante variables/argumentos, montajes lectura/escritura y exclusiones Docker; no incluir todo `data/` en imágenes.

**Aceptación:** importación desde ubicación canónica funciona; hashes preservados; archivos no aparecen en frontend público; scripts funcionan desde el CWD documentado y no escriben en código fuente.

**Retorno:** restablecer referencias de rutas; conservar ambas copias hasta verificar consumidores. No eliminar el único original ni el único backup.

#### Fase 4 — Encapsulación backend y transacciones

**Objetivo:** convertir la división por carpetas en límites reales.

**Inicio (05/11/2026):** autorizado por el usuario con precaución. Punto de retorno
`2f4140e`, árbol inicialmente limpio. Ejecución incremental: bloque A de reloj,
bootstrap e identidad, validado por separado antes de abordar workflows de negocio.
No se cambia esquema/credenciales/modelo ni se interviene el principal. El bloque A
no equivale a cerrar la fase completa. [Bitácora](docs/migracion/fase-04/README.md).

**Bloque A validado (05/11/2026):** ejecución `bloque-a-20261105-02`, fuentes
identificadas por SHA-256 sin commit automático. **15/15 pruebas nuevas aprobadas**;
diagnóstico **276 aprobadas / 1 fallo previo** frente a baseline **261/1**,
cobertura **87,14 %**. OpenAPI, DDL de metadata, modelo y predicciones idénticos;
entorno Alembic actualizado probado sobre laboratorio nuevo, sin revisiones nuevas.
Fallos de login/bloqueo persistidos y rollback de clave tras flush comprobados entre
conexiones independientes. Suite completa conserva el error previo de colección IA;
frontend no reejecutado. Ambos laboratorios detenidos; archivos protegidos intactos.
[Evidencia sanitizada](docs/migracion/fase-04/evidencia/bloque-a-20261105-02/resumen.json).
Siguen pendientes contratos/workflows de negocio, routers sin SQL y concurrencia;
**la fase 4 permanece EN CURSO**.

**B.1 validado (05/11/2026), antes de C:** implementación `d59d290` y ajuste de fixture `6e7787c`; ejecución `bloque-b1-20261105-02`, baseline explícito del bloque B `2f95273`. Auditoría de liberación restaurada, reprogramación interna sin fecha rechazada, contratos por IDs/snapshots y sin fábrica ORM inyectable. **27/27 focalizadas**, diagnóstico **303/1** frente a **284/1**, mismos casos previos y 19 nuevos aprobados; cobertura **87,42 %**. API/DDL/predicciones/modelo idénticos; rollback tras flush de cupo comprobado desde otra conexión. S-02/S-03 siguen históricos. Archivos protegidos intactos, laboratorios nuevos detenidos y frontend no reejecutado. [Evidencia B.1](docs/migracion/fase-04/evidencia/bloque-b1-20261105-02/manifest.json), [alcance y límites](docs/migracion/fase-04/B1.md). Pendientes C/D; no iniciar fase 5.

**C validado (06/11/2026):** código `d7c7f45`, ejecución `bloque-c-20261106-01`, baseline `6da1c49`. Routers sin persistencia directa/commits, casos de uso de ofertas/cierres y exportación REP-02. S-03 corregido sin cambiar el rechazo humano 400 vigente; S-08 con estados/matching/auditoría e historial; alias S-05 reproducido y corregido al delegar reporte. **341/0 diagnóstico** frente a 303/1: único caso previo cambiado es S-03 (failure → passed), 37 nuevos aprobados. **38/38 focalizadas**, cobertura **91,15 %**. Paridad OpenAPI/DDL/modelo/predicciones y rollback tras flush de oferta/cierre/exportación observados desde otra conexión. Suite completa conserva S-02; frontend no reejecutado. Originales intactos y laboratorio nuevo detenido. [Evidencia C](docs/migracion/fase-04/evidencia/bloque-c-20261106-01/manifest.json), [criterios y límites](docs/migracion/fase-04/C.md). **Pendiente D; fase 4 EN CURSO.** No se certificó concurrencia ni build empaquetado final.

**D validado y fase 4 COMPLETADA (06/11/2026):** responsable: agente, bajo autorización del usuario. Baseline D `2ad167e`; código/tests `500c040`, corrección `a463fdb`, runner `62f04ac`. Ejecución aceptada `bloque-d-20261106-04`: **341/0 → 352/0**, once pruebas nuevas, **91,23 %** cobertura; **211/0** sobre imagen sin fuentes backend montadas. **9/9 carreras HTTP** con sesiones precargadas, espera PostgreSQL observada y un único éxito efectivo; **4/4 rollbacks** tras flush observados independientemente, más identidad/bloqueo. Gates de límites, adaptadores read-only, DAG y composición aprobados. Imagen `sha256:b1225267a59311a2fadce32ea139cabaa948b0b6ff2d344eb083a48e6421666d`, no-root y sin env owner; OpenAPI/DDL/modelo/predicciones idénticos. Evidencia separada en `f2c5823`, hashes del índice y paquete comprobados desde clon limpio. Intentos 01–03 conservados; los cuatro laboratorios detenidos, originales intactos. S-02 sigue explícito: **no suite completa verde**; frontend no reejecutado. [Criterios, revisión y límites D](docs/migracion/fase-04/D.md), [evidencia](docs/migracion/fase-04/evidencia/bloque-d-20261106-04/manifest.json). Retorno D `2ad167e`, fase `2f4140e`: revertir solo lógica, nunca volúmenes/datos. **Fase 5 no iniciada**. Los estados EN CURSO anteriores y del resumen capturado son históricos, previos a esta revisión final.

- [x] Añadir contratos públicos por módulo y tests que prohíban imports a routers/repositorios/modelos privados ajenos, con excepciones explícitas de composición/reporting. D: lista exhaustiva en `bootstrap/limites.py` y gate de todos los módulos.
- [x] Llevar reloj/zona horaria técnica a `core`, actualizar dependency overrides de pruebas y retirar dependencia de `intervenciones.router` hacia `citas.router`.
- [x] Llevar registro global ORM a `bootstrap` y actualizar `main.py`, Alembic, scripts y tests; registrar todos los modelos antes de construir metadata.
- [x] Definir propiedad de `Usuario` en Usuarios y contratos con Auth; conservar tabla, hashing, tokens, expiración, bloqueo y revocación existentes.
- [x] Extraer operaciones públicas de Citas para confirmar/liberar/cambiar estado y de Lista de Espera para crear cupo, ofrecer y reasignar. D: entradas componibles por contratos públicos; REPROGRAMADA conserva su caso de uso con fecha obligatoria.
- [x] Consolidar reglas duplicadas entre Citas e Intervenciones: una transición legal debe generar exactamente un historial y la auditoría requerida. D: `citas/transiciones.py`, contratos y carreras con unicidad persistida.
- [x] Introducir workflows para operaciones multímódulo; todos participan en la misma sesión/transacción del caso de uso. D: `app/workflows/`, sin commits propios ni imports privados ajenos.
- [x] Quitar SQL y commits de routers, incluidos endpoints de ofertas/rechazo/desistimiento; mover validaciones/estados a servicios propios. Bloque C; prueba de arquitectura para los siete routers.
- [x] Separar operaciones componibles sin commit de casos de uso de nivel superior que sí cierran transacción. Actualizar importador/seed para evitar transacciones anidadas incorrectas. D: importador componible con prueba de reversión; seed hace flush de usuarios y confirma junto con importación, sin begin anidado (revisión de código, no ejecución integral del seed demo).
- [x] Mantener auditoría append-only dentro de la transacción de negocio cuando hay éxito. Fallos de login requieren su propia persistencia explícita, sin perder bloqueo/registro al responder 401. Gates A/B.1/C conservados; D repite diagnóstico, rol operativo e identidad independiente.
- [x] Crear adaptadores de lectura para bandeja/detalle/reportes que hoy consultan varias tablas; no duplicar datos para evitar un JOIN. D: `consultas.py`, excepciones read-only y filtros/contratos regresionados.
- [x] Probar concurrencia y rollback completo: cita + historial + intervención + cupo + auditoría, según la operación. D: nueve carreras y cuatro coordinadores; oferta/cierre/exportación conservan pruebas C.

**Se toca:** organización y lógica interna necesaria para delimitar responsabilidades; actualizar tests y composición.

**No se toca:** contrato público, políticas del piloto, datos existentes, versiones de modelo ni esquema salvo necesidad aprobada. No usar autogenerate para renombrar tablas por mover clases.

**Configurar:** política transaccional uniforme y lista de dependencias permitidas. Si aparece cambio de esquema imprescindible, crear revisión nueva aditiva y detenerse para aprobación.

**Aceptación:** cero escrituras ajenas fuera de contratos/workflows aprobados, sin ciclos, routers sin SQL/commits; permisos y estados conservados; rollback y doble reasignación probados en PostgreSQL.

**Retorno:** revertir solo entrega de lógica desde punto de control, manteniendo datos. Si hubo revisión nueva aprobada, usar procedimiento compatible y restauración ensayada, no downgrade genérico.

#### Fase 5 — Extraer y probar la aplicación IA independiente

**Objetivo:** disponer de IA autónoma antes de cambiar sus consumidores.

**Revisión correctiva (06/11/2026): RESUELTA por A/B/C (07/11/2026).** La
declaración COMPLETADA siguiente se conserva como histórica; la revisión la había
suspendido porque readiness aceptaba artefactos incompatibles, había clave por
defecto, validación contractual insuficiente y el runner carecía de trazabilidad
verificable. Corrección autorizada por el usuario; baseline operativo `af13b3b`,
retorno de esta entrega `fe4768b`. No se conecta backend/IA.
No se reduce el alcance original: separación de entrenamiento y migración del
generador se validaron después en A/B; timeout y concurrencia en C. El estado
vigente se recoge en el checklist y resultados siguientes, sin trasladar
requisitos a fase 6 por decisión implícita.
[Criterios correctivos](docs/migracion/fase-05/CORRECCION.md).

**Resultado (06/11/2026): COMPLETADA.** Solicitado y autorizado por el usuario. Baseline `af13b3b`, imagen `sha256:82d2316f5247f5f698e966885b22f2787ece0f40573c38a5c75b831e6e070395` (no-root `predicitas:1000`). **21/21 pruebas aprobadas**, cobertura de código **92.0 %**. Paridad matemática estricta y explicabilidad TreeSHAP verificada al 100 % contra baseline congelado. Siete rutas OpenAPI idénticas a contratos. Backend integrado y frontend intactos. [Evidencia](docs/migracion/fase-05/evidencia/ia-20261106-01/manifest.json) y [bitácora](docs/migracion/fase-05/README.md).

- [x] Crear `apps/ia/` con API, configuración, autenticación interna, tests y dependencias propias.
- [x] Separar predictor actual en features, inferencia, entrenamiento, métricas y datasets, sin rediseñar algoritmo/preprocesado. Features/inferencia corregidas; entrenamiento/evaluación/métricas offline validados en A; generador/datasets/mapping validados en B. Copia integrada preservada hasta retirar consumidores.
- [x] Migrar el generador sintético a datasets IA y producir CSV explícito para el futuro seed; mientras dura transición, marcar copia antigua como temporal con fecha de retirada. B: `apps/ia/datasets/`, CSV canónico probado en PostgreSQL nuevo, [registro temporal](docs/migracion/fase-05/LEGACY_GENERADOR.md) con objetivo provisional 20/11/2026 y gates de retirada; seed sin cambios.
- [x] Eliminar dependencias de FastAPI backend, ORM operativo y `app.modules.citas` de la nueva aplicación IA.
- [x] Cargar el artefacto legado confiable solo tras verificar compatibilidad de librerías/clases serializadas; comprobar que no depende de rutas Python antiguas antes de retirarlas. Corrección `ia-correccion-20261106-03`: hash previo a deserialización, validación de compatibilidad y smoke en imagen sin backend.
- [x] Implementar API interna de sección 6, healthchecks y manejo de modelo ausente/corrupto/incompatible. Corrección validada contra schemas congelados, API-key explícita, errores y readiness real.
- [x] Implementar carga en startup/caché controlada por versión; ningún endpoint entrena ni escribe modelos.
- [x] Fijar límites de request/lote, validación estricta, timeout y número de workers compatible con memoria disponible; cada worker puede duplicar modelo en RAM. Corrección: recepción 10 s, 1 worker/16 conexiones, hilos nativos acotados. C: un worker persistente aislado, cupo único sin cola, plazo total duro de 10 s, interrupción y reinicio comprobados, memoria pico medida bajo 1 GiB; ver [bloque C](docs/migracion/fase-05/BLOQUE_C.md).
- [x] Crear Dockerfile IA no-root, con librerías nativas necesarias para LightGBM (`libgomp1` si aplica) y TZ/data requeridas.
- [x] Comparar probabilidades, niveles y explicaciones con baseline congelado; comprobar que una predicción no modifica artefactos.

**Corrección validada (06/11/2026), sin cierre total de fase:** código `d0ca97f`,
runner `5c260bf` + `d9c523e` + `bba0e61`; ejecución vigente
`ia-correccion-20261106-03`. **83/83 pruebas empaquetadas**, cobertura
**96,00725952813067 %**, tres autopruebas del runner, **207 casos diferenciales
idénticos en todos los campos** (7 congelados únicos + 200 deterministas), incluidos
BAJO/MEDIO/ALTO. HTTP real: lote de 100 en **0,98 s** dentro del presupuesto local de
10 s, red none, filesystem/modelo RO, UID 1000, 2 CPU/1 GiB, sin fuentes/DSN backend.
Imagen `sha256:21c8cd34539de93335c813b13a2bc7e81e254ba2ce293a9df90782c5e09e3bbf`.
Backend/frontend/contratos/protegidos iguales al baseline. Evidencia separada en
`8dd4cdd`, hashes del índice y clon limpio Windows/autocrlf comprobados; seed también
verifica desde ese clon. Intentos correctivos 01/02 conservados. **La fase 5 seguía
EN CURSO**: faltaban extracción de entrenamiento/generador/datasets/CSV y resolver
timeout de cómputo bajo concurrencia. No se desplazan implícitamente a otra fase ni
se conecta el backend. [Detalle y límites](docs/migracion/fase-05/CORRECCION.md),
[evidencia vigente](docs/migracion/fase-05/evidencia/ia-correccion-20261106-03/manifest.json).

**Bloque A validado (06/11/2026); la fase 5 seguía EN CURSO:** implementación `83a96a6`,
runner probado `22c6788`, evidencia separada `9f6636b`; ejecución
`ia-bloque-a-20261106-01`. **105/105 pruebas** (83 previas + 22 nuevas), cobertura
conjunta **96,89 %**, offline **100 %**. Entrenamiento extraído en memoria con
registros/versiones/fecha explícitos; serialización exclusiva de candidato nuevo,
sin dependencias operativas, caché ni promoción. Dos entrenamientos reales en
contenedores independientes reprodujeron splits 700/150/150, preprocesadores,
parámetros, probabilidades crudas de ambos estimadores sobre 1000 filas, métricas,
equidad e importancias. F1 de prueba **0,8621** en ambos. Modelos de prueba solo
en scratch; activo y registry intactos. Serving no importa ni ejecuta entrenamiento,
207 casos de inferencia idénticos y HTTP real aprobado. Imagen ejecutada por ID
`sha256:93b75b1f7d095dbdeb3c5d478cdf209026fb7ea6faf4822f834a0612fe329892`,
sin red externa ni BD; código serving, dependencias, manifiesto aprobado,
backend/frontend/contratos/modelos/CSV sin cambios. Evidencia y corrección previa
verificadas en clon limpio Windows/autocrlf; sin contenedores de prueba activos.
Retorno A `3e561b2`. **No se iniciaron B/C ni fase 6/7**; pendientes generador/
datasets/CSV/retirada temporal y timeout/concurrencia. [Criterios y resultados A](docs/migracion/fase-05/BLOQUE_A.md),
[manifiesto A](docs/migracion/fase-05/evidencia/ia-bloque-a-20261106-01/manifest.json).

**Bloque B validado; cierre documental reanudado (07/11/2026); la fase 5 seguía EN CURSO:**
implementación `58c9288`, runner probado `30f576b`, evidencia separada `16d663c`;
ejecución `ia-bloque-b-20261106-01` capturada el 07/11 a las 01:16 UTC (06/11 Lima).
**135/135 pruebas** (105 previas + 30 nuevas), cobertura conjunta **97,18 %**,
datasets **98,14 %**, entrenamiento **100 %**. Nueve escenarios/3450 filas con
todos los campos y orden iguales al generador preservado. CSV canónico de 13
columnas: 1080 aceptadas en endpoint ASGI/backend empaquetado y PostgreSQL nuevo,
repetición 0 aceptadas/1080 duplicadas sin cambiar citas/historial; cuatro filas
suplementarias de nulos/BOM/Unicode/zonas y rollback tras flush comprobados desde
conexiones independientes. Regresión A, 207 casos de inferencia y HTTP IA real
aprobados. Imagen por ID
`sha256:ecbe5845ec10f4832b3a86cd0a095fd5068c57ed5b8b830bf4fcee90ee05134d`.
Serving, entrenamiento, dependencias, backend/frontend/contratos/modelos/CSV y
credenciales intactos; seed y consumidores siguen usando su compatibilidad
legacy. Parada del laboratorio archivada con salida 0. Al reanudar se comprobaron
fuentes/protegidos, JUnit/cobertura/logs/hash CSV y paridad archivada; paquetes
B/A/seed verifican desde clon limpio Windows/autocrlf. Docker no disponible en
esa reanudación: **no se presenta como nueva ejecución ni consulta actual de
recursos**. Retorno B `bfcad63`. En ese cierre, **solo C quedaba pendiente para
fase 5**; no iniciado entonces, sin pipeline/promoción fase 6 ni conexión fase 7.
[Detalle B](docs/migracion/fase-05/BLOQUE_B.md),
[manifiesto B](docs/migracion/fase-05/evidencia/ia-bloque-b-20261106-01/manifest.json).

**Bloque C validado; fase 5 COMPLETADA (07/11/2026):** implementación `4d00f07`,
pruebas/ramas límite `3294380`, evidencia separada `bc1af92`; ejecución
`ia-bloque-c-20261107-02`, commit probado
`3294380e0ff10421058c165179fa22fcdfa281e8`. **184/184 pruebas** (135 previas + 49
de ejecución), cobertura **94,37 %**, paridad **207 casos** en todos los campos y
tres niveles. Worker persistente aislado con cupo único sin cola; plazo total duro
de 10 s, interrupción/recogida en **0,302 s** y reinicio automático; concurrencia
**1×200 + 1×503 `CAPACIDAD_OCUPADA`** con recuperación; lote de 100 en **0,929 s**;
memoria pico **303 251 456 bytes** bajo 1 GiB (`procfs-vmrss+cgroup`). UID 1000,
red none, filesystem/modelo RO, sin DSN ni fuentes backend. Imagen por ID
`sha256:b1a1f3b30300ff2537f5ea689e1cf3e3d3e4c822c9ffbf2d3743abc1b438140c`.
Entrenamiento, datasets, manifiestos, Dockerfile, dependencias, backend, frontend,
contratos, modelo y CSV intactos respecto de `96d809d`; sin promoción ni conexión
fase 7. El run `ia-bloque-c-20261107-01` se conserva como intermedio, no publicado.
Evidencia y paquete verificados desde clon limpio; los hashes de fuentes solo
difieren por CRLF del árbol de trabajo, con contenido normalizado idéntico.
[Detalle C](docs/migracion/fase-05/BLOQUE_C.md),
[manifiesto C](docs/migracion/fase-05/evidencia/ia-bloque-c-20261107-02/manifest.json).

**Se toca:** nueva app IA, contrato interno, ubicación de código matemático y packaging IA.

**No se toca:** conexión productiva del backend, BD, estados, UI ni versión del modelo si el cálculo es equivalente.

**Configurar:** clave interna, registry montado RO para serving, readiness y puerto local. El servicio puede levantarse aisladamente sin BD/backend.

**Aceptación:** API IA cumple contratos y paridad, no importa backend ni contiene DSN, no entrena en inferencia; el backend sigue funcionando con implementación integrada hasta fase 7.

**Retorno:** desactivar servicio nuevo sin afectar backend actual; preservar artefactos y evidencia de comparación.

#### Fase 6 — Pipeline de datos, entrenamiento y promoción (COMPLETADA)

**Objetivo:** poder preparar un equipo limpio sin depender de un `.joblib` oculto o entrenamiento automático.

**Inicio (07/11/2026):** autorizado por el usuario con precaución; retorno
`d6e9b1c`, árbol inicialmente limpio. Primer bloque: CLI offline explícito de
generación/validación/entrenamiento y manifiestos de candidato. Sin promoción,
conexión backend/IA, cambios del seed ni intervención en BD/modelo activo.
Fase **COMPLETADA** el 07/11/2026 tras validar el camino limpio E; la conexión
backend/IA y el retiro del predictor siguen en fase 7, no iniciada.
[Bitácora y comandos](docs/migracion/fase-06/README.md).

**Primer bloque offline probado (07/11/2026):** 20 pruebas nuevas; suite IA
**204/204**, cobertura **93,18 %** en imagen empaquetada, sin red y modelo RO.
Generación reproducible, hashes/particiones y candidato real con manifiesto
validados. Modelo legacy conserva SHA-256 histórico. Pendientes promoción/
rollback, seed explícito/reconciliación y camino limpio integral; no se cierra
ningún ítem combinado por esta entrega ni se inicia fase 7.

**Bloque B validado en aislamiento (07/11/2026):** promoción con aprobación
explícita por hash/versión, releases inmutables, puntero atómico, rollback previo
o dirigido (incluido legacy), lock y control de activo esperado. Serving opt-in
con versión/hash fijados al reiniciar; arranque legacy por defecto conservado.
**228/228 pruebas**, 24 nuevas, cobertura **92,85 %**, imagen empaquetada sin red,
modelo host RO y registries efímeros. Sin despliegue, BD ni cambios backend/UI;
fuentes A preservadas. Pendientes seed, consumidores y camino limpio integral.
[Criterios/resultados B](docs/migracion/fase-06/BLOQUE_B.md).

**Bloque C iniciado (07/11/2026):** seed desde CSV/hash/BD explícitos, sin
generación ni resets; usuarios existentes preservados, carga parcial solo con
reconciliación autorizada y conflictos sin sobrescritura. Transacción única por
servicios backend y auditoría sin claves. Pruebas exclusivamente en PostgreSQL
nuevo aislado, sin tocar principal/modelos; A/B preservados sin commits.
[Alcance, comandos y resultados C](docs/migracion/fase-06/BLOQUE_C.md).

**Bloque C validado (07/11/2026):** ejecución `bloque-c-20261107-03`, **21/21
focales y 330/330 regresión empaquetada** (21 incluidas), cobertura app+seed
**91,07 %**, seed **88,07 %**. CSV canónico IA explícito: CLI backend carga
1080 citas/2080 historiales/3 usuarios en PostgreSQL nuevo con rol app; rerun
idéntico en todas las tablas, reconciliación explícita, conflictos/segundo seed
rechazados y rollback tras flush observado desde otra conexión. Imagen nueva
por ID, sin montajes fuente backend; tres laboratorios detenidos y originales/
modelos intactos. Colección completa conserva S-02 y error de árbol del
verificador histórico; dos archivos monorepo y tests/ia excluidos del diagnóstico
empaquetado, **no suite completa verde**. D/E/7 no iniciados; fase 6 EN CURSO.

**Bloque D iniciado; retiro total BLOQUEADO (07/11/2026):** inventario AST y
política cerrada de consumidores con hashes, gate manual previo al retiro y
**16/16 autopruebas** aprobados. Siete dependencias directas (incluido QA frontend
antes omitido), nueve namespaces informativos. Código 2 esperado impide retirar
la copia mientras predictor/reexport, exportador y fixtures sigan usándola.
Smoke de muestra backend/IA equivalente tras normalizar saltos; fuentes A/B/C y
protegidos intactos. Un error inicial de fixture temporal fue corregido; sin
errores actuales en las autopruebas. No se elimina código/datos ni se adelanta
fase 7. Acordar si D cierra como retirada programada o revisar la secuencia para
retiro físico, dado que el predictor se sustituye en 7 y 7 depende de 6.
**D no completada**, fase 6 EN CURSO; E/7 no iniciados.
[Alcance, errores y bloqueos D](docs/migracion/fase-06/BLOQUE_D.md).

**Decisión D aprobada por el usuario (07/11/2026):** cierre como **retirada
programada**, conservando temporalmente solo predictor integrado y su reexport
hasta su sustitución validada en fase 7. Resuelve la dependencia circular de
criterio, no las migraciones: exportador y cuatro consumidores QA siguen
pendientes. D **EN CURSO**, no completada. Guarda de cierre programado añadida:
19/19 autopruebas, inventario válido; cierre programado/retiro físico devuelven 2
esperado. No se elimina código ni se toca el entorno operativo.
[Decisión y secuencia obligatoria](docs/migracion/fase-06/DECISION_D_RETIRADA_PROGRAMADA.md).
**Antes de iniciar 7:** migrar/validar esos cinco consumidores, cerrar D como
programado, ejecutar E y cerrar la fase 6. E/7 no iniciados por esta actualización.

**Migraciones D completadas y validadas (07/11/2026 Lima):** ejecución
`migraciones-d-20261107-02`. Exportación generativa en IA; adaptador backend solo
consume muestras explícitas verificadas. Cuatro consumidores QA migrados a CSV
con manifiestos y hashes, sin quitar asserts ni el caso de 5000 citas/≤3 s.
**241/241 IA, 339/339 backend empaquetado y 33/33 archivos/CLI/guardas QA**;
cobertura IA 90,12 %, app backend+seed 88,40 %. Nueve escenarios CSV idénticos a
la proyección legacy, QA 45/4 y dos 20/4, repetición 0/24 y rollback independiente.
Solo quedan las dos excepciones aprobadas, cierre programado código 0 y retiro
físico no permitido. Error inicial de montaje QA corregido; dos laboratorios
nuevos detenidos, fuentes A/B/C/modelos/privados intactos, sin despliegue.
**D COMPLETADA COMO RETIRADA PROGRAMADA**, no eliminación física. Falta E; fase 6
EN CURSO y fase 7 PENDIENTE. Colección completa conserva bloqueos conocidos;
sin validación visual de navegador ni clon limpio.
[Detalle, límites y evidencia de migraciones D](docs/migracion/fase-06/MIGRACIONES_D.md).

**Bloque E validado y fase 6 cerrada (07/11/2026):** ejecución
`e-20261107-01`. Paquete de **243 fuentes** reconstruido sin artefactos,
`.joblib`, secretos ni `runtime`; imágenes IA/backend construidas solo desde ese
árbol (backend sin modelo, IA sin SQLAlchemy). En PostgreSQL nuevo y aislado:
dataset de 1000 históricas/1080 filas de seed, dos entrenamientos con métricas y
predicciones iguales, promoción, rechazo de corrupción y rollback; serving con
release/hash explícitos (lote de 60) y escenario sin modelo 503; seed
1080/2080/3 con repetición idempotente; backend real con health, login,
`/citas` 1080, `/usuarios` 3, catálogos y reportes 02/03. Gate D en 2
excepciones aprobadas, cierre programado 0 y retiro físico no permitido. Archivos
protegidos y contenedores en ejecución sin cambios. No se conectó backend/IA, no
se desplegó Compose ni se ejecutó navegador. **FASE 6 COMPLETADA**; fase 7
PENDIENTE y no iniciada. [Detalle y límites E](docs/migracion/fase-06/BLOQUE_E.md).

- [x] Implementar comandos documentados para generar dataset/seed, validar, particionar, entrenar baseline/LightGBM y producir candidato/manifiestos. A/E: CLI offline y camino limpio validados; seed.csv generado por el pipeline.
- [x] Establecer flags explícitos para versión, semilla, fecha de corte, fuente y directorios. Nunca sobrescribir una versión distinta con el mismo nombre. A: fechas/versiones nuevas obligatorias y rechazo de sobrescritura.
- [ ] Si se entrena con snapshot BD, implementar exportación backend autorizada con trazabilidad y sin acceso IA a PostgreSQL. **No soportado**: la CLI rechaza esa fuente y no consulta BD; no se implementó por esta vía.
- [x] Crear manifest de split y controles anti-leakage/calidad/equidad; conservar dataset sintético rotulado. A: manifiestos/hashes, 700/150/150, leakage y rotulado validados.
- [x] Implementar promoción de candidato aprobado y rollback a versión anterior; verificar hash y dependencias antes de cargar. Bloque B validado en registry temporal; sin cambiar el modelo activo del entorno.
- [x] Ajustar seed backend para consumir CSV operacional explícito y crear usuarios demo sin imports a generador IA. C: nulos/RN17, desenlaces y fechas validados; sin regenerar datos existentes.
- [x] Usar `SEED_PASSWORD` local/no registrada en logs, no contraseña fija en YAML. C: clave solo para usuarios nuevos, rerun conserva hashes/usuarios y no recibe passwords por argv.
- [x] Hacer seed repetible sin duplicar citas/usuarios; detectar carga parcial y reportar/reconciliar, no dar éxito simplemente porque existe alguna `CIT-SIM-*`. C: falta parcial exige flag; conflictos/contadores previos incompletos se rechazan sin sobrescribir.
- [x] Mantener normalización/importación por servicios backend, no SQL directo que omita historial/auditoría. C: transacción única, historial/auditoría y rollback tras flush comprobados desde observador independiente.
- [x] Definir camino limpio: generar sintéticos explícitos, entrenar/promover, importar seed; camino existente: preservar datos/modelo y no sembrar por defecto. E: recorrido completo en aislamiento; el camino existente no se modificó.

**Se toca:** procesos puntuales, manifiestos, scripts seed/export y retirada programada del generador duplicado.

**No se toca:** BD existente para regenerar datos, modelo activo sin promoción, parámetros para mejorar métricas durante esta migración.

**Configurar:** proceso entrenamiento escribible en datasets/artefactos; inferencia RO. La meta F1 documentada se verifica, no se declara cumplida sin medición.

**Aceptación:** un equipo sin artefactos puede generarlos de forma explícita y reproducible; se conoce qué dataset entrenó cada versión; rerun no destruye ni duplica datos.

**Retorno:** volver al manifest/artefacto previo con reinicio/recarga controlada; no regenerar BD ni sobreescribir versiones previas.

#### Fase 7 — Conectar backend con IA y retirar predictor integrado

**Objetivo:** completar la separación real manteniendo API pública y persistencia.

**Gate previo cumplido (07/11/2026):** fase 6 **COMPLETADA** con migraciones D y
evidencia integrada E. Fase 7 sigue **PENDIENTE** y no se inicia por esta
entrega. La excepción temporal aprobada en D no permite omitir los gates de 7 ni
conservar el generador integrado después de la sustitución validada.

- [ ] Crear puerto/contrato de motor predictivo en módulo IA backend y adaptador HTTP con `httpx`, lifecycle y timeouts explícitos.
- **7A implementado y validado (07/11/2026):** retorno `3700c5f`, puerto de
  inferencia, adaptador integrado diferido y HTTP opt-in con lifecycle propio,
  timeouts, respuesta validada y versión fija en todos los fragmentos. 19/19
  pruebas unitarias y HTTP TCP real: 1 individual + 105 en lote iguales al
  integrado; caída, timeout, clave inválida, modelo ausente y respuesta inválida.
  Cambio de versión entre fragmentos probado con transporte controlado. Sin BD,
  Compose ni cambios de ruta operativa. El ítem permanece abierto hasta cablear
  lifespan FastAPI/selección y completar metadata. **Fase 7 EN CURSO**, sin
  retiro del predictor, sin commit automático ni suite completa certificada.
  [Alcance, resultados y límites 7A](docs/migracion/fase-07/README.md).
- **7B autorizado e implementado (07/11/2026), en validación:** servicios y
  alias Citas inyectan el puerto, metadata remota normalizada, lifecycle FastAPI
  sin contacto IA en startup y selección explícita `IA_MOTOR`. El integrado
  sigue por defecto. Lectura cerrada antes de inferir, revalidación bajo locks
  por PK y persistencia/auditoría atómicas. Sin cambios de tablas/API, Compose,
  `.env` ni modelo activo; sin retiro ni commit automático. Laboratorios nuevos
  PostgreSQL/IA, no entorno operativo. [Alcance y evidencia 7B](docs/migracion/fase-07/BLOQUE_7B.md).
- [ ] Sustituir imports de `predictor.py` en `ia/service.py`; actualizar también ruta alias de Citas, métricas, dataset-resumen y predicción por lote.
- [ ] Mantener comprobación de rol/estado, snapshot, versión, explicación, persistencia y auditoría en backend.
- [ ] Implementar reglas de validación de respuesta, concurrencia, lote y fallos de sección 6.3.
- [ ] Propagar ID de correlación; no reenviar JWT a IA.
- [ ] Sustituir tests que monkeypatchean predictor local por dobles del puerto predictivo; separar tests HTTP contra IA real.
- [ ] Probar IA caída, lenta, clave inválida, modelo ausente, respuesta malformada y cambio de versión a mitad de lote.
- [ ] Solo después de paridad y regresión, retirar copia matemática/generador integrada y dependencias ML del backend.
- [ ] Mantener Joblib/NumPy/scikit-learn/LightGBM únicamente donde se utilicen; revisar otros scripts/tests antes de quitar paquetes o `libgomp1` del Dockerfile backend.
- [ ] Reproducir instalaciones con versiones fijadas; separar dependencias de tests sin actualizar librerías por iniciativa de la migración.

**Se toca:** integración/backend IA, tests, configuración y dependencias extraídas.

**No se toca:** tablas, permisos, rutas públicas, modo de guardar versiones ni estado de citas al fallar IA.

**Configurar:** `IA_URL` real por entorno, clave igual en backend/IA, timeout; CORS solo para navegador-backend. Backend startup/readiness no debe depender de IA.

**Aceptación:** backend operativo sin librerías ML y sin IA; inferencia exitosa cuando vuelve el servicio; predicciones guardadas y métricas compatibles; no queda fallback silencioso al predictor antiguo.

**Retorno:** recuperar adaptador anterior desde entrega etiquetada mientras exista compatibilidad y modelo preservado. No conservar dos motores activos indefinidamente ni cambiar de motor silenciosamente por error HTTP.

#### Fase 8 — Consolidar frontend sin perder funcionalidad

**Objetivo:** una única organización activa de UI y consumidores consistentes.

- [ ] Mapear imports reales de `pages/`, `auth/`, `components/`, `lib/` y equivalentes en `nucleo/`/`modulos/`; revisar también tests y entradas alternativas.
- [ ] Comparar pantallas antiguas con nuevas antes de migrar. En particular, verificar si `pages/ModeloIA.jsx` contiene funcionalidad no expuesta por los módulos actuales.
- [ ] Consolidar features en `modulos/` y utilidades compartidas en `nucleo/`; mantener tests/cambios pequeños por funcionalidad.
- [ ] Mantener rutas públicas, redirects, deep links, permisos, menú por rol y descubrimiento `rutas.tsx`/`menu.ts`.
- [ ] Tratar `prueba-ranura` como soporte de pruebas: preservar la prueba de descubrimiento sin exponer un módulo de demostración al usuario final; hacerlo mediante fixture/configuración de test explícita.
- [ ] Centralizar URL y transporte HTTP, incluidos `descargas.ts` y `lista-espera/exportar.ts`; preservar descargas binarias, nombres y MIME, no forzarlas por un cliente exclusivamente JSON.
- [ ] Conservar `sessionStorage`, manejo de 401 tardío, expiración, cancelación de fetch y protección de sesión nueva.
- [ ] Mostrar IA no disponible sin bloquear bandeja, confirmación o atención. Distinguir sin predicción, fallo técnico y riesgo BAJO.
- [ ] Mantener estados de carga/error/vacío, validaciones de formulario, rótulo sintético y accesibilidad básica.
- [ ] Actualizar imports y tests antes de retirar archivos antiguos. Evitar conversión masiva JS→TS o rediseño visual no solicitado.

**Se toca:** organización/frontend, cliente compartido, UI necesaria para errores de integración y tests.

**No se toca:** branding/diseño por iniciativa propia, semántica API, reglas backend, almacenamiento real de datos o modelo.

**Configurar:** `VITE_API_URL`, origen CORS, tipos frontend alineados con contratos y salidas de cobertura/capturas.

**Aceptación:** build/typecheck/lint/tests y navegación por tres roles; no referencias vivas a estructura retirada; deep links y descargas funcionan; IA caída no inutiliza pantallas operativas.

**Retorno:** volver por módulo a versión frontend anterior compatible con backend; no tocar BD.

#### Fase 9 — Compose oficial, configuración y bootstrap local

**Objetivo:** iniciar el proyecto completo desde la raíz sin conocimiento implícito.

- [ ] Consolidar `compose.yaml` con `db`, `migraciones`, `backend`, `ia`, `frontend` y tareas por perfil para preparación/entrenamiento/seed/pruebas.
- [ ] Crear `scripts/bootstrap.ps1` idempotente y documentado; validar herramientas, `.env`, paths, puertos, volumen elegido y permisos antes de escribir datos.
- [ ] Ofrecer modos explícitos: **Existing** preserva y valida datos/modelo; **FreshDemo** exige BD nueva vacía autorizada y prepara sintéticos/modelo/usuarios; **Verify** no siembra ni entrena.
- [ ] El bootstrap no sobrescribe `.env`, no rota contraseñas ni promueve modelos existentes sin confirmación. Si falta configuración, explica cómo completarla.
- [ ] Definir perfiles Compose `setup`, `training`, `test` o equivalentes; que no arranquen procesos destructivos al ejecutar `up` normal.
- [ ] Implementar dependencias: DB saludable → migrador puntual exitoso → backend; IA con artefacto listo en paralelo; frontend inicia con backend disponible. No condicionar arranque backend a IA saludable.
- [ ] Para FreshDemo, el bootstrap espera readiness IA antes de declarar stack completo; no confundir degradación aceptada del backend con instalación completa exitosa.
- [ ] Mover init BD a infraestructura, asegurar creación de rol antes de migración y manejar volúmenes ya inicializados donde los init scripts no se reejecutan.
- [ ] Diferenciar proceso vivo y listo: `/health` existente se mantiene compatible; agregar comprobación real de BD para readiness backend sin exigir IA. Healthcheck no debe usar solo `/docs` como prueba de dependencias.
- [ ] Inyectar owner solo en tareas de administración. Backend permanente e IA sin credenciales administrativas.
- [ ] Revisar `restart`, tiempos de gracia, límites razonables y logs por servicio; los procesos puntuales terminan con código útil y no reinician en bucle.
- [ ] Mantener un único nombre/volumen, sin colisiones con Compose históricos. Archivar instrucciones anteriores y retirar entradas ambiguas solo tras verificación.
- [ ] Implementar preparación de directorios, incluidas `Skills` vacías; no agregar `.gitkeep` dentro de ellas.
- [ ] Documentar ejecución nativa: Python/venv separados, Node, BD/roles, migraciones, dataset/artefacto explícito, IA, backend y frontend en terminales separadas.

**Se toca:** infraestructura, Dockerfiles si procede, ejemplos de entorno, scripts de operación y documentación de arranque.

**No se toca:** datos de usuarios existentes, modelos activos sin autorización, historial Alembic o reglas de negocio.

**Configurar:** matriz sección 7 completa y renderizado verificado por `docker compose config`, protegiendo su salida si incluye secretos. No añadir nginx/HTTPS como requisito del demo local.

**Aceptación:** Existing conserva datos y FreshDemo parte de entorno aislado vacío y funciona; Verify no altera BD/modelo; reiniciar preserva datos; backend sigue disponible si IA falla.

**Retorno:** configuración Compose/imagen previa apuntando al volumen correcto, sin `down -v`. Si se seleccionó otro volumen, conservar ambos y cambiar referencia de forma controlada.

#### Fase 10 — Validación integral y controles de regresión

**Objetivo:** demostrar que la organización nueva funciona y mantiene límites.

- [ ] Ejecutar matriz de sección 9 en PostgreSQL real de pruebas y entorno E2E aislado.
- [ ] Mantener mínimo 75% de cobertura backend/frontend y medir cobertura IA definida en fase 1; no reducir umbrales para terminar.
- [ ] Tests de arquitectura: backend sin imports ML/IA app, IA sin imports backend/SQL operativo, frontend sin credenciales internas, módulos sin dependencias prohibidas/ciclos.
- [ ] Tests de contratos backend-frontend e IA; snapshot OpenAPI con diferencias revisadas, no regenerado ciegamente para ocultarlas.
- [ ] Comparar BD antes/después, restricciones, permisos, historial y auditoría. Probar migraciones tanto desde baseline existente como instalación nueva.
- [ ] Probar dos reasignaciones simultáneas, dos predicciones de misma versión, cambio de cita durante inferencia y fallos después de flush antes de commit.
- [ ] Parar solo IA y demostrar degradación controlada; reiniciarla y repetir inferencia sin reiniciar ni borrar BD.
- [ ] Probar modelo corrupto/ausente/incompatible en copia aislada, no dañando el activo real.
- [ ] Verificar límites CSV/lote, fechas, BOM, duplicados, opt-out y ausencia de cancelación/liberación por silencio.
- [ ] Medir arranque frío/caliente, latencias de inferencia/lote y RAM. Registrar valores medidos y presupuesto acordado, no afirmar mejoras sin datos.
- [ ] Buscar secretos y rutas antiguas/absolutas en archivos activos, imágenes y logs; referencias históricas se permiten si están identificadas.
- [ ] Crear `scripts/smoke.ps1` que verifique servicios, login/demo, lectura e inferencia opcional con resultados claros; escrituras de prueba solo en entorno aislado o con autorización explícita.
- [ ] Integrar validaciones reproducibles por script y pipeline CI cuando exista remoto/proveedor acordado. No asumir GitHub ni publicar repositorio por esta tarea.

**Se toca:** pruebas, scripts de validación, correcciones concretas de regresión y evidencia.

**No se toca:** baseline para ocultar diferencias, umbrales de cobertura, seguridad BD o datos demo reales bajo pretexto de tests.

**Configurar:** BD/test volúmenes separados, secretos ficticios de tests y salida `runtime/test-results/`.

**Aceptación:** matriz crítica pasa; fallos previos no críticos documentados y aceptados; ninguna regresión crítica abierta; recuperación de backup y modelo demostrada.

**Retorno:** detener corte final y volver a fase responsable del fallo; no declarar cierre parcial como migración completa.

#### Fase 11 — Corte, documentación final y cierre

**Objetivo:** dejar una única estructura vigente y una guía local probada.

- [ ] Fijar ventana de corte, detener escritores, respaldar otra vez y registrar conteos/revisión/modelo justo antes de cambiar el stack local principal.
- [ ] Aplicar estructura/configuración validadas; ejecutar migrador si hay revisiones nuevas aprobadas. No sembrar sobre datos existentes por defecto.
- [ ] Ejecutar smoke y recorrido manual por tres roles; verificar persistencia tras reinicio.
- [ ] Crear README raíz con requisitos, arranque Existing/FreshDemo/Verify, URLs, errores comunes, recuperación y enlaces a contratos.
- [ ] Clasificar documentos previos en `docs/`, conservar fechas y distinguir diseño antiguo de arquitectura vigente. Corregir enlaces y referencias `contratos/comun.json` solo tras localizar o sustituir esa fuente explícitamente.
- [ ] Consolidar o retirar archivos/configuraciones antiguas únicamente con evidencia de cero consumidores y respaldo. No borrar históricos válidos ni evidencias de pruebas.
- [ ] Confirmar `apps/frontend/Skills/` y `apps/backend/Skills/` existen y siguen vacías.
- [ ] Actualizar todos los checklists y bitácoras con fechas reales, comandos ejecutados, resultados y limitaciones pendientes.
- [ ] Conservar último backup y versión anterior hasta aceptación del equipo y cumplimiento de la política de retención acordada.

**Se toca:** documentación vigente, referencias restantes, configuración de corte y limpieza aprobada.

**No se toca:** funcionalidades adicionales, aumento de dataset, nuevos canales reales de mensajería ni decisiones clínicas automatizadas.

**Configurar:** punto de retorno final, acceso a backups y responsables de mantenimiento.

**Aceptación:** definición de terminado de sección 12 completa y equipo capaz de arrancar siguiendo únicamente README.

**Retorno:** detener escrituras, volver a imágenes/config compatibles y volumen correcto. Restaurar BD solo si es necesario y tras preservar operaciones posteriores al respaldo; restaurar un dump antiguo puede perder datos nuevos.

## 9. Matriz mínima de pruebas y evidencia

| Área | Casos obligatorios | Evidencia esperada |
|---|---|---|
| Arranque | FreshDemo, Existing, Verify y reinicio | Comandos, exit codes, servicios saludables y conteos |
| BD | Instalación vacía y actualización desde copia existente | Alembic head, mismas entidades/IDs, permisos y triggers |
| Identidad | Login correcto/incorrecto, bloqueo, expiración, revocación y usuario inactivo | pytest/integración y prueba UI por rol |
| RBAC | Acceso autorizado/no autorizado a cada familia de endpoints | Matriz rol×operación, no solo ocultar menú |
| CSV | Válido, BOM, vacío, demasiado grande, >5.000, duplicados, celdas vacías y filas inválidas | Conteos y motivos estables, hashes y no doble importación |
| Fechas | Lima, offsets, domingo, desenlace futuro y registro posterior a cita | Tests con reloj controlado |
| Citas | Estados legales/ilegales, check-in y desenlaces | Un historial por transición y target correcto |
| IA | Predicción individual, alias Citas, lote/forzar, métricas, dataset y consulta histórica | Contratos, paridad y snapshot persistido |
| Resiliencia IA | Timeout, desconexión, clave mala, modelo ausente y JSON inválido | Error visible y operación no predictiva funcionando |
| Concurrencia IA | Cita modificada durante cálculo, versión cambiada y duplicados simultáneos | Sin predicciones obsoletas ni violación silenciosa de unicidad |
| Intervenciones | Consentimiento, opt-out, límite de contactos, confirmación y liberación voluntaria | Reglas vigentes preservadas; resolver discrepancias documentales antes de aceptar |
| Silencio paciente | No responde al contacto | No cancela ni libera cita automáticamente |
| Cupos | Compatibilidad, oferta, rechazo, desistimiento y doble reasignación | Una asignación, confirmación humana y trazabilidad |
| Transacciones | Fallo entre escritura de cita, cupo, historial y auditoría | Todo o nada por caso de uso; fallos de login registrados aparte |
| Reportes | Filtros, datos, permisos y exportación JSON/CSV/Excel existentes | MIME/filename correctos, sin fórmulas peligrosas |
| UI | Login, menú, deep link, recarga, logout, carga/error/vacío | Vitest y E2E/manual reproducible |
| Sesión UI | 401 antiguo y sesión nueva, cancelación y expiración | Pruebas actuales no degradadas |
| Datos/archivos | Paths nuevos, no exposición pública, permisos no-root y limpieza | Inventario, inspección de mounts y tests |
| Arquitectura | Imports/ciclos/escrituras fuera de propietario | Tests automáticos y excepciones justificadas |
| Reproducibilidad | Misma fuente/semilla/split y promoción de versión | Manifiestos/hashes, no garantía de igualdad bit a bit entre plataformas distintas |
| Recuperación | Restore DB aislado y rollback del modelo | Procedimiento ejecutado con resultados verificables |

No usar SQLite para dar por probados RLS, JSONB, locks o triggers específicos de PostgreSQL. Los tests de BD existentes deben seguir verificándose en PostgreSQL.

## 10. Operación local objetivo

**Esta sección describe el resultado a implementar en fases 9–11. No ejecutar estos comandos como si los scripts ya existieran.** Los parámetros del bootstrap quedan fijados como interfaz objetivo; su implementación debe documentar y validar exactamente estas opciones.

### Camino A — Conservar datos existentes

1. Verificar backup/restauración y elegir `PGDATA_VOLUME_NAME` real.
2. Preparar `.env` privado con credenciales reales existentes, clave IA, puertos y paths.
3. Ejecutar desde la raíz en PowerShell:

```powershell
.\scripts\bootstrap.ps1 -Mode Existing
docker compose -f compose.yaml --env-file .env up -d --build
.\scripts\smoke.ps1
```

`Existing` verifica modelo compatible y revisión; si falta artefacto no entrena silenciosamente: explica cómo preparar uno explícitamente. No ejecuta seed ni vacía BD. Debe aplicar migraciones pendientes solo si están aprobadas y el respaldo está confirmado.

### Camino B — Demo nueva aislada

Seleccionar volumen nuevo inequívoco, sin reutilizar uno con datos. El script debe rechazar BD no vacía en este modo salvo procedimiento de adopción explícito, nunca borrarla.

```powershell
.\scripts\bootstrap.ps1 -Mode FreshDemo -ReferenceDate 2026-11-03
docker compose -f compose.yaml --env-file .env up -d --build
.\scripts\smoke.ps1
```

La fecha es ejemplo reproducible, no promesa de citas futuras permanentemente. Para una demo en otra fecha elegir referencia explícita y nueva versión de datos; respetar calendario piloto.

El bootstrap implementa en orden: preflight → directorios/config → BD/rol → migraciones → generación explícita dataset y CSV seed → entrenamiento/verificación/promoción → seed autorizado → arranque servicios → readiness → resumen. Usa procesos puntuales y no entrena en el servidor API.

### Camino C — Verificación sin regeneración

```powershell
.\scripts\bootstrap.ps1 -Mode Verify
docker compose -f compose.yaml --env-file .env ps
```

Verify inspecciona configuración/servicios/modelo/revisión y no siembra, migra, entrena, promueve ni cambia credenciales. No imprimir el `.env` ni un Compose renderizado con secretos en evidencias compartidas.

### URLs y diagnóstico esperado

- UI: `http://localhost:5173`.
- Backend/docs: `http://localhost:8000/docs`.
- Salud backend existente: `/health`; readiness adicional documentado en implementación.
- IA: `http://127.0.0.1:8100/health/ready` solo si el puerto se publica en loopback.
- PostgreSQL: `localhost:<DB_PUERTO_HOST>` solo para herramientas locales autorizadas; dentro de Docker siempre `db:5432`.
- Consultar logs por servicio, comprobar rol DB, CORS y disponibilidad de modelo; no resolver fallos borrando volúmenes.
- `docker compose ... down` sin `-v` conserva volúmenes; antes de detener confirmar que es el proyecto correcto. No incluir borrado de datos en el comando habitual de parada.

### Alternativa nativa a documentar y probar

1. PostgreSQL 16 con roles correctos, o solo servicio DB en Docker.
2. Venv Python 3.12 del backend, instalar dependencias fijadas desde `apps/backend/`, `.env` local apuntando a host/puerto correctos, crear rol si falta y ejecutar Alembic.
3. Venv independiente para `apps/ia/`; preparar dataset/artefacto con comandos documentados, cargar el modelo y servir en 8100.
4. Backend desde `apps/backend/` con `uvicorn app.main:app --host 127.0.0.1 --port 8000`, `IA_URL=http://127.0.0.1:8100` y credenciales operativas.
5. Frontend desde `apps/frontend/`: `npm ci`, `npm run dev -- --host 127.0.0.1 --port 5173` y `VITE_API_URL` del navegador.
6. No copiar comandos de entrenamiento no implementados: el README final debe contener los nombres/flags reales probados. No compartir venv ni ejecutar ambas apps Python desde un `PYTHONPATH` global.

### Verificaciones por aplicación

Ejecutar cada comando desde la carpeta indicada y registrar resultado/exit code. Son verificaciones para la estructura objetivo; no constituyen evidencia de que ya se ejecutaron.

| Carpeta objetivo | Comandos/validaciones |
|---|---|
| `apps/frontend/` | `npm ci`, `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build` |
| `apps/backend/` | Instalación de requirements runtime/dev, `alembic heads`, `alembic current`, `python -m pytest`; solo con BD de pruebas aislada para pytest |
| `apps/ia/` | Instalación de requirements runtime/dev y `python -m pytest` con registry/dataset de fixtures, nunca modificando el modelo activo |
| Raíz | Verificación de contratos, pruebas E2E y smoke con los comandos efectivamente implementados y documentados en fases 9–10 |

El test suite backend importa configuración y engine al cargar módulos: establecer y validar las variables de la BD de pruebas **antes** de arrancar pytest, no después. No ejecutar tests dentro del backend operativo usando sin cambios su `DATABASE_URL`.

## 11. Riesgos y decisiones que pueden bloquear

| Riesgo | Prevención/respuesta |
|---|---|
| Se ve BD vacía tras mover Compose | Inspeccionar nombre/volumen; detener y corregir referencia, no sembrar inmediatamente |
| `.env` nuevo con password diferente rompe conexión | Confirmar credenciales del volumen; `.env` no rota roles existentes |
| Init no corre en volumen existente | Ejecutar provisión idempotente autorizada, no reinicializar datos |
| Modelo no carga tras mover código | Verificar clases serializadas/dependencias en copia; conservar artefacto y entorno anterior |
| IA intenta escribir en ruta de código no-root | Servir RO; entrenamiento solo en mounts autorizados |
| Contexto Docker no contiene CSV/contratos | Usar mounts o empaquetado explícito; no ampliar contexto a todos los secretos de la raíz |
| CSV estático queda temporalmente obsoleto | Fechas de referencia/versionado; tests con reloj fijo y demos regenerables explícitas |
| Doble historial/auditoría al centralizar | Tests de unicidad lógica por transición y una transacción coordinadora |
| Refactor de usuario provoca múltiples modelos para misma tabla | Cambiar propietario e imports conjuntamente; un solo registro ORM |
| Lote mantiene locks durante HTTP | Snapshot fuera de transacción larga, revalidación y guardado corto |
| Reentrenamiento silencioso cambia resultados | Sin fallback de dataset/modelo; promoción/versionado explícitos |
| Eliminación de archivos frontend pierde pantalla no migrada | Grafo de referencias y comparación funcional antes de retirar |
| Repositorios anidados/historial perdido | Estrategia de monorepositorio aprobada; conservar origen y backup |
| OneDrive bloquea/sincroniza archivos grandes | Volúmenes DB fuera de bind mount y paths de datos/artefactos configurables |
| Tests escriben sobre BD de demo | URL/nombre test explícitos y guardas antes de importar engine/ejecutar fixtures |
| Se prometen funcionalidades no terminadas | Baseline funcional explícita; separar migración de ampliación de alcance |
| Políticas documentadas no coinciden con código | Registrar decisión y pruebas; no corregir silenciosamente durante movimientos |

## 12. Definición de terminado

- [ ] Un repositorio/estrategia aprobada con aplicaciones, contratos, infraestructura, datos y documentación separados.
- [ ] `apps/frontend/Skills/` y `apps/backend/Skills/` existen y están completamente vacías.
- [ ] Un Compose oficial y nombres de proyecto/volumen inequívocos.
- [ ] README probado en equipo/entorno limpio y procedimiento de adopción de BD existente probado.
- [ ] Sin pérdida de citas, usuarios, predicciones, auditoría, historial, IDs, claves o secuencias existentes.
- [ ] Migraciones preservadas; permisos, triggers y RLS verificados sin atribuirles garantías no implementadas.
- [ ] CSV/fixtures/datasets/modelos con rutas y propietarios documentados, sin exposición pública o secretos versionados.
- [ ] Backend modular con contratos, propietarios y transacciones coherentes; routers sin SQL/commits.
- [ ] IA realmente independiente, sin credenciales/imports backend y sin entrenamiento en inferencia.
- [ ] Backend sin dependencias ML innecesarias y capaz de operar cuando IA no está disponible.
- [ ] Contratos públicos mantenidos y nuevos errores documentados; frontend maneja degradación IA.
- [ ] Modelo/dataset/umbral versionados, promoción y rollback comprobados.
- [ ] Pruebas unitarias, BD, contratos, arquitectura y recorrido E2E aprobados con cobertura sin rebajas.
- [ ] FreshDemo, Existing, Verify y reinicio validados; ningún camino habitual elimina datos.
- [ ] Backup restaurado en entorno aislado y rollback de modelo demostrados.
- [ ] Cero regresiones críticas abiertas; limitaciones previas y cambios aprobados identificados.
- [ ] Documentación histórica conservada y arquitectura vigente claramente distinguida.
- [ ] Todas las fases cerradas con evidencia real, no solo checklists marcados.

## 13. Bitácora para retomar el trabajo

Actualizar este documento al iniciar y cerrar cada fase. Guardar evidencias detalladas en `docs/migracion/fase-XX/`, sin secretos. Antes de retomar, leer el último registro, comprobar archivos reales y ejecutar la validación de la fase anterior.

### Plantilla por fase/entrega

```text
Fase / subentrega:
Estado: PENDIENTE | EN CURSO | BLOQUEADA | COMPLETADA
Fecha real y responsable:
Objetivo de esta sesión:
Punto de partida / commit o snapshot:
Archivos y rutas afectados:
Archivos y comportamientos deliberadamente no tocados:
Cambios de configuración (nombres, nunca valores secretos):
Movimientos realizados y hashes relevantes:
Cambios de lógica / esquema (si los hubo y aprobación):
Comandos ejecutados y directorio de ejecución:
Pruebas ejecutadas, resultado, duración y cobertura:
Evidencia antes/después:
Datos / volumen / revisión Alembic preservados:
Modelo / dataset / contrato activos:
Fallos previos frente a regresiones nuevas:
Pendientes y bloqueos:
Procedimiento y punto de retorno:
Próxima acción concreta:
Aceptación de fase y fecha:
```

### Registro inicial de esta entrega

- **Tipo:** planificación, no implementación de la arquitectura.
- **Creado:** este documento y las dos carpetas `Skills` vacías en las aplicaciones actuales.
- **Sin modificar:** código, modelos, datos, CSV, `.env`, Dockerfiles, Compose, migraciones y pruebas existentes.
- **Validación de esta entrega:** comprobar existencia del Markdown, presencia/vaciedad de `Skills` y correspondencia del plan con archivos inspeccionados. No se ejecutó la matriz funcional de la migración.
- **Siguiente acción:** fase 0 — inventario operativo, respaldo/restauración y baseline en entorno aislado.

### Ejecución de fase 0 — 3 de noviembre de 2026

- **Estado:** EN CURSO, con pendientes explícitos; no declarar la fase completada ni iniciar movimientos.
- **Trabajo retomado:** snapshot Git `69c686f21fd1938dc76d679f4c6b33270f10a6d7` creado por el agente anterior; se conservó sin cambios de historial.
- **Realizado:** inventario de archivos/configuración, copias RO de tres volúmenes, dumps y globals privados, restauración lógica CRP verificada, migraciones en BD de pruebas vacía, pruebas backend/frontend, smoke API por tres roles, navegador de Recepción y fixtures/predicciones IA.
- **Respaldo privado duradero:** `C:\Users\arami\AppData\Local\PrediCitasBackups\fase0-20261103-2200`, fuera de OneDrive y Temp, con acceso restringido. Sigue en el mismo equipo; copia externa cifrada recomendada.
- **Sin tocar:** 302 archivos originales verificados (salvo este plan y metadata Git), tres volúmenes originales con hashes TAR idénticos, CSV, modelo, secretos y lógica existentes. `Skills` siguen vacías.
- **Límites:** errores previos documentados, resolución limpia Python bloqueada por red, capturas pendientes por ventana no visible y volumen principal sin aceptación definitiva.
- **Recursos:** laboratorios aislados detenidos, volúmenes preservados; ningún servicio original fue arrancado. No se borraron recursos ajenos.
- **Evidencia y próximos pasos:** leer [docs/migracion/fase-00/README.md](docs/migracion/fase-00/README.md) y confirmar qué volumen conservar como principal; no corregir fallos mezclándolos con la mudanza.

### Continuación y cierre de fase 0 — 3 de noviembre de 2026

- **Estado actual:** COMPLETADA en su alcance de inventario, respaldo, recuperación y línea base; el registro EN CURSO anterior es histórico.
- **Decisiones del usuario:** `predicitas-crp_pgdata` principal; evidencia funcional aceptada en lugar de capturas sin ventana visible. Los otros volúmenes siguen preservados.
- **Verificaciones nuevas:** instalación real en venv Python 3.12.16 sin paquetes de sistema, 54 requirements fijados coincidentes, `pip check` código 0; tres cuentas demo históricas verificadas por hash sin exponer claves; login y bandeja revalidados.
- **Integridad:** 302 archivos originales y los tres TAR de volúmenes con hashes iniciales; 11 respaldos duraderos revalidados. Sin cambios de lógica/configuración/datos originales ni commits automáticos.
- **Pendientes transferidos, no ocultados:** fallos anteriores de pruebas/TypeScript, auditoría moderada npm, configuración nativa divergente y dependencias transitivas a estabilizar. No se declara aprobación funcional.
- **Recursos:** continuación de laboratorio cerrada; servicios temporales detenidos, volúmenes y recursos ajenos preservados.
- **Siguiente paso:** fase 1 — contratos y decisiones. Permanece PENDIENTE en esta entrega; no se ejecutó ninguna mudanza.
- **Detalle y punto de retorno:** [cierre técnico](docs/migracion/fase-00/CIERRE_FASE_0.md), snapshot `69c686f`, dumps/TAR/ZIP privados verificados y ZIP adicional de cierre.

### Ejecución y cierre de fase 1 — 3 de noviembre de 2026

- **Estado:** COMPLETADA en alcance documental/de contratos. Fase 2 sigue PENDIENTE; ninguna mudanza ni arreglo de lógica aplicado.
- **Entregables:** ocho ADRs, mapa de dependencias/escrituras, rutas/consumidores/permisos, contratos actuales frente a objetivo, doce JSON Schemas, OpenAPI IA, sesenta fixtures, especificación E2E y estabilización separada.
- **Verificado:** 55 operaciones AST/OpenAPI, 15 rutas UI productivas y una test-only, 12 schemas/60 casos con resultados esperados, refs locales, ocho casos de fila normalizada y dos CSV contra validadores reales en contenedor sin red/BD. Alias REP-02 incompatible confirmado por firma, no por ejecución HTTP.
- **Decisiones:** conservar volumen existente principal; Compose `predicitas-crp`, BD host 5432 configurable; precisión y lotes preservados; modelo legacy declara linaje incompleto cuando no hay archivos originales, sin hashes/fechas inventados.
- **Sin tocar:** aplicaciones, secretos, CSV/modelo existentes, dependencias runtime, migraciones o volumen principal. Herramientas de validación solo en Temp. Sin commits automáticos.
- **Limitaciones:** validaciones documentales, no suite funcional nueva ni OpenAPI formal completo. Los fallos previos permanecen abiertos y no se atribuyen a la migración.
- **Siguiente acción recomendada:** entrega mínima S-01 de estabilización de build/typecheck y luego fase 2 mecánica; diffs y pruebas separados. No saltar a extracción IA.
- **Evidencias y retorno:** [README de fase 1](docs/migracion/fase-01/README.md), snapshot/respaldos de fase 0 y ZIP privado adicional de esta entrega. No sobrescribir evidencia histórica al repetir validaciones.

### Ejecución de fase 2 — 4 de noviembre de 2026

- **Estado:** COMPLETADA; mudanza mecánica consolidada y gate de lint en Registrar.tsx resuelto.
- **Punto de retorno:** commit `80e3ce2`, limpio al comenzar, que ya contiene S-01 y ajustes backend del usuario. No se alteró su lógica ni se crearon commits automáticos.
- **Movimientos:** `backend-predicitas/` → `apps/backend/`; `frontend-predicitas/` → `apps/frontend/`. 286 archivos verificados byte a byte al mover. Skills vacías; `node_modules` previo conservado fuera del proyecto e instalación nueva `npm ci` sin modificar lockfile.
- **Configuración:** `compose.yaml` raíz con contextos/montaje init nuevos, volumen externo físico explícito, seed fuera del arranque normal y owner restringido a tareas admin. Compose antiguos archivados como referencias no operativas. README raíz y reglas ignore actualizados.
- **Sin tocar:** fuentes/tests de aplicaciones, reglas, endpoints, modelo, CSV, versiones de dependencias, migraciones, secretos ni volúmenes originales. No seed, entrenamiento, extracción IA ni consolidación UI.
- **Validaciones antes/después:** typecheck/build pasan; lint conserva error `react-refresh/only-export-components` en `Registrar.tsx:16`; frontend 451/56 con los mismos casos fallidos; backend completo conserva error de colección `app.modules.ia.cliente`, diagnóstico 218/1 con cobertura 87,13 %. No se bajó el umbral 75 %.
- **Paridad:** OpenAPI, smoke por tres roles, tres predicciones fijas, bytes/hash del modelo, resultados JUnit y tests UI idénticos. Backend empaquetado no-root con rol `predicitas_app`, sin DSN owner, 54 pins coincidentes; build frontend en Node 22 aprobado.
- **Arranque:** imágenes nuevas construidas y stack Compose probado exclusivamente sobre clon de CRP, con puertos de laboratorio distintos. HTTP API/UI/deep link aprobados; Alembic `m01_001_indices_auditoria`, nueve tablas, fingerprints, secuencias, constraints, triggers, permisos y RLS conservados tras arranque y recreación controlada. No se certifica inspección visual completa.
- **Integridad:** tres volúmenes originales idénticos por hash TAR antes/después y tres `.env` intactos; 1.122 citas preservadas. Respaldo privado previo y adicional de cierre; ver manifiestos sin secretos en evidencia.
- **Recursos:** solo laboratorio nuevo detenido al finalizar; contenedores/volúmenes preservados. Los servicios originales nunca se arrancaron. No hay corte del stack principal en esta entrega.
- **Incidentes de laboratorio:** primera suite UI interrumpida por timeout y repetida completa; guarda Compose de perfil corregida antes del build; red interna del override impedía publicar puertos en Docker Desktop, corregida solo en laboratorio y recreada sin eliminar volúmenes. Evidencias anteriores preservadas.
- **Siguiente acción:** fase 3 — centralización de archivos y datasets.
- **Detalle/retorno:** [docs/migracion/fase-02/README.md](docs/migracion/fase-02/README.md), `preparacion.json`, `movimientos.json`, `comparacion.json`, verificaciones de integridad y respaldo privado de cierre. No restaurar BD innecesariamente ni descartar cambios posteriores.

### Ejecución inicial de fase 3 — registro histórico del 5 de noviembre de 2026

Los números de este apartado corresponden a la ejecución inicial (31 pruebas), no a la revalidación vigente `cierre-20261105-02` (43 pruebas) descrita arriba. Los archivos históricos no se sobrescriben.

- **Estado:** COMPLETADA; fase 4 permanece PENDIENTE. Usuario exigió confirmación para acciones críticas/de alto riesgo; ninguna fue necesaria ni ejecutada.
- **Punto de retorno:** `a5a1f5f`, árbol limpio. Respaldo privado previo con ACL restringida de 444 archivos y revalidación del ZIP de fase 2; copia adicional privada de cierre con evidencia cruda.
- **Datos:** dos muestras canónicas en `data/samples/importacion/`, por copias byte a byte; CSV legacy preservados por compatibilidad. Guías activas corregidas. Cuatro fixtures frontend y fixtures de contrato intactos; no modificar datos históricos ni inventar fecha/semilla originales.
- **Artefactos:** snapshot readonly de preservación en `artifacts/models/legacy-import/`, hash idéntico; fuente activa original intacta. Sin cargar/promover copia, entrenar, crear active.json ni atribuir linaje completo al legacy.
- **Herramientas:** CLI exige salida absoluta nueva y fecha explícita, no sobrescribe, no escribe en código, proyecta 13 columnas; generador/negocio/contratos sin cambios. QA escribe resultados nuevos por ID en runtime y valida nombre explícito de BD test/qa antes de conectar. Sin reescribir evidencia previa.
- **Runtime/Docker:** políticas documentadas, datos raw/processed vacíos, outputs ignorados. Contextos por app conservados; datos legacy/secretos fuera de imagen y modelo activo integrado incluido. API mantiene memoria/streaming, sin retención ni tareas de borrado.
- **Validación:** 31 nuevas pruebas pasan; API canónica 40/0 y 20/4, UTF-8/BOM, segunda carga sin duplicar, rollback de usuarios/citas/historial/auditoría. OpenAPI y tres predicciones congeladas idénticos. CLI en imagen no-root sin red/credenciales funciona con montaje destino explícito y rechaza sobrescritura.
- **Regresión:** typecheck/lint/build frontend pasan; frontend 451/56 con los mismos casos; backend diagnóstico 249/1, siendo 31 nuevas aprobadas y mismos casos previos 218/1; cobertura 87,13 %, umbral 75 % intacto. Suite completa conserva error previo de colección IA. No se certifica E2E visual completo ni se ocultan defectos de S-02..S-13.
- **Aislamiento:** solo BD nueva `predicitas_fase3_test`, volumen nuevo inequívoco y contraseñas aleatorias privadas. Historial Alembic existente aplicado solo a test vacío; sin revisión nueva ni seed. Volúmenes originales no montados/arrancados, `.env` y fuentes de negocio intactos.
- **Recursos:** servidor nuevo detenido; contenedor/red/volumen y recursos previos preservados, sin `down -v` ni limpieza recursiva.
- **Retorno/continuación:** respaldos y `docs/migracion/fase-03/README.md`; revertir únicamente herramientas/referencias de esta entrega preservando trabajo posterior, no restaurar BD. Próxima entrega: fase 4; retirar duplicados, cambiar modelo o intervenir principal requiere revisión/confirmación independiente.
