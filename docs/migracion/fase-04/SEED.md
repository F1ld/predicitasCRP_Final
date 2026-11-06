# Validación complementaria del seed — alcance congelado

Autorizada por el usuario tras D. No cambia el seed ni el generador/importador,
credenciales existentes, modelo, CSV o esquema. Paquete D por ID inmutable,
comparado con las fuentes registradas; PostgreSQL nuevo, red interna sin puertos
host y volumen exclusivo. No adopta ni reanuda recursos previos.

Secuencia: migrar BD vacía, ejecutar el seed real con fallo inducido tras flush
de usuarios/citas/historial/auditoría; comprobar invisibilidad desde otra conexión
y reversión al cerrar sesión. Luego carga completa (1000 históricas + 80 próximas,
semilla 42, corte 2026-11-06, reloj fijo Lima), comprobación de todos los campos de
negocio, relaciones, estados, target, historial y auditoría. Reejecutar con otra
contraseña efímera: todas las filas y contraseñas anteriores deben permanecer
idénticas. Cada ejecución exitosa debe intentar un solo commit; la fallida ninguno.

No confundir reejecución de carga completa con recuperación de cargas parciales:
el retorno legacy ante alguna CIT-SIM-* permanece igual (deuda de fase 6). Las
secuencias pueden avanzar tras rollback: no se exige continuidad de IDs.

Herramientas registradas antes de validar; fallos conservados, parada en finally.
Publicación separada, solo resultados sanitizados; nunca env, claves o hashes de
contraseña. Verificación del paquete en clon limpio antes de pasar a fase 5.

```powershell
python -B docs/migracion/fase-04/validar_seed.py ejecutar --run-id seed-20261106-01
python -B docs/migracion/fase-04/validar_seed.py publicar --run-id seed-20261106-01
python -B docs/migracion/fase-04/validar_seed.py verificar --run-id seed-20261106-01
```

Estado: **APROBADO**, ejecución `seed-20261106-01`, código de herramientas
`7d8c35b`. 3 usuarios, 1080 citas (1000 históricas + 80 RECIBIDA), 2080 historiales
y un evento IMPORT. Fallo tras flush sin commit y rollback completo observado
independientemente. Reejecución con un commit y todas las filas/contraseñas
idénticas, sin duplicados. Paquete D sin montar backend, rol app sin env owner.
Fuentes y protegidos intactos; laboratorio detenido, recursos conservados.

[Resultados sanitizados](evidencia/seed-20261106-01/resumen.json) y
[manifiesto](evidencia/seed-20261106-01/manifest.json). Fase 5 puede iniciarse
aislada, sin conectar todavía el backend ni modificar su predictor integrado.
