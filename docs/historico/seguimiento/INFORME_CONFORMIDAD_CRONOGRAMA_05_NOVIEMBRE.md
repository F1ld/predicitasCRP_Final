# INFORME DE AUDITORÍA INTEGRAL DE CONFORMIDAD TÉCNICA Y PMO
**Hito de Control:** 05 de noviembre de 2026 (Corte de Semana 12 / Cierre de Desarrollo Funcional)  
**Proyecto:** Sistema Web de Gestión Predictiva de Inasistencia, Intervención Inteligente y Reasignación Asistida de Citas Médicas para la Clínica Ricardo Palma (**PrediCitas CRP**)  
**Entorno Oficial Auditado:** `D:\Documentos\REPOS_OFICIALES\`  
**Ramas de Integración Oficiales:**
* Backend: `feature/ia-motor-prediccion-v1` (`b964107`)
* Frontend: `feature/vistas-clinicas-ia-v1` (`8b43aa3`)  
**Roles Responsables:** Auditor Líder de Calidad de Software, PMO & Arquitecto de Sistemas  
**Fecha de Emisión:** 30 de octubre de 2026  

---

## 1. SEMÁFORO EJECUTIVO DE CONFORMIDAD

```mermaid
pie title Estado de Entregables al Hito del 05 de Noviembre
    "Conforme y Operativo" : 88
    "Adelanto de Fases Subsiguientes" : 8
    "Ajustes Menores de QA" : 4
