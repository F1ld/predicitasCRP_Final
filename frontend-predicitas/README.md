# PrediCitas CRP · Frontend

![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9%20estricto-3178C6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-4-06B6D4?logo=tailwindcss&logoColor=white)
![Vitest](https://img.shields.io/badge/Vitest-cobertura%20%E2%89%A5%2075%25-6E9F18?logo=vitest&logoColor=white)

Interfaz web del **MVP PrediCitas CRP**: gestión predictiva de citas médicas **posterior al agendamiento** para la Clínica Ricardo Palma, Sede San Isidro (Cardiología, Traumatología y Pediatría).

> **Proyecto académico.** Universidad Privada del Norte (UPN), ciclo 2026-2, curso *Administración de Proyectos de Software*, Grupo 05.
> **Todos los datos son sintéticos y seudonimizados** (`paciente_anon_id`). La interfaz nunca muestra ni pide datos personales reales (Ley N.° 29733).

**API (backend):** [F1ld/backend-predicitas](https://github.com/F1ld/backend-predicitas)

---

## Contenido

1. [Qué ofrece la interfaz](#1-qué-ofrece-la-interfaz)
2. [Estado del desarrollo](#2-estado-del-desarrollo)
3. [Tecnologías](#3-tecnologías)
4. [Requisitos previos](#4-requisitos-previos)
5. [Inicio rápido](#5-inicio-rápido)
6. [Scripts disponibles](#6-scripts-disponibles)
7. [Estructura del proyecto](#7-estructura-del-proyecto)
8. [Cómo agregar un módulo](#8-cómo-agregar-un-módulo)
9. [Cliente de la API y sesión](#9-cliente-de-la-api-y-sesión)
10. [Calidad: pruebas, accesibilidad y responsive](#10-calidad-pruebas-accesibilidad-y-responsive)
11. [Flujo de trabajo y contribución](#11-flujo-de-trabajo-y-contribución)
12. [Glosario](#12-glosario)
13. [Equipo](#13-equipo)

---

## 1. Qué ofrece la interfaz

La usan tres roles, y cada uno ve solo lo que su permiso le permite:

| Vista | Ruta | Roles | Para qué |
|---|---|---|---|
| Inicio de sesión | `/login` | Público | Acceso con correo institucional y contraseña |
| Citas | `/citas` | Todos | Bandeja con filtros, paginación, nivel de riesgo y acceso al detalle |
| Detalle de cita | `/citas/:id` | Todos | Datos, historial de estados, cambio de estado, check-in y cálculo de riesgo |
| Importar CSV | `/citas/importar` | Administrador, Recepción | Carga de citas con validación fila por fila |
| Intervenciones | `/intervenciones` | Todos (Técnico IA solo consulta) | Citas elegibles, nueva intervención con consentimiento y seguimiento |
| Reporte de intervenciones | `/reportes/intervenciones` | Administrador, Recepción | REP-02 con filtros, exportación a CSV/Excel e impresión a PDF |
| Usuarios | `/usuarios` | Administrador | Alta, edición, activación y restablecimiento de acceso |
| Mi cuenta | `/mi-cuenta` | Todos | Cambio de contraseña y datos de la sesión |
| Lista de espera · Cupos · Reasignaciones | `/lista-espera` · `/cupos` · `/reportes/reasignaciones` | Administrador, Recepción | Lista de espera, cupos liberados y reasignación con confirmación humana *(a la espera de su API)* |

El riesgo siempre se presenta como **orientación, nunca como decisión clínica**. Mientras provenga del simulador, lleva el rótulo «Resultado simulado».

## 2. Estado del desarrollo

| Módulo | Estado |
|---|---|
| Base: núcleo, rutas por módulo, sesión y diseño institucional | ✅ Certificado por QA |
| M01 · Autenticación, usuarios y Mi cuenta | ✅ Certificado por QA |
| M02 · Bandeja, detalle, registro, importación y check-in | ✅ Certificado por QA |
| M05 · Intervención inteligente y reporte REP-02 | ✅ Certificado por QA |
| M06 · Lista de espera y reasignación | 🔨 Interfaz lista; falta su API en el backend |
| M07 · Panel operativo · M08 · Auditoría · M09 · Vistas de IA | 📐 Planificado |

## 3. Tecnologías

| Capa | Tecnología |
|---|---|
| Interfaz | React 18.3 · TypeScript 5.9 en modo estricto |
| Rutas | React Router 7 |
| Estilos | Tailwind CSS 4, más un sistema de diseño propio en `src/index.css` |
| Construcción | Vite 8 |
| Pruebas | Vitest · React Testing Library · jsdom · cobertura V8 (umbral 75 %) |
| Calidad de código | ESLint con reglas de hooks · `tsc --noEmit` |
| Entorno | Node.js 22 · imagen Docker `node:22-alpine` |

## 4. Requisitos previos

- **Node.js 22** y npm. La imagen oficial de desarrollo y las pruebas de referencia usan Node 22.
- La **API** del [backend](https://github.com/F1ld/backend-predicitas) en marcha (por defecto en `http://127.0.0.1:8000`) para usar la aplicación de verdad. Las pruebas automáticas no la necesitan.
- Opcional: Docker, para levantar la interfaz en contenedor.

## 5. Inicio rápido

1. Levanta el backend siguiendo su README (`docker compose up --build -d`) y carga los datos de demostración.
2. Arranca la interfaz:

```bash
git clone https://github.com/F1ld/frontend-predicitas.git
cd frontend-predicitas
npm ci
cp .env.example .env          # en Windows PowerShell: Copy-Item .env.example .env
npm run dev                   # http://localhost:5173
```

3. Entra con un usuario demo del seed del backend: `admin@predicitas.crp`, `recepcion@predicitas.crp` o `tecnico.ia@predicitas.crp`, con la contraseña que elegiste al cargar el seed.

**Variable de entorno:**

| Variable | Para qué | Por defecto |
|---|---|---|
| `VITE_API_URL` | URL base de la API, sin `/docs` ni barra final | `http://127.0.0.1:8000` |

Las variables `VITE_*` quedan visibles en el navegador: **nunca guardes secretos en ellas**. La API debe permitir el origen de la interfaz en su CORS (por defecto permite `http://localhost:5173` y `http://127.0.0.1:5173`).

**Con Docker:**

```bash
docker build -t predicitas-web .
docker run --rm -p 5173:5173 -e VITE_API_URL=http://localhost:8000 predicitas-web
```

## 6. Scripts disponibles

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo con recarga en caliente |
| `npm run typecheck` | Revisión de tipos (`tsc --noEmit`, modo estricto) |
| `npm run lint` | TypeScript y luego ESLint |
| `npm run build` | Compila TypeScript y genera `dist/` para producción |
| `npm run test` | Vitest con cobertura; falla si las líneas cubiertas bajan de 75 % |
| `npm run preview` | Sirve localmente el build de `dist/` |

## 7. Estructura del proyecto

```text
.
├── src/
│   ├── main.tsx                 # monta React, el router y el proveedor de sesión
│   ├── App.tsx                  # descubre las rutas de cada módulo
│   ├── index.css                # sistema de diseño: colores, tipografía y componentes base
│   ├── nucleo/                  # piezas compartidas por todos los módulos
│   │   ├── api/                 # cliente HTTP, ApiError, tipos comunes y useConsulta
│   │   ├── auth/                # sesión, useAuth y RutaProtegida
│   │   ├── sesion/              # renovación de token y cierre por inactividad
│   │   ├── layout/              # cabecera, menú por rol y ranuras de módulos
│   │   ├── componentes/         # mensajes, carga, estados vacíos, riesgo, iconos y marca
│   │   └── formato/             # fechas en America/Lima y etiquetas
│   ├── modulos/                 # una carpeta por módulo funcional
│   │   ├── sesion/              # login y Mi cuenta
│   │   ├── usuarios/            # gestión de usuarios
│   │   ├── citas/               # bandeja, detalle, registro e importación
│   │   ├── intervenciones/      # elegibles, seguimiento y REP-02
│   │   └── lista-espera/        # lista de espera, cupos y reasignaciones
│   └── pruebas/                 # configuración común de Vitest
├── tests/                       # herramienta heredada de validación de diseño y capturas de referencia
├── public/                      # favicon e iconos
├── Dockerfile
├── vite.config.ts
├── eslint.config.js
└── package.json
```

Las pruebas viven **junto al código** (`*.test.ts` o `*.test.tsx`). `src/modulos/prueba-ranura/` es un módulo técnico que solo existe en modo de pruebas, para comprobar el descubrimiento de rutas.

## 8. Cómo agregar un módulo

No hace falta editar el router global ni el menú: ambos descubren los archivos de cada módulo con `import.meta.glob`.

1. Crea `src/modulos/<modulo>/`.
2. Agrega `rutas.tsx`, que exporta por defecto las rutas con sus roles:

```tsx
import type { RutaModulo } from "../../nucleo/layout/ranuras";
import Vista from "./Vista";

const rutas: RutaModulo[] = [
  { ruta: "/mi-modulo", elemento: <Vista />, roles: ["ADMINISTRADOR"] },
];

export default rutas;
```

3. Si necesita menú, agrega `menu.ts`:

```ts
import type { EntradaMenu } from "../../nucleo/layout/ranuras";

const menu: EntradaMenu[] = [
  { etiqueta: "Mi módulo", ruta: "/mi-modulo", icono: "calendario", roles: ["ADMINISTRADOR"], orden: 30 },
];

export default menu;
```

El menú se filtra por rol y se ordena por `orden`. Los roles de la ruta y del menú deben coincidir. Ocultar una acción en el navegador **no reemplaza** la validación de permisos de la API.

## 9. Cliente de la API y sesión

Usa `api<T>` del núcleo, con los tipos del contrato del módulo:

```ts
import { api, ApiError } from "../../nucleo/api/cliente";
import type { Pagina } from "../../nucleo/api/tipos";
import type { CitaResumenOut } from "./tipos";

try {
  const pagina = await api<Pagina<CitaResumenOut>>("/citas", { params: { limite: 20, desplazamiento: 0 } });
} catch (fallo: unknown) {
  if (fallo instanceof ApiError) {
    // fallo.status, fallo.codigo, fallo.mensaje y fallo.campos
  }
}
```

- **Opciones:** `metodo`, `params`, `json`, `form`, `archivo` (`FormData`) y `signal`, para cancelar la petición.
- **Errores:** la API responde siempre `{ error: { codigo, mensaje, campos } }`. La interfaz reacciona al `codigo` y muestra el `mensaje`. Un fallo de red llega con `status: 0` y `codigo: "ERROR_CONEXION"`.
- **Consultas:** `useConsulta<T>` maneja la carga, los datos, el error y el reintento, e impide que una respuesta atrasada pise a la vigente.
- **Sesión:**
  - el token se guarda en `sessionStorage` y se envía como `Authorization: Bearer`;
  - un 401 o una sesión invalidada devuelve al login con un aviso;
  - la sesión se renueva antes de expirar y se cierra por inactividad;
  - nunca se almacenan contraseñas.

## 10. Calidad: pruebas, accesibilidad y responsive

```bash
npm run typecheck && npm run lint && npm run build && npm run test
```

- **Pruebas:** más de 500 pruebas de Vitest y React Testing Library, con cobertura de líneas superior al 99 %. La referencia es Node 22, el mismo de la imagen Docker.
- **Accesibilidad (WCAG 2.2 AA):**
  - contraste ≥ 4,5:1 en todo el texto;
  - navegación completa por teclado, con foco visible y enlace «Ir al contenido»;
  - diálogos que atrapan el foco y se cierran con Escape;
  - respeta `prefers-reduced-motion`.
- **Responsive:** sin scroll horizontal en 320, 360, 768, 1024, 1280 y 1440 px. El menú se reparte en varias filas cuando no cabe.
- **Estados:** cada vista con datos muestra cargando, con datos, vacío y error. Los formularios muestran editando, enviando, error y éxito.

## 11. Flujo de trabajo y contribución

- **Ramas:** `main` contiene las versiones estables; el trabajo se integra desde ramas de trabajo como `Project-Manager`, por *pull request*.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/es/) en español, con el requisito que implementan. Por ejemplo: `feat(citas): registro manual de cita (RF-010)`.
- **Antes de abrir un PR:** typecheck, lint, build y pruebas en verde, con cobertura ≥ 75 %. Los nombres de campos, rutas y enums deben ser los mismos que usa la API.

## 12. Glosario

| Término | Significado |
|---|---|
| **No-show** | El paciente no asiste a su cita y no avisa. |
| **Riesgo** | Probabilidad de no-show calculada por el servicio de inferencia: BAJO, MEDIO o ALTO. |
| **Intervención** | Recordatorio simulado (WhatsApp, SMS o llamada) a una cita de riesgo ALTO o MEDIO. |
| **Opt-out** | El paciente pide no recibir más mensajes. |
| **Cupo liberado** | Horario que queda libre cuando el paciente libera su cita. |
| **Confirmación humana** | Ninguna reasignación de cupo ocurre sin que una persona la confirme. |
| **Resultado simulado** | Rótulo obligatorio mientras el riesgo venga del simulador. |

## 13. Equipo

Grupo 05 · UPN 2026-2

| Rol | Integrante |
|---|---|
| Director del proyecto | Nicolas Goray |
| Programador y tester | Anders Ramirez |
| Datos e IA | Deivi Ferrer |
| Calidad | Jose Gutierrez |

---

<sub>Proyecto académico con fines educativos. Cliente de referencia: Clínica Ricardo Palma, Sede San Isidro. Ningún dato de esta aplicación corresponde a pacientes reales.</sub>
