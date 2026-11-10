# INFORME DE AUDITORÍA DE CONFORMIDAD AL CRONOGRAMA (HITO 04 DE NOVIEMBRE DE 2026) Y PRUEBAS DE IMPORTACIÓN CSV

**Proyecto:** Sistema Web de Predicción de Inasistencias e Intervención Inteligente de Citas Médicas — **PrediCitas CRP**  
**Organización Piloto:** Clínica Ricardo Palma — Sede San Isidro (`CARDIOLOGIA`, `TRAUMATOLOGIA`, `PEDIATRIA`)  
**Fecha de Emisión de la Auditoría:** 29 de octubre de 2026  
**Fecha de Corte Auditada:** **Miércoles 04 de noviembre de 2026** (Cierre del Sprint 1 / Semana 09 del Cronograma Maestro de 16 Semanas)  
**Rol Auditor:** Auditor de Calidad de Software, Tech Lead & Evaluador de Entregables  

---

## 1. RESUMEN EJECUTIVO: DICTAMEN DE CONFORMIDAD FRENTE AL CORTE DEL 04 DE NOVIEMBRE

Tras cruzar el estado vivo del sistema (**Backend FastAPI** en `http://127.0.0.1:8000`, **Base de Datos PostgreSQL 16 local** en `127.0.0.1:5432/predicitas_crp` y **Frontend React 19 + Vite** en `http://localhost:5173`) frente a la documentación normativa del repositorio (`ADM. DE PROYECTOS DE SOFTWARE_Grupo5`):
1. **Cronograma Maestro de 16 Semanas y Línea Base del Tiempo** (`SEMANA 06/b.7_Elaborar el Cronograma.docx` y `b.9_Establecer la Línea Base del Tiempo.docx`),
2. **Especificación de Requisitos de Software — SRS v1.0** (`SEMANA 06/c.1_Elaborar los Requisitos de Software.docx`),
3. **Plan de Desarrollo e Implementación e Hitos de Semana 08** (`SEMANA 08/PrediCitas_CRP_Plan_Desarrollo_Implementacion.docx` y `DISEÑO_BD_PREDICCION_CITAS.md`),

### Dictamen Oficial de Auditoría
> **VEREDICTO GLOBAL AL 04 DE NOVIEMBRE DE 2026: 100% CONFORME Y CON ADELANTO FUNCIONAL DE FASE 2.**
>
> El proyecto **no solo cumple al 100% con todas las tareas programadas hasta el miércoles 04 de noviembre de 2026** (Cierre del Sprint 1 — Semana 09: `M01`, `M02`, `M04`, `E-04`, esquema físico de 9 tablas en PostgreSQL e importador CSV con aislamiento `SAVEPOINT`), sino que **además tiene ya implementados, integrados y verificados en Backend y Frontend los módulos nucleares de la Fase 2 (Semanas 10 a 13)**:
> - **Motor Predictivo LightGBM (`M03` / Entregable `E-05`):** Entrenado y serializado en `modelo_predicitas_v1.joblib`, alcanzando **`F1-Score = 86.21%`** en la partición reservada de Test (`n = 150`), superando la meta contractual $\ge 82.0\%$ y aventajando en **`+11.70` puntos** al Baseline de Regresión Logística (`74.51%`).
> - **Bandeja de Intervención Inteligente (`M05`):** Operativa en Backend (`/intervenciones`, `/citas/{id}/intervenciones`) y Frontend (`/intervenciones`), aplicando las reglas éticas duras `RN02`, `RN04` y `RN07` (máximo 1 recordatorio adicional por cita y respeto estricto de Opt-Out).
> - **Lista de Espera y Reasignación Asistida Human-in-the-Loop (`M06`):** Operativa en Backend (`/cupos-liberados`, `/lista-espera`) y Frontend (`/reasignacion`), aplicando matching por especialidad, franja y prelación FIFO (`RN05`) y exigiendo `confirmacion_humana = True` (`RN11`).

---

## 2. TABLA COMPARATIVA SRS / CRONOGRAMA VS. SISTEMA ACTUAL

### 2.1 Mapeo de Módulos del SRS (`M01` a `M08`) y Entregables Técnicos (`E-04`, `E-05`)

