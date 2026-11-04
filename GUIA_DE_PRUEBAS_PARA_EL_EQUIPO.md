# Guía de Pruebas y Despliegue para el Equipo
**Proyecto:** PrediCitas CRP — Clínica Ricardo Palma (Sede San Isidro)  
**Versión oficial:** Rama `main` (post Merge Request #2)  
**Fecha:** 31 de Octubre de 2026  

---

Esta guía explica paso a paso cómo actualizar tu entorno local con los últimos cambios fusionados en `main` y cómo probar cada una de las nuevas funcionalidades y correcciones del sistema.

---

## 1. Actualización del Código desde GitHub

Si ya tienes los repositorios clonados en tu equipo, abre una terminal (PowerShell o Git Bash) y ejecuta:

### A. Actualizar Backend (`backend-predicitas`)
```powershell
cd D:\Documentos\REPOS_OFICIALES\backend-predicitas   # (O la ruta donde tengas tu repo)
git checkout main
git pull origin main
```

### B. Actualizar Frontend (`frontend-predicitas`)
```powershell
cd D:\Documentos\REPOS_OFICIALES\frontend-predicitas  # (O la ruta donde tengas tu repo)
git checkout main
git pull origin main
npm install    # Asegura que las dependencias estén al día
```

> **Si vas a clonar desde cero:**
> ```powershell
> git clone https://github.com/F1ld/backend-predicitas.git
> git clone https://github.com/F1ld/frontend-predicitas.git
> ```

---

## 2. Iniciar los Servicios Locales

Abre **3 terminales independientes** para mantener cada servicio en ejecución:

### Terminal 1: Base de Datos PostgreSQL
Asegúrate de que el motor de PostgreSQL esté corriendo en el puerto **5432** y que exista la base de datos `predicitas_crp`.

*(Si usas el entorno embebido con python/pgserver):*
```powershell
# Levantar PostgreSQL en 127.0.0.1:5432
```

### Terminal 2: Servidor Backend (FastAPI)
```powershell
cd D:\Documentos\REPOS_OFICIALES\backend-predicitas
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
> Verifica en tu navegador que responda la documentación interactiva:  
> [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Terminal 3: Servidor Frontend (Vite)
```powershell
cd D:\Documentos\REPOS_OFICIALES\frontend-predicitas
npm run dev
```
> La interfaz estará disponible en:  
> [http://localhost:5173](http://localhost:5173)

---

## 3. Credenciales de Acceso Oficiales

Ingresa a [http://localhost:5173](http://localhost:5173) e inicia sesión:

| Rol | Correo Institucional | Contraseña |
|---|---|---|
| **Recepción (Operativo)** | `recepcion@predicitas.crp` | `DemoCRP2026!` |
| **Administrador (Gestión)** | `admin@predicitas.crp` | `DemoCRP2026!` |
| **Técnico IA (Métricas)** | `tecnico.ia@predicitas.crp` | `DemoCRP2026!` |

> [!TIP]
> Si tu navegador tenía una sesión previa guardada y la pantalla queda en blanco, abre las herramientas de desarrollo (`F12`), ve a **Application / Storage** y haz clic en **Clear site data** (o abre una pestaña en modo incógnito).

---

## 4. Batería de Pruebas: ¿Qué debes verificar?

Sigue este checklist ordenado para validar cada cambio implementado:

### Prueba 1: Arrastrar y Soltar CSV (*Drag & Drop*) en Importador
- **Ruta:** [http://localhost:5173/citas/importar](http://localhost:5173/citas/importar)
- **Qué hacer:**
  1. Toma el archivo de prueba ubicado en:  
     `backend-predicitas\data\citas_para_importar_variado.csv` (o en la raíz del repositorio).
  2. Arrástralo directamente desde tu Explorador de Windows hacia el recuadro punteado.
  3. **Verifica:**
     - El recuadro cambia de color a verde clínico (*teal*) y muestra el texto `"¡Suelta tu archivo CSV aquí!"`.
     - Al soltarlo, aparece una tarjeta confirmando el nombre del archivo, su tamaño en KB y un botón `"Quitar"`.
  4. Haz clic en el botón verde **"Importar archivo"**.
  5. **Resultado esperado:** Muestra el resumen con citas recibidas, aceptadas y rechazadas (0 duplicadas en primera carga).

---

### Prueba 2: Nueva Jerarquía Visual y Trazabilidad en Detalle de Cita
- **Ruta:** [http://localhost:5173/citas](http://localhost:5173/citas) ➔ Haz clic en cualquier cita (ej. `/citas/1`).
- **Qué hacer:**
  1. Observa el bloque superior derecho de la pantalla:
     - Debe aparecer la **Tarjeta Predictiva de IA** destacada en primer plano.
     - Contiene el badge de nivel de riesgo (**ALTO**, **MEDIO** o **BAJO** con sus colores representativos).
     - Muestra la probabilidad de inasistencia en porcentaje y los **3 factores explicables de SHAP** (antelación, inasistencias históricas, etc.).
     - Incluye el rótulo ético mandatorio: *"Resultado predictivo orientativo — Dataset sintético acreditado (RF-056)"*.
  2. En el panel de **Acciones**, haz clic en el botón **"Ver trazabilidad"**.
  3. **Resultado esperado:** Ya **no da error 404**. Abre el panel/scroll con la bitácora cronológica visual mostrando los cambios de estado (`RECIBIDA`, `CONFIRMADA`, `LIBERADA`, etc.) y el operador responsable.

---

### Prueba 3: Bandeja de Intervenciones Asistenciales
- **Ruta:** [http://localhost:5173/intervenciones](http://localhost:5173/intervenciones)
- **Qué hacer:**
  1. Ingresa a la pestaña **"Elegibles"**.
  2. **Resultado esperado:** Ya **no aparece el error 405** (*"Método no permitido para este recurso"*).
  3. Filtra por nivel de riesgo `Alto y medio` o selecciona una especialidad.
  4. Haz clic en una cita para registrar una acción preventiva (Llamada telefónica, WhatsApp o Confirmación de asistencia).

---

### Prueba 4: Lista de Espera y Cupos Liberados
- **Ruta:** [http://localhost:5173/lista-espera](http://localhost:5173/lista-espera)
- **Qué hacer:**
  1. Ingresa a la vista de lista de espera.
  2. **Resultado esperado:** Ya **no queda en pantalla blanca**. Carga de inmediato la tabla de pacientes candidatos para reasignación.
  3. Ve al menú superior y pulsa en **"Cupos liberados"** ([http://localhost:5173/cupos](http://localhost:5173/cupos)).
  4. **Resultado esperado:** Ya **no da error 404** (*"El recurso no existe"*). Se muestra la bandeja de cupos disponibles para reasignación asistida.

---

### Prueba 5: Módulo de Reportes Asistenciales
- **Rutas:**
  - Reporte de Intervenciones: [http://localhost:5173/reportes/intervenciones](http://localhost:5173/reportes/intervenciones)
  - Reporte de Reasignaciones: [http://localhost:5173/reportes/reasignaciones](http://localhost:5173/reportes/reasignaciones)
- **Qué hacer:**
  1. Ingresa a cada reporte y valida los KPIs de tasa de contacto y cupos recuperados.
  2. **Resultado esperado:** Carga fluida de datos de gestión sin errores de recurso no encontrado.

---

## 5. Resumen de Errores Corregidos para Comparar

Si alguien del equipo recuerda cómo fallaba antes, aquí está el antes y después:

| Problema Anterior | Estado Actual en `main` |
|---|---|
| No se podía arrastrar archivos CSV en `/citas/importar`. | **Soporte Drag & Drop nativo** con animaciones y selector dual. |
| Error 404 al hacer clic en "Ver trazabilidad" en detalle de cita. | **Corregido:** Timeline visual integrado de estados cronológicos. |
| Predicción de IA estaba abajo e invisible a primera vista. | **Corregido:** Tarjeta KPI destacada en la cabecera con TreeSHAP. |
| Error 405 ("Método no permitido") en `/intervenciones`. | **Corregido:** Precedencia de endpoints resuelta en backend. |
| Pantalla en blanco en `/lista-espera`. | **Corregido:** Esquema paginado compatible y fallback tolerante. |
| Error 404 ("El recurso no existe") en `/cupos`. | **Corregido:** Router `/cupos` unificado en backend. |

