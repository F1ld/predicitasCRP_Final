# Evidencia funcional de navegador — continuación de fase 0

Fecha: 03/11/2026. Frontend temporal `http://127.0.0.1:5174`; API temporal `http://127.0.0.1:8001`; PostgreSQL restaurado aislado. No se accedió al volumen original.

Estos son **extractos textuales** de los snapshots de accesibilidad devueltos por la herramienta de navegador, no screenshots ni un volcado completo. Se omiten filas de pacientes, referencias efímeras de elementos y credenciales. El usuario autorizó esta evidencia alternativa en `decision_evidencia_visual.json`.

## Login, antes de autenticar

URL observada: `/login`. Snapshot sin truncamiento a profundidad 20.

```text
[RootWebArea] "PrediCitas CRP"
  [heading] "Cada cita merece seguimiento."
  [heading] "Iniciar sesión"
  [textbox] "Correo institucional"
  [textbox] "Contraseña"
  [button] "Ingresar"
  [DisclosureTriangle] "Usuarios de demostración" expanded=false
  [StaticText] "Entorno académico · Datos sintéticos de demostración"
```

## Bandeja, después de autenticar

Se usó la cuenta desechable de Recepción creada previamente solo en la copia restaurada. URL final observada: `/citas`.

```text
[RootWebArea] "PrediCitas CRP"
  [StaticText] "Fase 0 Recepcion temporal"
  [StaticText] "Recepción"
  [button] "Cerrar sesión"
  [navigation] "Principal"
    [link] "Citas"
    [link] "Importar CSV"
    [link] "Intervenciones"
    [link] "Reporte de intervenciones"
    [link] "Lista de espera"
    [link] "Mi cuenta"
    [link] "Cupos liberados"
    [link] "Reporte de reasignaciones"
  [heading] "Bandeja de citas"
  [group] "Filtros de citas"
  [button] "Aplicar filtros"
  [button] "Limpiar"
  [heading] "Citas encontradas 1122"
  [region] "Resultados de citas"
    [table] "Citas que cumplen los filtros aplicados"
```

El snapshot final extenso estaba truncado por tamaño, pero contenía explícitamente el total y filas cargadas. Los logs del servidor aislado confirmaron 200 en `/auth/login`, `/auth/me`, `/citas/catalogos` y `/citas?limite=20&desplazamiento=0`. La comprobación HTTP de salud confirmó 200 y CORS para el origen temporal.

La espera por el texto concatenado `Citas encontradas 1122` agotó su plazo porque el encabezado y número están divididos en nodos. Se inspeccionó el snapshot y las respuestas antes de continuar; no se repitió el formulario ni se interpretó el timeout como un fallo del backend.

No se certifican apariencia pixel a pixel, responsividad, accesibilidad completa ni todos los flujos E2E. Se conserva la línea base de pruebas con sus fallos conocidos.