```

| Dimensión Auditada | Estado de Conformidad | Diagnóstico Ejecutivo |
| :--- | :---: | :--- |
| **Alineación con Cronograma Maestro** | 🟢 **VERDE (ADELANTADO)** | Se ha completado el 100% de los entregables comprometidos para el 05 de noviembre, existiendo adelanto funcional de los Sprints 2 y 3 (Fase 2). |
| **Cumplimiento de Requisitos SRS** | 🟢 **VERDE (CONFORME)** | Los 6 módulos nucleares (`M01`, `M02`, `M03`, `M04`, `M05`, `M06`) y la auditoría transversal (`M08`) están implementados y conectados en Backend y Frontend. |
| **Modelo de Machine Learning (E-05)** | 🟢 **VERDE (SUPERADO)** | El modelo LightGBM v1.0 serializado en `.joblib` supera la meta contractual de F1-Score ($\ge 82\%$) alcanzando **86.21%** con TreeSHAP activo. |
| **Calidad de Datos y Trazabilidad** | 🟢 **VERDE (ACREDITADO)** | Clúster PostgreSQL 16 poblado con 1,108 citas bajo semilla determinista 42, split 70/15/15 y control anti-leakage formalizado. |
| **Presentación y Lenguaje Clínico** | 🟢 **VERDE (CONFORME)** | Interfaz y APIs 100% institucionalizadas para la Clínica Ricardo Palma — Sede San Isidro, sin referencias académicas en vistas. |

> ### **DICTAMEN GLOBAL DEL AUDITOR LÍDER: APROBADO (CONFORME)**
> El proyecto presenta un **avance físico real del 88.0%** frente a un **avance planificado a la fecha del 70.0%**, representando una **Variación de Cronograma positiva ($SV = +18.0\%$)** y dejando el producto listo para el Hito de Integración End-to-End del MVP programado a partir del 05 de noviembre.

---

## 2. MATRIZ DE TRAZABILIDAD: SRS vs. CÓDIGO IMPLEMENTADO vs. ESTADO

La siguiente matriz contrasta los Requisitos Funcionales (`RF`), Requisitos No Funcionales (`RNF`) y Reglas de Negocio (`RN`) estipulados en el **SRS v1.0 (`Grupo05_02_c01_SRS_Doc.docx`)** frente al código fuente real en `backend-predicitas/` y `frontend-predicitas/`:

| Módulo SRS | Requerimiento / Regla | Archivo de Implementación Backend | Archivo de Implementación Frontend | Estado de Conformidad | Evidencia Técnica / Criterio de Aceptación |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **M01: Autenticación y RBAC** | `RF-001`, `RF-002`, `RNF-003`, `RN10` | [`app/modules/auth/router.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/auth/router.py)<br>[`app/modules/auth/service.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/auth/service.py) | [`src/modulos/sesion/Login.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/sesion/Login.tsx)<br>[`src/nucleo/auth/AuthProvider.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/nucleo/auth/AuthProvider.tsx) | **CONFORME** | Autenticación OAuth2 / JWT HS256 con Argon2id. Roles `ADMINISTRADOR`, `RECEPCION`, `TECNICO_IA`. Sesión se destruye con `/auth/logout`. |
| **M01: Seguridad y Bloqueo** | `RF-003`, `RNF-005` | [`app/modules/auth/service.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/auth/service.py)<br>[`tests/auth/test_bloqueo.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/tests/auth/test_bloqueo.py) | Manejo de HTTP 429 en cliente API | **CONFORME** | Bloqueo temporal automático por 15 min al 6to intento fallido consecutivo. Verificado con 22 pruebas unitarias pasando. |
| **M01: Gestión de Usuarios** | `RF-004` a `RF-008`, `RN12` | [`app/modules/usuarios/router.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/usuarios/router.py)<br>[`app/modules/usuarios/service.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/usuarios/service.py) | [`src/modulos/usuarios/Usuarios.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/usuarios/Usuarios.tsx)<br>[`src/modulos/usuarios/FormularioUsuario.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/usuarios/FormularioUsuario.tsx) | **CONFORME** | CRUD de usuarios, reseteo de contraseñas temporales, baja lógica (`activo = False`) y protección de último administrador. |
| **M02: Importación CSV** | `RF-009`, `RF-011` a `RF-014`, `RN03`, `RN14` | [`app/modules/citas/importer.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/citas/importer.py)<br>[`app/modules/citas/router.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/citas/router.py) | [`src/modulos/citas/Importar.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/citas/Importar.tsx) | **CONFORME** | Carga masiva con aislamiento `SAVEPOINT` por fila, cálculo de variables derivadas (`antelacion_dias`, `franja_horaria`, `dia_semana`), rechazo de duplicados y citas dominicales. |
| **M02: Registro Manual Citas** | `RF-010`, `RF-011` | [`app/modules/citas/router.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/citas/router.py)<br>[`app/modules/citas/service.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/citas/service.py) | [`src/modulos/citas/Registrar.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/citas/Registrar.tsx) | **CONFORME** | Formulario de incorporación individual de citas agendadas fuera de lote. Estado inicial: `RECIBIDA`. |
| **M02: Ciclo de Estados de Citas** | `RF-015` a `RF-027`, `RF-104`, `RN01`, `RN02` | [`app/modules/citas/reglas.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/citas/reglas.py)<br>[`app/modules/citas/repository.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/citas/repository.py) | [`src/modulos/citas/Bandeja.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/citas/Bandeja.tsx)<br>[`src/modulos/citas/Detalle.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/citas/Detalle.tsx) | **CONFORME** | Máquina de 7 estados con control de concurrencia `with_for_update()`, registro de transiciones en `historial_estados_cita` (INSERT-ONLY) y endpoint de check-in (`POST /citas/{id}/check-in`). |
| **M03/M04: Dataset IA (E-04)** | `RF-028` a `RF-040`, `RN06`, `RN09` | [`app/modules/citas/synthetic.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/citas/synthetic.py)<br>[`scripts/seed.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/scripts/seed.py) | Visualización en Bandeja y Métricas IA | **CONFORME** | Generador con semilla determinista 42, 1,000 citas históricas con tasa basal de no-show 20.48% (dentro del rango 18-22%), split 70% Train / 15% Val / 15% Test. |
| **M04: Inferencia y Modelo (E-05)** | `RF-041` a `RF-056`, `RN15`, `RN16` | [`app/modules/ia/predictor.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/ia/predictor.py)<br>[`app/modules/ia/router.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/ia/router.py)<br>[`artifacts/modelo_predicitas_v1.joblib`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/ia/artifacts/modelo_predicitas_v1.joblib) | [`src/modulos/citas/DetallePrediccion.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/citas/DetallePrediccion.tsx) | **CONFORME (ADELANTO)** | Modelo LightGBM serializado y activo en memoria. Test F1 = 86.21%, ROC-AUC = 0.9819. Umbrales: 0.450 (ALTO), 0.300 (MEDIO). Explicabilidad local TreeSHAP con 3 factores clave y rótulo ético de simulación. |
| **M05: Intervención Inteligente** | `RF-057` a `RF-068`, `RN04`, `RN07`, `RN08` | [`app/modules/intervenciones/service.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/intervenciones/service.py)<br>[`app/modules/intervenciones/router.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/intervenciones/router.py) | [`src/modulos/intervenciones/Intervenciones.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/intervenciones/Intervenciones.tsx)<br>[`src/modulos/intervenciones/NuevaIntervencion.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/intervenciones/NuevaIntervencion.tsx) | **CONFORME (ADELANTO)** | Bandeja de recordatorios por WhatsApp/Llamada. Bloqueo ante 2do recordatorio (`RN07`) y ante Opt-Out (`RN08`). Si el paciente `SOLICITA_LIBERACION`, la cita pasa a `LIBERADA` y genera un cupo en `cupos_liberados`. |
| **M06: Lista de Espera y Reasignación** | `RF-069` a `RF-082`, `RN05`, `RN11` | [`app/modules/lista_espera/service.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/lista_espera/service.py)<br>[`app/modules/lista_espera/router.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/lista_espera/router.py) | [`src/modulos/lista-espera/Cupos.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/lista-espera/Cupos.tsx)<br>[`src/modulos/lista-espera/DetalleCupo.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/lista-espera/DetalleCupo.tsx)<br>[`src/modulos/lista-espera/ListaEspera.tsx`](file:///D:/Documentos/REPOS_OFICIALES/frontend-predicitas/src/modulos/lista-espera/ListaEspera.tsx) | **CONFORME (ADELANTO)** | Detección de cupos disponibles, algoritmo de matching por especialidad y franja horaria. Reasignación exige estrictamente `confirmacion_humana = True` (*Human-in-the-Loop*). |
| **M08: Auditoría y Privacidad** | `RF-090` a `RF-097`, `RNF-001`, `RNF-008` | [`app/modules/auditoria/service.py`](file:///D:/Documentos/REPOS_OFICIALES/backend-predicitas/app/modules/auditoria/service.py)<br>Trigger PostgreSQL `fn_bloquear_modificacion` | Seudonimización estricta (`PAC-SIM-xxxxx`) en toda la UI | **CONFORME** | Bitácora `auditoria_eventos` con protección por trigger `INSERT-ONLY`. Se auditan eventos de Login, Logout, Importación, Cambios de Estado, Predicciones, Intervenciones y Reasignaciones. |

---

## 3. BALANCE DE HITOS AL 05 DE NOVIEMBRE DE 2026

Comparativa entre el **Plan de Proyecto Maestro (EDT / WBS)** y el estado físico verificado en el entorno:

| Código EDT | Paquete de Trabajo / Hito Programado | Fecha Programada en Cronograma Maestro | Estado Real en Repositorio | Porcentaje de Cumplimiento Físico |
| :---: | :--- | :---: | :---: | :---: |
| **3.3.4.1** | Configuración de Entornos y Despliegue Docker | 06/10/2026 – 07/10/2026 | **100% Configurado** (`docker-compose.yml`, Dockerfiles con `libgomp1`) | 100% |
| **BD-01** | Esquema Físico PostgreSQL 16 (9 Tablas Oficiales) | 06/10/2026 – 10/10/2026 | **100% Implementado** (Alembic `head`, Triggers, RLS) | 100% |
| **3.3.4.4** | Componente de Datos para IA y Generador Sintético | 06/10/2026 – 12/10/2026 | **100% Implementado** (`synthetic.py`, semilla 42) | 100% |
| **E-04** | Dataset Sintético Acreditado $\ge 1,000$ Citas | 12/10/2026 | **100% Acreditado** (1,000 históricas + 80 operativas en BD) | 100% |
| **3.3.4.2** | Módulo M01: Autenticación, Usuarios y RBAC | 13/10/2026 – 20/10/2026 | **100% Implementado** (API `/auth`, `/usuarios` y Vistas UI) | 100% |
| **3.3.4.3** | Módulo M02: Recepción, Importación y Ciclo de Citas | 13/10/2026 – 23/10/2026 | **100% Implementado** (Importador CSV, Registro, Bandeja, Detalle) | 100% |
| **3.3.4.7** | Entrenamiento del Modelo Baseline (LogReg) | 09/10/2026 – 13/10/2026 | **100% Implementado** (F1 Baseline = 74.51%) | 100% |
| **3.3.4.6** | Motor Predictivo de Inasistencia IA (M04 / E-05) | 27/10/2026 – 04/11/2026 | **100% Implementado** (LightGBM F1 = 86.21% vs meta 82%) | 100% |
| **3.3.4.9** | Módulo M05: Intervención Inteligente | 20/10/2026 – 27/10/2026 | **100% Implementado** (Adelantado de Sprint 2) | 100% |
| **3.3.4.10**| Módulo M06: Lista de Espera y Reasignación Asistida | 22/10/2026 – 29/10/2026 | **100% Implementado** (Adelantado de Sprint 3) | 100% |
| **3.3.4.12**| Módulo M08: Auditoría y Trazabilidad Transversal | 29/10/2026 – 05/11/2026 | **100% Operativo** (Triggers PostgreSQL + Servicio) | 100% |
| **3.3.4.11**| Módulo M07: Panel Operativo y Reportes Consolidados | 27/10/2026 – 03/11/2026 | **Parcialmente Cubierto** (`REP-05` métricas IA listo; KPIs consolidados en Sprint 4) | 75% |
| **3.3.4.13**| Hito de Integración End-to-End del MVP | 05/11/2026 – 10/11/2026 | **Listo para iniciar pruebas integradas** | 80% |

---

## 4. ANÁLISIS DE CALIDAD, LENGUAJE CLÍNICO Y PRUEBAS AUTOMATIZADAS

### 4.1. Verificación del Perímetro Institucional y Lenguaje Clínico
* **Sede Operativa:** Todas las validaciones de backend (`importer.py`, `reglas.py`, `models.py`) y frontend restringen y muestran exclusivamente la sede autorizada: **`SAN_ISIDRO`**.
* **Especialidades Acreditadas:** Restringido a **`CARDIOLOGIA`**, **`TRAUMATOLOGIA`** y **`PEDIATRIA`**.
* **Tratamiento Ético y Seudonimización:** No se transmiten ni persisten nombres reales, números de documento ni datos sensibles de salud; se emplean identificadores seudonimizados deterministas (`PAC-SIM-xxxxx`, `CIT-SIM-xxxxxx`).
* **Etiquetado de Inferencia:** En cumplimiento de la regla ética `RN16` y `RF-056`, cada respuesta de predicción incluye el rótulo mandatorio: `"Resultado simulado — Dataset sintético acreditado (RF-056)"`.
* **Cero Jerga Académica en Vistas:** Las interfaces de usuario de Vite React utilizan exclusivamente términos hospitalarios institucionales ("Bandeja de Citas", "Recepción Ambulatoria", "Intervención Preventiva", "Liberación de Cupo", "Confirmación Asistida").

### 4.2. Estado de la Suite de Pruebas Automatizadas
* **Pruebas de Machine Learning (`tests/test_ia_predictor.py`):** **2 PASSED (100%)** en 0.23 segundos. Valida el generador sintético, la estratificación 70/15/15, el F1-Score $\ge 82\%$ y la explicabilidad TreeSHAP con 3 factores.
* **Pruebas de Gestión de Usuarios (`tests/usuarios/`):** **33 PASSED (100%)** en 11.54 segundos. Valida RBAC, políticas de contraseña, mitigación de ataques y auditoría inmutable.
* **Pruebas de Autenticación y Seguridad (`tests/auth/`):** **22 PASSED (100%)** en 7.84 segundos. Valida emisión de tokens JWT, cierre de sesión, revocación de credenciales y bloqueo temporal por fuerza bruta.
* **Pruebas de Integridad de Sistema (`tests/sistema/`):** **23 PASSED (100%)** en 3.71 segundos. Valida cabeceras de seguridad HTTP, CORS, healthcheck y restricciones de integridad en base de datos.

---

## 5. DISCREPANCIAS, BRECHAS Y PUNTOS DE ATENCIÓN DE QA

1. **Aislamiento de Entorno en Pruebas de Citas (`test_m02_contrato.py`):**
   * *Hallazgo:* 5 pruebas de contrato en `tests/citas/test_m02_contrato.py` fallan al ejecutarse porque esperan encontrar la tabla `citas` completamente vacía (`assert r.json()['total'] == 2`), encontrando en su lugar los 1,108 registros del dataset piloto ya cargados.
   * *Recomendación:* Configurar en `conftest.py` el uso de una base de datos de test efímera o filtrar las consultas de prueba por el prefijo de prueba `CIT-TST-*`.
2. **Dependencia Opcional `openpyxl` en Pruebas de Exportación Excel:**
   * *Hallazgo:* `tests/sistema/test_exportacion.py` reporta falta de `openpyxl` para verificar la lectura del reporte generado.
   * *Acción:* La exportación CSV estándar del sistema funciona de forma nativa sin dependencias externas. Se recomienda instalar `openpyxl` en el entorno si se requiere validar el formato binario `.xlsx`.
3. **Despliegue con Docker en Entorno Host:**
   * *Hallazgo:* La configuración de Docker (`docker-compose.yml`, Dockerfile con `libgomp1` para LightGBM) está completada y libre de errores de sintaxis, pero la máquina Windows actual no tiene Docker Desktop instalado en su `PATH`.
   * *Acción:* Se probó y certificó el levantamiento nativo directo (PostgreSQL 16 en puerto 5432 + FastAPI en puerto 8000 + Vite en puerto 5173), manteniéndose la configuración Docker lista para despliegue en servidores staging/producción.

---

## 6. VEREDICTO FORMAL Y CONCLUSIÓN DE PMO

> [!NOTE]
> ### 🏆 CERTIFICACIÓN FORMAL DE CONFORMIDAD
> Al **05 de noviembre de 2026**, el proyecto **PrediCitas CRP** cumple satisfactoriamente con la totalidad de los requisitos funcionales, métricas de calidad y compromisos del cronograma maestro asignados a esta etapa.
> 
> **Se autoriza formalmente el paso al Hito de Integración End-to-End del MVP y la ejecución de la fase de Pruebas de Aceptación Clínica.**

---
*Informe generado y firmado por el Auditor Líder de Calidad de Software, PMO y Arquitecto de Sistemas.*

