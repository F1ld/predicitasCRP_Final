# Arquitectura definida en fase 1

Estas especificaciones son el destino de la reestructuración, no cambios ya aplicados a producción.

1. [Decisiones ADR-001 a ADR-008](DECISIONES.md): componentes, propiedad, transacciones, entorno, datos, registry, IA y compatibilidad.
2. [Rutas y consumidores](RUTAS_Y_CONSUMIDORES.md): 15 rutas de módulos, roles, menús, código legacy y las familias de 55 operaciones API.
3. [Mapa de dependencias y escrituras](MAPA_DEPENDENCIAS_Y_ESCRITURAS.md): imports, sitios de persistencia, excepciones y workflows futuros.
4. [Estabilización y recorrido E2E](ESTABILIZACION_Y_E2E.md): deudas conocidas, gates y pruebas pendientes; no arreglos realizados.
5. [Contratos](../../contracts/README.md): OpenAPI público congelado y API IA/schemas objetivo con ejemplos.
6. [Evidencias de fase 1](../migracion/fase-01/README.md): validaciones, alcance y comandos reproducibles.

El principal confirmado es `predicitas-crp_pgdata`. No ejecutar scripts de seed, entrenamiento, provisión o migraciones por el mero hecho de leer estos documentos. El plan raíz sigue siendo la bitácora de fases.
