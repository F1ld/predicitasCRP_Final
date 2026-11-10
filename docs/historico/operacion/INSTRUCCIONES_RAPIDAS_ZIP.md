# Instrucciones Rápidas — PrediCitas CRP (Paquete ZIP)
**Proyecto:** PrediCitas CRP — Clínica Ricardo Palma (Sede San Isidro)  
**Destinatario:** Miembros del equipo de desarrollo y evaluación  
**Archivo fuente:** `PrediCitas_CRP_Proyecto_Oficial.zip`  

---

¡Hola! Has recibido el paquete oficial consolidado de **PrediCitas CRP**. Para mantener el archivo ligero y libre de conflictos, se han excluido las carpetas temporales (`node_modules/`, `.venv/` y `.git/`).

Sigue estos sencillos pasos para dejar el sistema corriendo en tu computadora en menos de 5 minutos:

---

## Paso 1: Descomprimir el archivo ZIP
1. Haz clic derecho sobre `PrediCitas_CRP_Proyecto_Oficial.zip` y selecciona **Extraer todo...** (o usa 7-Zip / WinRAR).
2. Extrae el contenido en la carpeta de tu preferencia (por ejemplo, en `D:\Documentos\REPOS_OFICIALES` o `C:\Proyectos\PrediCitas`).

---

## Paso 2: Levantar el Backend (FastAPI + Python)

Abre tu primera terminal (PowerShell) y posiciónate en la carpeta `backend-predicitas`:

```powershell
cd backend-predicitas

# 1. Crear el entorno virtual de Python
python -m venv .venv

# 2. Activar el entorno virtual
.\.venv\Scripts\Activate.ps1

# 3. Instalar las dependencias oficiales
pip install -r requirements.txt

# 4. Iniciar el servidor backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

> **Verificación:** Abre en tu navegador [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Debe cargar Swagger con todos los endpoints operativos.  
> *(Nota: Asegúrate de tener PostgreSQL corriendo en el puerto `5432` con la base de datos `predicitas_crp`).*

---

## Paso 3: Levantar el Frontend (React + Vite)

Abre una **segunda terminal** (PowerShell) y posiciónate en la carpeta `frontend-predicitas`:

```powershell
cd frontend-predicitas

# 1. Instalar los paquetes y librerías de Node.js
npm install

# 2. Iniciar el servidor de desarrollo
npm run dev
```

> **Verificación:** Abre en tu navegador [http://localhost:5173](http://localhost:5173). Cargará la pantalla de inicio de sesión de la Clínica Ricardo Palma.

---

## Paso 4: Credenciales Oficiales de Demostración

Ingresa en la interfaz web con cualquiera de las cuentas del piloto asistencial:

| Rol Asistencial | Correo Institucional | Contraseña |
|---|---|---|
| **Recepción (Operativo)** | `recepcion@predicitas.crp` | `DemoCRP2026!` |
| **Administrador (Gestión)** | `admin@predicitas.crp` | `DemoCRP2026!` |
| **Técnico IA (Métricas)** | `tecnico.ia@predicitas.crp` | `DemoCRP2026!` |

> [!TIP]
> Si tu navegador muestra una pantalla blanca por haber tenido una sesión antigua abierta, presiona `F12`, ve a la pestaña **Application** (o Almacenamiento), haz clic en **Clear site data** (Borrar datos del sitio) y recarga con `F5`.

---

## Paso 5: ¿Qué novedades debes probar?

1. **Importación con Arrastrar y Soltar (Drag & Drop):**
   - Entra a [http://localhost:5173/citas/importar](http://localhost:5173/citas/importar).
   - Toma `data/samples/importacion/citas_para_importar_variado.csv` (ubicación canónica desde fase 3) y **arrástralo directamente al recuadro punteado**. Las copias de rutas anteriores son solo compatibilidad, no muestras nuevas.
   - Verás el cambio de color, el mensaje de confirmación y podrás hacer clic en **"Importar archivo"**.
2. **Jerarquía Visual de IA y Trazabilidad:**
   - Entra a [http://localhost:5173/citas](http://localhost:5173/citas) y abre cualquier cita.
   - Revisa la **tarjeta de predicción LightGBM** en la parte superior derecha (badge de riesgo ALTO/MEDIO/BAJO y factores TreeSHAP).
   - Pulsa en **"Ver trazabilidad"** para verificar el historial cronológico de cambios de estado (¡ya no da error 404!).
3. **Bandeja de Intervenciones:**
   - Entra a [http://localhost:5173/intervenciones](http://localhost:5173/intervenciones) (¡ya no da error 405 de método no permitido!).
4. **Lista de Espera y Cupos:**
   - Revisa [http://localhost:5173/lista-espera](http://localhost:5173/lista-espera) (carga la tabla sin pantalla blanca).
   - Revisa [http://localhost:5173/cupos](http://localhost:5173/cupos) (muestra los cupos liberados sin error 404).

---
*Para ver la guía completa y detallada de casos de prueba, consulta el archivo `GUIA_DE_PRUEBAS_PARA_EL_EQUIPO.md` incluido en este mismo paquete.*
