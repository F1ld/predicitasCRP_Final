# Corrección quirúrgica de fase 5

Autorizada tras revisión del usuario. Retorno de entrega `fe4768b`; baseline de
backend/frontend/contratos `af13b3b`. No se modifica backend, frontend, algoritmo,
modelo, CSV ni esquema. No se inicia fase 6/7 ni se conecta el consumidor IA.

## Gates congelados antes de ejecución formal

1. Clave explícita, fallo de arranque ante ausencia/vacío, APIKey en OpenAPI.
2. Manifiesto de confianza versionado y hash comprobado antes de deserializar los
   mismos bytes; compatibilidad Python/librerías/clases/features/catálogos/versión,
   umbrales y smoke. Fallo = no ready, sin entrenamiento automático.
3. Metadata legacy fiel al artefacto, sin defaults de éxito. `generado_en` identifica
   la creación del manifiesto de importación, no la generación desconocida del raw.
   Conteos inferidos de tamaños/tasas del artefacto, sin inventar hashes ni IDs.
4. Versiones obligatorias y enteros sin coerciones; JSON schemas congelados
   comprueban solicitudes/respuestas, metadata y errores. Bordes 0.300/0.450,
   lote 0/1/100/101, no finitos sin fallback. Sin modificar fórmulas ni redondeos.
5. Recepción streaming acotada a 256 KiB, no consumir el resto tras exceso;
   presupuesto de recepción 10 s. No confundirlo con timeout duro de cómputo.
6. Imagen nueva con contexto contractual explícito; no-root, filesystem RO,
   modelo montado RO, red none, sin DSN ni fuentes backend. 1 worker, máximo 16
   conexiones y 1 hilo por runtime nativo. Smoke HTTP real del lote máximo con
   presupuesto local de 10 s, contenedor acotado a 2 CPU/1 GiB. Esto no equivale
   a certificación de carga prolongada ni garantiza interrupción de cómputo nativo.
7. Todas las pruebas previas pasan, nuevas regresiones aprobadas y cobertura ≥80 %;
   resultados medidos de JUnit/coverage JSON. Paridad de todos los campos contra
   los casos congelados de fase 0 y los cinco de la suite IA original, más 200
   adicionales deterministas, usando backend preservado y expectativas congeladas.
8. Código registrado antes de ejecutar, imagen usada por ID inmutable, fuentes de
   paquete iguales al commit (EOL normalizado), protegidos iguales antes/después,
   resultados exclusivos sin sobrescritura. Evidencia sanitizada separada y
   verificación de hashes desde clon limpio Windows con autocrlf.

## Alcance pendiente que impide el cierre total

Se restauran sin reducir los ítems originales de fase 5: separación autónoma del
entrenamiento y migración del generador/datasets/CSV con retirada temporal definida.
Esta entrega corrige seguridad/contrato/evidencia del servicio de inferencia; no
afirma haber terminado esas extracciones ni las desplaza a fase 6 sin aprobación.
El presupuesto/timeout de inferencia bajo concurrencia también requiere resolución
antes de marcar ese ítem completo. Fase 5 permanece EN CURSO aunque estos gates pasen.

## Ejecución

```powershell
python -B docs/migracion/fase-05/validar_ia.py ejecutar --run-id ia-correccion-20261106-01
python -B docs/migracion/fase-05/validar_ia.py publicar --run-id ia-correccion-20261106-01
python -B docs/migracion/fase-05/validar_ia.py verificar --run-id ia-correccion-20261106-01
```

Estado de corrección: **VALIDADA**, ejecución `ia-correccion-20261106-03`.
Seed complementario permanece aceptado en `seed-20261106-01`; no se reabre su
laboratorio ni se alteran sus pruebas.

Intento `ia-correccion-20261106-01` conservado: 83 pruebas empaquetadas aprobadas,
pero la sonda externa no encontraba `/app` al ejecutarse desde `/checks`. Corregido
PYTHONPATH del contenedor de validación; no fue fallo de inferencia. No se cuenta
ese intento como aceptación; repetir con identidad nueva.
`ia-correccion-20261106-02` aprobó 83 pruebas, HTTP real y 203 casos diferenciales
(3 de fase 0 + 200). Se amplió el runner para incluir también todos los casos de
la suite original en la comparación diferencial, no solo sus pruebas unitarias.
Se conserva 02 como intermedio aprobado, no como evidencia de la ampliación.

## Resultado vigente

- Implementación `d0ca97f`; runner probado `bba0e61` (incluye `5c260bf`/`d9c523e`).
- **83/83 pruebas** (21 previas conservadas + 62 nuevas), cobertura
  **96,00725952813067 %**. Tres autopruebas stdlib del runner aprobadas.
- **207 casos diferenciales**: 7 congelados únicos (3 de fase 0 y 5 de la suite
  original, con un caso compartido) + 200 semilla 42. Todos los campos idénticos,
  expectativas congeladas comprobadas, presentes BAJO/MEDIO/ALTO.
- HTTP real con readiness, rechazo de falta de clave y lote de 100: **0,983 s**
  (presupuesto local 10 s). Modelo sin cambios, UID 1000, 2 CPU/1 GiB, red none,
  filesystem y modelo RO; backend no montado, sin credenciales de BD.
- Imagen ejecutada por ID:
  `sha256:21c8cd34539de93335c813b13a2bc7e81e254ba2ce293a9df90782c5e09e3bbf`.
- Fuentes empaquetadas iguales a registradas, protegidos y baseline operativo
  intactos. Evidencia separada `8dd4cdd`, hashes del índice y del paquete desde clon
  limpio Windows/autocrlf aprobados. También seed verifica en ese clon.
- Sin contenedores correctivos en ejecución; servicio previo ajeno intacto,
  imágenes y resultados fallidos/intermedios conservados. No despliegue principal.

[Evidencia correctiva](evidencia/ia-correccion-20261106-03/manifest.json).
La corrección no declara cierre total: quedan los pendientes de alcance indicados
arriba. Tampoco certifica suite completa backend ni E2E frontend.
