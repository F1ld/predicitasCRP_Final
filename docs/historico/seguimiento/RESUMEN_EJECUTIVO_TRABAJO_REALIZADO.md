# Resumen Ejecutivo y Bitácora de Trabajo Realizado
**Proyecto:** PrediCitas CRP — Clínica Ricardo Palma (Sede San Isidro)  
**Fecha de corte:** 30 de Octubre de 2026 (Proyección de Hito: 05 de Noviembre de 2026)  
**Ramas de trabajo activas:**
- **Backend:** `feature/ia-motor-prediccion-v1`
- **Frontend:** `feature/vistas-clinicas-ia-v1`

---

## 1. Higienización y Limpieza del Árbol Git

Se llevó a cabo una depuración exhaustiva de ramas obsoletas y desfasadas en ambos repositorios oficiales dentro de `D:\Documentos\REPOS_OFICIALES\`:

1. **Backend (`backend-predicitas`):**
   - Se verificó la rama activa oficial: `feature/ia-motor-prediccion-v1`.
   - Se eliminó la rama remota obsoleta en GitHub: `feature/motor-predictivo-ia-y-modulos`.
   - Se eliminó la rama localmente de forma forzada (`git branch -D`).
   - Se ejecutó `git fetch --prune origin` para purgar referencias remotas huérfanas.
2. **Frontend (`frontend-predicitas`):**
   - Se verificó la rama activa oficial: `feature/vistas-clinicas-ia-v1`.
   - Se eliminó la rama remota obsoleta en GitHub: `feature/interfaz-clinica-modelo-ia`.
   - Se eliminó la rama localmente de forma forzada.
   - Se podaron las referencias remotas con `git fetch --prune origin`.

**Resultado:** Árbol de Git 100% higienizado, conservando únicamente `main` y las ramas activas de integración oficial.

---

## 2. Migración y Consolidación de Documentación Técnica

Se trasladó toda la documentación de gestión y auditoría desde la ruta previa `D:\Documentos\SISTEMA\` hacia la raíz oficial `D:\Documentos\REPOS_OFICIALES\`:

- Carpeta académica de gestión completa: `ADM. DE PROYECTOS DE SOFTWARE_Grupo5/` (WBS/EDT, actas de constitución, especificación SRS, matrices de trazabilidad).
- Documentos Markdown de auditoría y arquitectura:
  - `AUDITORIA_CRONOGRAMA_04_NOVIEMBRE.md`
  - `DIAGNOSTICO_BD_Y_DISENO_DATASET_IA.md`
  - `DISEÑO_BD_PREDICCION_CITAS.md`
  - `ESPECIFICACION_SISTEMA_Y_ESTADO_ACTUAL.md`
  - `ESTADO_CONFORMIDAD_CRONOGRAMA_Y_PRUEBAS_CSV.md`
  - `EXPLICACION_ENTRENAMIENTO_DATASET_Y_PESOS_IA.md`
  - `Recursos/` (diagramas de arquitectura, flujo asistencial y mockups).

---

## 3. Auditoría Integral de Conformidad (Hito: 05 de Noviembre de 2026)

Se elaboró y publicó el informe formal: `INFORME_CONFORMIDAD_CRONOGRAMA_05_NOVIEMBRE.md`.

### Principales conclusiones de la auditoría:
- **Alineación con el Cronograma:** Avance físico del **96.5%** sobre la EDT planificada al 05 de noviembre.
- **Módulos auditados y conformes:**
  - **M01 (Autenticación y Seguridad):** Roles estrictos (`ADMINISTRADOR`, `RECEPCION`, `TECNICO_IA`), tokens JWT, políticas de inactividad (RNF-004, RF-001/008).
  - **M02 (Gestión de Citas):** Ciclo de vida y transiciones de estado (`RECIBIDA`, `ATENDIDA`, `NO_SHOW`, `LIBERADA`), motor de validación de negocio.
  - **M04 (Motor Predictivo IA):** Modelo LightGBM entrenado (`modelo_predicitas_v1.joblib`), métricas de rendimiento (ROC-AUC = 0.887, F1 = 0.742, Brier Score = 0.091), clasificación de riesgo (ALTO/MEDIO/BAJO) y explicabilidad con TreeSHAP.
  - **M05 (Bandeja de Intervenciones):** Filtros por riesgo, registro de contacto preventivo y liberación formal de cupos asistenciales.
  - **M06 (Reasignación y Lista de Espera):** Detección de cupos liberados y recomendación con confirmación *Human-in-the-Loop*.
  - **Trazabilidad del Dataset:** Semilla determinista `42`, 1,000 citas históricas y 80 citas próximas de evaluación.

---

## 4. Reingeniería UX/UI de la Vista de Detalle de Cita (`/citas/:id`)

Se solucionaron deficiencias visuales y funcionales en el detalle asistencial:

1. **Resolución de Error 404 en Trazabilidad:**
   - Se eliminó el enlace roto a `/citas/:id/trazabilidad`.
   - Se implementó un timeline cronológico de auditoría y transiciones de estados (`RECIBIDA` -> `CONFIRMADA` -> `LIBERADA`, etc.) integrado con scroll suave y visualización de operador responsable.
2. **Prioridad Asistencial del Motor de IA:**
   - Se reubicó la tarjeta predictiva en el primer golpe de vista clínico (encabezado superior derecho).
   - Se integraron badges KPI destacados de riesgo (**ALTO**: carmín/ámbar, **MEDIO**: dorado, **BAJO**: verde clínico).
   - Desglose legible de los 3 principales factores explicables de SHAP (antelación de reserva, inasistencias previas, canal de confirmación).
   - Inclusión del rótulo ético obligatorio: *"Resultado predictivo orientativo — Dataset sintético acreditado (RF-056)"*.
3. **Jerarquización Cromática de Acciones:**
   - Botón de check-in / confirmación destacado.
   - Botón de liberación formal de cupos con modal de advertencia para evitar cancelaciones involuntarias.

---

## 5. Corrección de Errores Críticos en Vistas y Endpoints (5 Pantallas)

Se identificaron y corrigieron los siguientes incidentes visualizados en las capturas de pantalla:

| Ruta | Incidente detectado | Causa raíz | Solución implementada |
|---|---|---|---|
| `http://localhost:5173/` | Pantalla en blanco | Redirección de raíz con token expirado en navegador | Enrutador ajustado para redirección limpia a `/login` o `/citas`. |
| `http://localhost:5173/cupos` | "El recurso no existe" (404) | Falta de alias en router backend para `/cupos` | Creación de endpoints unificados `/cupos` y `/cupos-liberados`. Responde **HTTP 200 OK**. |
| `http://localhost:5173/lista-espera` | Pantalla en blanco | Incompatibilidad de esquema (backend devolvía array directo y frontend leía `.items.length`) | Esquema backend `PaginaCandidatoOut` y blindaje defensivo en `ListaEspera.tsx`. Responde **HTTP 200 OK**. |
| `http://localhost:5173/intervenciones` | "Método no permitido" (405) | Precedencia de rutas en FastAPI (`PATCH /{id}` tapaba `GET /elegibles`) | Reordenamiento de endpoints específicos antes de rutas parametrizadas. Responde **HTTP 200 OK**. |
| `http://localhost:5173/reportes/reasignaciones` | Registro no encontrado | Rutas REP-02 y REP-03 pendientes de registrar en router | Registro de endpoints `/reportes/rep-02` y `/reportes/rep-03`. Responde **HTTP 200 OK**. |

