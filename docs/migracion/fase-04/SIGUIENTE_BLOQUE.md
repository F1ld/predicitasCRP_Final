# Siguiente bloque de fase 4 — no implementado todavía

Orden propuesto a partir del árbol tras el bloque A:

1. Caracterizar por separado POST y PATCH legacy de Intervenciones: respuesta
   sin transición frente a respuesta con confirmación/liberación. Preservar
   consentimiento, opt-out y las diferencias documentadas; no endurecerlas
   silenciosamente durante la extracción de workflows.
2. Definir snapshots/operaciones públicas de Citas e Intervenciones y creación
   componible de cupo en Lista de Espera. No exportar repositorios completos.
3. Sacar la coordinación multímódulo de `citas/service.py` e
   `intervenciones/service.py` a workflows. Una transición efectiva produce
   un solo historial; cita, respuesta, cupo y auditoría comparten transacción.
4. Establecer orden de locks consistente (incluida recarga de estado al esperar
   un lock); probar solicitudes simultáneas, no solo sesiones secuenciales.
5. Extraer oferta/rechazo/desistimiento de `lista_espera/router.py`, con
   estados, compatibilidad, eventos e historial (S-08). El diagnóstico conserva
   S-03: la prueba antigua de reasignación trata una página como si fuera lista.
6. Mover lecturas de repositorio y `db.get` fuera de routers de Intervenciones,
   Lista de Espera e IA, y el commit de exportación de Reportes a su caso de uso.
7. Separar consultas compuestas de lectura, documentar excepciones autorizadas
   y ampliar los tests de arquitectura sin habilitar escrituras ajenas.

Los tests nuevos del bloque A no se presentan como prueba de estas tareas. No
es suficiente añadir `public.py` que reexporte modelos privados y dejar intactas
las escrituras cruzadas. El cierre completo exige PostgreSQL real, rollback tras
flush y ausencia de doble liberación/reasignación bajo concurrencia.
