# ToDo del frontend

Registrar aquí trabajo pendiente. Las tareas completadas se trasladan a changelog.md y su especificación vigente.

## Panel Operativo

**Implementado el 09/11/2026**, validado con backend aislado, sin despliegue al piloto.

- [Especificación](panel-operativo.md).
- [Registro de cambios](changelog.md).
- [Resultados de validación](validacion-panel-operativo.md).

La funcionalidad definida está implementada: filtros, indicadores, categorías paginadas, actualización manual, permisos, inicio por rol y retorno directo desde detalles.

Salvedades y seguimiento:

- [ ] Cerrar la deuda preexistente de la suite global: 59 fallos ya presentes antes del panel (40 en Detalle de Citas, 17 en citas.test, 1 en MiCuenta y 1 en componentes). El panel no introdujo regresiones nuevas; no se declara la suite global verde.
- [ ] Revisión visual adicional con zoom real del navegador; ya se verificaron los anchos 1440/1024/390 px y navegación por teclado.

Los recorridos secundarios con retorno de varios niveles y el despliegue conservan su alcance separado.

## REP-01 · Pantalla de Reporte diario

Vista implementada para Recepción. [Comportamiento, alcance y validación](reporte-diario.md).
