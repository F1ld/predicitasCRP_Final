# Límites introducidos en el bloque A

## Propiedad y llamadas

- `usuarios/models.py` es la única definición de `Usuario`; nombre físico,
  columnas, constraints, FKs y revisiones de Alembic no cambian.
- `usuarios/public.py` ofrece consultas de identidad y operaciones de credenciales.
  Las consultas entregan `Identidad`, una dataclass inmutable sin `password_hash`
  ni instrumentación ORM. Verificar una clave devuelve un booleano, no su hash.
- `auth/public.py` publica el principal y las dependencias de autorización.
  Los módulos consumidores dejan de importar modelos/dependencias privados de Auth.
- Usuarios ya no depende de repositorios, reloj, schemas ni servicios privados
  de Auth. La política de contraseña está en Usuarios y el tiempo técnico en core.
- `auditoria/public.py` publica append componible y consultas de login/logout.
  Las consultas conservan el orden, ventana y condiciones de la implementación anterior.
- `bootstrap/models.py` registra todos los modelos. Main, Alembic, seed y tests
  vigentes usan ese registro. El shim `core/models.py` permanece para herramientas
  históricas; no aloja otro registro.

## Transacciones: lo hecho y lo que no se afirma

- `usuarios.identidad.cambiar_clave` bloquea la fila y modifica credenciales y
  timestamp de revocación en la sesión recibida, **sin commit propio**.
- El caso de uso Auth conserva el commit de clave + evento y emite el token
  nuevo a un milisegundo del timestamp de revocación, como antes.
- Los intentos fallidos/bloqueados se confirman explícitamente antes del error;
  no se sustituyen por un append que se perdería al cerrar la sesión del 401/429.
- El append de auditoría no confirma por sí solo. Para identidad admite el mismo
  timestamp UTC de precisión milisegundo, sin manipular su modelo desde Auth.
- Esto **no** implementa todavía una unidad de trabajo general, los workflows
  de liberación/respuesta/cancelación o una política global de locks. Tampoco
  demuestra todavía ausencia de escrituras cruzadas en los otros módulos.

## Compatibilidad deliberada

Se mantienen `auth/models.py`, `auth/reloj.py` y `auth/repository.py` como puentes
históricos mínimos. No se mantienen dos clases Usuario, dos relojes ni consultas
SQL duplicadas. El puente de consultas entrega DTO sin secretos, no ORM.
Los tests vigentes inyectan `app.core.reloj`; las herramientas históricas no se
reescriben en masa. Los imports de `citas.router.reloj` siguen resolviendo al mismo
objeto de dependencia, pero Intervenciones ya no importa ese router.

La API pública y sus schemas deben compararse sin regenerar el snapshot para
ocultar diferencias. Las pruebas nuevas revisan únicamente límites ya migrados;
no contienen una whitelist que dé por aprobados los acoplamientos pendientes.
