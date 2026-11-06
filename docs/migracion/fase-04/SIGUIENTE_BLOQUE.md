# Siguiente bloque de fase 4 — D, todavía no implementado

A, B, B.1 y C están registrados. La ejecución vigente de C es
`bloque-c-20261106-01`: diagnóstico 341/0, S-03 corregido y S-08 backend HTTP
implementado. Esto **no cierra fase 4** ni certifica carreras concurrentes.

Pendiente D:

1. Auditar orden global de locks y recarga de estado después de esperar locks;
   no basta haber añadido `with_for_update` ni ejecutar dos llamadas secuenciales.
2. Probar solicitudes concurrentes reales de liberación/reasignación/ofertas en
   PostgreSQL aislado: una única asignación efectiva, sin historiales/eventos
   duplicados ni transacciones parcialmente persistidas.
3. Ampliar rollback y límites de composición a todos los workflows multímódulo,
   con observaciones independientes. Conservar las pruebas de identidad y B.1/C.
4. Revisar las tareas restantes del plan: adaptadores de lectura compuesta,
   excepciones de composición/reporting explícitas, ausencia de ciclos y APIs
   internas permitidas. No confundir routers limpios con encapsulación total.
5. Construir la imagen final de fase 4, comprobar el contenido empaquetado sin
   bind de fuentes y repetir paridad OpenAPI/DDL/predicciones, regresión y cobertura.
6. Registrar código y evidencia por separado, detener laboratorio conservando
   recursos y verificar el paquete desde un clon limpio antes del cierre formal.

S-02 de colección IA conserva su gate de fase 7; no declarar suite completa
verde por aprobar el diagnóstico. Frontend/E2E visual y S-06 no fueron certificados
en C. No iniciar fase 5 ni tocar esquema/modelo/credenciales/principal sin el alcance
y las aprobaciones correspondientes.