---

## 6. Generación de Dataset de Pruebas Heterogéneo

Para validar la importación masiva y el comportamiento predictivo de la IA frente a diversos perfiles de pacientes, se generó el archivo:
- **Ubicación:** `D:\Documentos\REPOS_OFICIALES\citas_para_importar_variado.csv`
- **Características:**
  - 40 citas médicas válidas para noviembre de 2026.
  - Distribución variada de especialidades (Cardiología, Pediatría, Traumatología, etc.).
  - Variabilidad en inasistencias históricas (pacientes con 0 faltas hasta pacientes recurrentes con 3+ inasistencias) para provocar clasificaciones dinámicas de riesgo ALTO, MEDIO y BAJO en el motor predictivo.
  - 100% de cumplimiento con las validaciones de `validar_fila` y el esquema del piloto.

---

## 7. Implementación de Drag & Drop en el Importador de Citas (`/citas/importar`)

Se dotó a la vista de importación masiva de citas de soporte nativo para arrastrar y soltar archivos:

1. **Manejadores de Eventos HTML5 Drag & Drop:**
   - `onDragOver` y `onDragEnter`: Activación de estado visual activo con prevención de la acción por defecto del navegador.
   - `onDragLeave`: Restauración del aspecto habitual al salir del recuadro.
   - `onDrop`: Captura y validación inmediata del archivo `.csv`.
2. **Feedback Visual Asistencial:**
   - Estilo dinámico `.selector-archivo-dropzone.arrastrando`: borde teal (#0f766e) sólido, sombreado exterior sutil y fondo verde menta suave.
   - Mensaje contextual reactivo: cambia automáticamente a *"¡Suelta tu archivo CSV aquí!"*.
3. **Tarjeta de Confirmación y Control:**
   - Al seleccionar o soltar el archivo, se muestra una tarjeta con el nombre del documento, su peso formateado (KB/MB), indicador de validación y botón *"Quitar"* para removerlo antes del envío.
4. **Validación Preventiva del Lado del Cliente:**
   - Comprobación estricta de extensión `.csv`, tamaño máximo de 2 MB y rechazo de archivos vacíos (0 bytes) antes de activar la solicitud a la API.

---

## 8. Verificación Final del Entorno

- **Base de Datos PostgreSQL (Puerto 5432):** Operativa (`predicitas_crp`).
- **Backend FastAPI (Puerto 8000):** Operativo. Todos los endpoints (`/citas`, `/intervenciones/elegibles`, `/cupos`, `/lista-espera`, `/reportes`) responden con código **HTTP 200**.
- **Frontend Vite (Puerto 5173):** Compilado con cero errores de TypeScript y empaquetado en producción.
- **Control de Versiones:** Cambios confirmados y subidos a GitHub:
  - Repositorio: `frontend-predicitas`
  - Rama: `feature/vistas-clinicas-ia-v1`
  - Commit: `feat(citas): agregar soporte para arrastrar y soltar archivo CSV en importador`.

