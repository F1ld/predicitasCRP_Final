"""Casos de uso HTTP: un único commit de las operaciones componibles."""
from app.modules.lista_espera.casos import (
    crear_candidato, actualizar_candidato, listar_espera, listar_cupos_paginados,
    listar_cupos, obtener_detalle_cupo, proponer_candidatos_para_cupo,
)
from app.modules.lista_espera import public as operaciones


def registrar_oferta(db, id_cupo, id_candidato, *, usuario, ip):
    resultado = operaciones.ofrecer_cupo(db, id_cupo, id_candidato, usuario=usuario, ip=ip)
    db.commit()
    return resultado


def cerrar_oferta(db, id_cupo, *, cierre, usuario, ip):
    resultado = operaciones.cerrar_oferta(db, id_cupo, cierre=cierre, usuario=usuario, ip=ip)
    db.commit()
    return resultado


def reasignar_cupo(db, id_cupo, datos, *, usuario, ip):
    resultado = operaciones.reasignar_cupo(db, id_cupo, datos, usuario=usuario, ip=ip)
    db.commit()
    return resultado