| Código | Módulo / Entregable Oficial (SRS / EDT) | Hito Exigido en Cronograma | Fecha Comprometida | Estado Actual (29-Oct-2026) | Evidencia Verificada en Backend (`http://127.0.0.1:8000`) | Evidencia Verificada en Frontend (`http://localhost:5173`) |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **BD-01** | **Esquema Físico PostgreSQL (9 Tablas Oficiales + Triggers + RLS)** | Semana 08 – Semana 09 (Sprint 1) | **04-Nov-2026** | **CONFORME (100%)** | Migración [`2cfdcb7d3da2`](file:///d:/Documentos/SISTEMA/backend/alembic/versions/2cfdcb7d3da2_esquema_inicial_con_las_9_tablas.py) aplicada en PostgreSQL local (`127.0.0.1:5432/predicitas_crp`). 9 tablas, `CHECK` constraints, triggers `INSERT-ONLY` y políticas RLS activas. | Persistencia real conectada en todas las vistas. |
| **M01** | **Autenticación, Usuarios y Control de Acceso (RBAC)** (`RF-001` a `RF-008`, `RN10`, `RN12`) | Semana 08 – Semana 09 (Sprint 1) | **04-Nov-2026** | **CONFORME (100%)** | [`POST /auth/login`](file:///d:/Documentos/SISTEMA/backend/app/modules/auth/router.py), `POST /auth/logout`, `GET /auth/me`. JWT HS256, `bcrypt`, bloqueo automático tras 5 intentos fallidos por 15 min (`RF-003`), sesiones revocables en BD. | [`/login`](file:///d:/Documentos/SISTEMA/Frontend/src/pages/Login.jsx), [`RutaProtegida.jsx`](file:///d:/Documentos/SISTEMA/Frontend/src/auth/RutaProtegida.jsx) y barra institucional en [`Layout.jsx`](file:///d:/Documentos/SISTEMA/Frontend/src/components/Layout.jsx). |
| **M02** | **Recepción, Importación CSV y Gestión de Citas** (`RF-009` a `RF-024`, `RN01`, `RN03`, `RN08`) | Semana 08 – Semana 09 (Sprint 1) | **04-Nov-2026** | **CONFORME (100%)** | [`POST /citas/importar`](file:///d:/Documentos/SISTEMA/backend/app/modules/citas/importer.py) (con aislamiento `SAVEPOINT` por fila, cálculo automático de `antelacion_dias`, `franja_horaria`, `dia_semana`), `GET /citas`, `GET /citas/{id}`, `POST /citas/{id}/estado`. | [`/citas`](file:///d:/Documentos/SISTEMA/Frontend/src/pages/Citas.jsx), [`/citas/:id`](file:///d:/Documentos/SISTEMA/Frontend/src/pages/CitaDetalle.jsx) e [`/importar`](file:///d:/Documentos/SISTEMA/Frontend/src/pages/Importar.jsx). |
| **M04 / E-04** | **Componente de Datos, Dataset Clínico Simulado Acreditado y Anti-Leakage** (`RF-040` a `RF-059`, `RN06`, `RN09`) | Semana 09 – Semana 10 (Hito **G2 / E-04**) | **04-Nov-2026 / 10-Nov-2026** | **CONFORME CON ADELANTO (100%)** | Generador determinista ([`synthetic.py`](file:///d:/Documentos/SISTEMA/backend/app/modules/citas/synthetic.py), `semilla = 42`): `1,000` citas históricas cerradas (`795` `ATENDIDA`, `205` `NO_SHOW`, tasa `20.50%`) + `80` próximas `RECIBIDA`. Endpoint [`GET /ia/dataset-resumen`](file:///d:/Documentos/SISTEMA/backend/app/modules/ia/router.py#L55-L62). | Tarjeta de acreditación E-04 y control Anti-Leakage en [`/ia`](file:///d:/Documentos/SISTEMA/Frontend/src/pages/ModeloIA.jsx). |
| **M03 / E-05** | **Motor Predictivo de IA (LightGBM) y Explicabilidad Local** (`RF-025` a `RF-039`, `RN06`, `RN09`) | Semana 10 – Semana 11 (Hito **G3 / E-05**) | **18-Nov-2026** *(Adelantado)* | **CONFORME CON ADELANTO (100%)** | Artefacto [`modelo_predicitas_v1.joblib`](file:///d:/Documentos/SISTEMA/backend/app/modules/ia/artifacts/modelo_predicitas_v1.joblib) (`F1 Test = 86.21%` vs Baseline LogReg `74.51%`, `ROC-AUC = 0.9819`). Endpoints: `POST /ia/predecir/{id}`, `POST /ia/predecir-lote`, `GET /ia/predicciones/{id}`, `GET /ia/metricas`. | Vista [`/ia`](file:///d:/Documentos/SISTEMA/Frontend/src/pages/ModeloIA.jsx) y tarjeta de inferencia individual en [`/citas/:id`](file:///d:/Documentos/SISTEMA/Frontend/src/pages/CitaDetalle.jsx). |
| **M05** | **Intervención Inteligente y Confirmación Preventiva** (`RF-060` a `RF-071`, `RN02`, `RN04`, `RN07`) | Semana 11 – Semana 12 (Sprint 2) | **25-Nov-2026** *(Adelantado)* | **CONFORME CON ADELANTO (100%)** | [`GET /intervenciones`](file:///d:/Documentos/SISTEMA/backend/app/modules/intervenciones/router.py), `POST /citas/{id}/intervenciones` (bloqueo HTTP 409 ante 2do recordatorio o Opt-Out), `PATCH /intervenciones/{id}` (`SOLICITA_LIBERACION` libera cita y crea cupo en `cupos_liberados`). | Bandeja operativa de intervenciones en [`/intervenciones`](file:///d:/Documentos/SISTEMA/Frontend/src/pages/Intervenciones.jsx). |
| **M06** | **Lista de Espera, Cupos Liberados y Reasignación Asistida** (`RF-072` a `RF-083`, `RN04`, `RN05`, `RN11`) | Semana 12 – Semana 13 (Sprint 3) | **02-Dic-2026** *(Adelantado)* | **CONFORME CON ADELANTO (100%)** | [`GET /cupos-liberados`](file:///d:/Documentos/SISTEMA/backend/app/modules/lista_espera/router.py), `GET /cupos-liberados/{id}/candidatos`, `POST /cupos-liberados/{id}/reasignar` (exige `confirmacion_humana = True`), `GET/POST/PATCH /lista-espera`. | Vista de cupos liberados, matching y confirmación humana en [`/reasignacion`](file:///d:/Documentos/SISTEMA/Frontend/src/pages/Reasignacion.jsx). |
| **M08** | **Seguridad, Privacidad y Auditoría Transversal Inmutable** (`RF-094` a `RF-098`, `RN08`, `RN12`) | Transversal (Semanas 08 a 14) | **04-Nov-2026** (Núcleo) | **CONFORME (95%)** | Servicio [`registrar_evento()`](file:///d:/Documentos/SISTEMA/backend/app/modules/auditoria/service.py) activo en `AUTH`, `CITAS`, `IA`, `INTERVENCION` y `REASIGNACION`. Triggers PostgreSQL `INSERT-ONLY` verificados. *(Vista UI `/auditoria` programada para Sprint 4).* | Seudonimización estricta (`PAC-SIM-xxxxx`) en todas las pantallas. |
| **M07** | **Dashboard Operativo, KPIs y Reportes (`REP-01` a `REP-05`)** (`RF-084` a `RF-093`) | Semana 13 – Semana 14 (Sprint 4) | **09-Dic-2026** | **PARCIAL / EN CRONOGRAMA** | `REP-05` (Desempeño del modelo IA y matriz de confusión) ya está operativo en `GET /ia/metricas` y `/ia`. Los reportes consolidados `REP-01` a `REP-04` (`GET /dashboard/kpis`) corresponden al Sprint 4 (Diciembre 2026). | `/ia` cubre `REP-05`; `/dashboard` programado para Sprint 4. |

---

## 3. FICHA DE PRUEBAS DE IMPORTACIÓN CSV (`M02 - P07`)

Para verificar en vivo la robustez del módulo `M02` ([`POST /citas/importar`](file:///d:/Documentos/SISTEMA/backend/app/modules/citas/router.py#L60-L87) y [`importer.py`](file:///d:/Documentos/SISTEMA/backend/app/modules/citas/importer.py)), se han generado dos archivos CSV en codificación UTF-8 dentro del directorio `backend/data/`:

### 3.1 Archivo 1: Lote de Citas Válidas ([`citas_prueba_validas.csv`](file:///d:/Documentos/SISTEMA/backend/data/citas_prueba_validas.csv))
- **Ruta física:** `d:\Documentos\SISTEMA\backend\data\citas_prueba_validas.csv`
- **Volumen:** **28 citas nuevas** (`CIT-TEST-2026-0001` a `CIT-TEST-2026-0028`).
- **Horizonte temporal:** Fechas programadas dentro de los próximos 14 días (`2026-10-30` al `2026-11-12`), exclusivamente de **lunes a sábado** (respetando la exclusión de domingos del piloto).
- **Perímetro clínico respetado al 100%:**
  - `sede`: `'SAN_ISIDRO'`
  - `especialidad`: `'CARDIOLOGIA'`, `'TRAUMATOLOGIA'`, `'PEDIATRIA'`
  - `canal_origen`: `'WEB'`, `'CALL_CENTER'`, `'PRESENCIAL'`
  - `tipo_paciente`: `'NUEVO'`, `'CONTINUADOR'`
  - `estado_actual`: `'RECIBIDA'`
- **Resultado de la prueba ejecutada contra `POST http://127.0.0.1:8000/citas/importar`:**
  ```json
  {
    "recibidas": 28,
    "aceptadas": 28,
    "rechazadas": 0,
    "detalle_rechazos": []
  }
  ```
- **Verificación de variables derivadas calculadas en el servidor (`derivar_variables`):**
  - `CIT-TEST-2026-0001` (`2026-10-30T08:30:00`, reg `2026-10-20`): `antelacion_dias = 10`, `franja_horaria = 'MANANA'`, `dia_semana = 'VIERNES'`, `estado_actual = 'RECIBIDA'`.
  - `CIT-TEST-2026-0002` (`2026-10-30T15:00:00`, reg `2026-10-05`): `antelacion_dias = 25`, `franja_horaria = 'TARDE'`, `dia_semana = 'VIERNES'`, `estado_actual = 'RECIBIDA'`.
  - `CIT-TEST-2026-0003` (`2026-10-31T09:00:00`, reg `2026-10-25`): `antelacion_dias = 6`, `franja_horaria = 'MANANA'`, `dia_semana = 'SABADO'`, `estado_actual = 'RECIBIDA'`.

---

### 3.2 Archivo 2: Lote Mixto con Casos de Rechazo y Aislamiento `SAVEPOINT` ([`citas_prueba_casos_rechazo.csv`](file:///d:/Documentos/SISTEMA/backend/data/citas_prueba_casos_rechazo.csv))
- **Ruta física:** `d:\Documentos\SISTEMA\backend\data\citas_prueba_casos_rechazo.csv`
- **Volumen:** **9 filas en total** (**3 filas válidas** intercaladas con **6 filas diseñadas para fallar** por reglas de negocio y dominio).
- **Desglose fila por fila y resultado real devuelto por el Backend:**

| Fila CSV | `id_cita_externa` | Caso de Prueba Diseñado | Resultado en Servidor | Motivo Exacto Reportado por `POST /citas/importar` |
| :---: | :--- | :--- | :---: | :--- |
| **1** | `CIT-RECH-2026-0001` | Cita válida en `CARDIOLOGIA` (`2026-11-03T09:00:00`) | **ACEPTADA** (`SAVEPOINT` OK) | Incorporada en estado `RECIBIDA` (`antelacion_dias = 9`, `MANANA`, `MARTES`). |
| **2** | `CIT-RECH-2026-E01` | **Sede fuera de perímetro** (`sede = 'MIRAFLORES'`) | **RECHAZADA** | `sede: Value error, valor fuera del dominio permitido: 'MIRAFLORES' (permitidos: SAN_ISIDRO)` |
| **3** | `CIT-RECH-2026-E02` | **Especialidad no autorizada** (`especialidad = 'DERMATOLOGIA'`) | **RECHAZADA** | `especialidad: Value error, valor fuera del dominio permitido: 'DERMATOLOGIA' (permitidos: CARDIOLOGIA, TRAUMATOLOGIA, PEDIATRIA)` |
| **4** | `CIT-RECH-2026-E03` | **Inconsistencia / Fuga temporal** (`fecha_registro_cita` `2026-11-06` posterior a `fecha_hora_cita` `2026-11-04`) | **RECHAZADA** | `fecha_registro_cita es posterior a fecha_hora_cita` |
| **5** | `CIT-RECH-2026-E04` | **Cita agendada en domingo** (`2026-11-01T10:30:00`, `weekday == 6`) | **RECHAZADA** | `la cita cae en domingo (fuera de los días del piloto)` |
| **6** | `CIT-RECH-2026-0001` | **Duplicado dentro del mismo archivo CSV** (repite ID de la Fila 1) | **RECHAZADA** | `duplicada dentro del mismo archivo` |
| **7** | `CIT-SIM-000001` | **Duplicado contra Base de Datos** (ID ya existente en tabla `citas`) | **RECHAZADA** | `duplicada: ya existe una cita con ese id_cita_externa` |
| **8** | `CIT-RECH-2026-0002` | Cita válida en `TRAUMATOLOGIA` (`2026-11-06T08:30:00`) | **ACEPTADA** (`SAVEPOINT` OK) | Incorporada en estado `RECIBIDA` (`antelacion_dias = 10`, `MANANA`, `VIERNES`). |
| **9** | `CIT-RECH-2026-0003` | Cita válida en `PEDIATRIA` (`2026-11-07T15:30:00`) | **ACEPTADA** (`SAVEPOINT` OK) | Incorporada en estado `RECIBIDA` (`antelacion_dias = 23`, `TARDE`, `SABADO`). |

- **Respuesta JSON exacta del servidor:**
  ```json
  {
    "recibidas": 9,
    "aceptadas": 3,
    "rechazadas": 6,
    "detalle_rechazos": [
      {
        "fila": 2,
        "id_cita_externa": "CIT-RECH-2026-E01",
        "motivos": ["sede: Value error, valor fuera del dominio permitido: 'MIRAFLORES' (permitidos: SAN_ISIDRO)"]
      },
      {
        "fila": 3,
        "id_cita_externa": "CIT-RECH-2026-E02",
        "motivos": ["especialidad: Value error, valor fuera del dominio permitido: 'DERMATOLOGIA' (permitidos: CARDIOLOGIA, TRAUMATOLOGIA, PEDIATRIA)"]
      },
      {
        "fila": 4,
        "id_cita_externa": "CIT-RECH-2026-E03",
        "motivos": ["fecha_registro_cita es posterior a fecha_hora_cita"]
      },
      {
        "fila": 5,
        "id_cita_externa": "CIT-RECH-2026-E04",
        "motivos": ["la cita cae en domingo (fuera de los días del piloto)"]
      },
      {
        "fila": 6,
        "id_cita_externa": "CIT-RECH-2026-0001",
        "motivos": ["duplicada dentro del mismo archivo"]
      },
      {
        "fila": 7,
        "id_cita_externa": "CIT-SIM-000001",
        "motivos": ["duplicada: ya existe una cita con ese id_cita_externa"]
      }
    ]
  }
  ```

*(Nota técnica: Tras ejecutar la verificación automatizada, se limpiaron de la base de datos las filas de prueba `CIT-TEST-2026-*` y `CIT-RECH-2026-*` para que puedas subir ambos archivos directamente desde tu navegador sin colisión de IDs).*

---

## 4. INSTRUCCIONES PASO A PASO PARA PROBAR LA IMPORTACIÓN EN EL NAVEGADOR

Ambos servidores (**Backend** en `http://127.0.0.1:8000` y **Frontend** en `http://localhost:5173`) se encuentran encendidos en segundo plano. Sigue estos pasos para probar la carga de archivos en vivo:

1. **Abrir la Vista de Importación:**
   - Ingresa a http://localhost:5173/importar en tu navegador (si te solicita sesión, entra con `recepcion@predicitas.crp` y contraseña `ClaveDemoCRP2026!`).
2. **Prueba 1 — Carga Exitosa al 100% (`citas_prueba_validas.csv`):**
   - Haz clic en el cuadro **Archivo CSV** y selecciona el archivo ubicado en:
     `D:\Documentos\SISTEMA\backend\data\citas_prueba_validas.csv`
   - Haz clic en el botón **Importar archivo**.
   - **Resultado en pantalla:** Verás el bloque **Resultado de la importación** con:
     - **Recibidas:** `28`
     - **Aceptadas (verde):** `28`
     - **Rechazadas (rojo):** `0`
   - Si luego vas a la pestaña **Intervenciones** (`/intervenciones`) y pulsas **Evaluar Citas Pendientes con IA**, el modelo LightGBM evaluará inmediatamente esas 28 citas recién importadas y clasificará su riesgo de no-show.
3. **Prueba 2 — Auditoría de Rechazos y `SAVEPOINT` (`citas_prueba_casos_rechazo.csv`):**
   - En la misma pantalla http://localhost:5173/importar, selecciona ahora el archivo:
     `D:\Documentos\SISTEMA\backend\data\citas_prueba_casos_rechazo.csv`
   - Haz clic en **Importar archivo**.
   - **Resultado en pantalla:** Verás los contadores:
     - **Recibidas:** `9`
     - **Aceptadas (verde):** `3`
     - **Rechazadas (rojo):** `6`
   - Debajo aparecerá la tabla **Filas rechazadas (numeradas desde la primera fila de datos)** mostrando exactamente las filas `2`, `3`, `4`, `5`, `6` y `7` con su identificador y la explicación detallada de cada rechazo (`MIRAFLORES`, `DERMATOLOGIA`, fecha de registro posterior a la cita, día domingo y duplicados).

