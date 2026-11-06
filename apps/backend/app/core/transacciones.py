"""Primitivas técnicas de sesión; no conoce módulos ni cierra transacciones."""
from sqlalchemy.orm import Session


def bloquear_fila(db: Session, modelo, identidad: int):
    """FOR UPDATE + refresh tras espera, conservando cambios propios ya bloqueados.

    Una sesión con expire_on_commit=False puede tener una copia obsoleta aunque
    SELECT FOR UPDATE haya esperado correctamente. populate_existing es esencial.
    Si el coordinador ya cambió esta fila dentro de la misma transacción, volcar
    solo esa fila primero evita descartar su cambio al refrescarla.
    """
    existente = db.identity_map.get((modelo, (identidad,), None))
    if existente is not None and existente in db.dirty:
        db.flush([existente])
    return db.get(modelo, identidad, with_for_update=True, populate_existing=True)
