from datetime import timedelta

import pytest

from app.modules.intervenciones import consultas as inter_consultas
from app.modules.intervenciones import service as inter_service
from app.modules.citas import consultas as citas_consultas
from app.modules.auditoria.models import AuditoriaEvento
from tests.panel.conftest import AHORA

TIPOS = ["CITAS_SIN_INTERVENCION", "INTERVENCIONES_SIN_RESPUESTA", "OFERTAS_EN_CURSO"]


@pytest.mark.parametrize("estado", ["RECIBIDA", "CONFIRMADA", "REPROGRAMADA", "CANCELADA", "LIBERADA", "ATENDIDA", "NO_SHOW"])
@pytest.mark.parametrize("nivel", ["ALTO", "MEDIO", "BAJO", None])
def test_sin_intervencion_estado_y_riesgo(datos, estado, nivel):
    c = datos.cita(estado_actual=estado)
    if nivel:
        datos.pred(c, nivel)
    esperado = int(estado == "RECIBIDA" and nivel in ("ALTO", "MEDIO"))
    assert datos.lista().total == datos.resumen().pendientes.citas_sin_intervencion == esperado


@pytest.mark.parametrize("estado", ["PENDIENTE", "FALLIDA", "ENVIADA", "ENTREGADA", "RESPONDIDA"])
def test_cualquier_intervencion_excluye_alerta_inicial(datos, estado):
    c = datos.cita()
    datos.pred(c)
    datos.inter(c, estado)
    assert datos.lista().total == 0


@pytest.mark.parametrize("categoria", TIPOS[:2])
def test_optout_transversal_otra_fecha_y_especialidad(datos, categoria):
    c = datos.cita()
    datos.pred(c)
    if categoria == TIPOS[1]:
        datos.inter(c)
    otra = datos.cita(paciente_anon_id=c.paciente_anon_id, especialidad="PEDIATRIA",
                     fecha_hora_cita=AHORA - timedelta(days=5))
    datos.inter(otra, "RESPONDIDA", consentimiento_optout=True)
    assert datos.lista(categoria, especialidad="CARDIOLOGIA").total == 0
    # El opt-out no afecta el contacto de otro paciente.
    otro = datos.cita()
    datos.pred(otro)
    if categoria == TIPOS[1]:
        datos.inter(otro)
    assert datos.lista(categoria, especialidad="CARDIOLOGIA").total == 1


@pytest.mark.parametrize("minutos", [-1, 0, 1])
def test_horario_estrictamente_futuro(datos, minutos):
    c = datos.cita(fecha_hora_cita=AHORA + timedelta(minutes=minutos))
    datos.pred(c)
    assert datos.lista().total == int(minutos > 0)
    datos.inter(c)
    assert datos.lista(TIPOS[1]).total == int(minutos > 0)
    datos.cupo("EN_OFERTA", fecha_hora_cupo=c.fecha_hora_cita)
    assert datos.lista(TIPOS[2]).total == int(minutos > 0)


@pytest.mark.parametrize(("estado", "respuesta", "fecha_respuesta", "esperado"), [
    ("ENVIADA", None, None, 1), ("ENTREGADA", None, None, 1),
    ("PENDIENTE", None, None, 0), ("FALLIDA", None, None, 0),
    ("RESPONDIDA", "SIN_RESPUESTA", AHORA, 0), ("ENVIADA", "CONFIRMA", None, 0),
    ("ENTREGADA", None, AHORA, 0),
])
def test_espera_respuesta(datos, estado, respuesta, fecha_respuesta, esperado):
    c = datos.cita()
    datos.inter(c, estado, respuesta_paciente=respuesta, fecha_hora_respuesta=fecha_respuesta)
    assert datos.lista(TIPOS[1]).total == esperado


@pytest.mark.parametrize("estado_cita", ["RECIBIDA", "CONFIRMADA", "REPROGRAMADA", "CANCELADA", "LIBERADA", "ATENDIDA", "NO_SHOW"])
def test_espera_solo_citas_activas(datos, estado_cita):
    c = datos.cita(estado_actual=estado_cita)
    datos.inter(c)
    esperado = int(estado_cita in ("RECIBIDA", "CONFIRMADA", "REPROGRAMADA"))
    assert datos.lista(TIPOS[1]).total == esperado
    assert datos.resumen().intervenciones.total == 1


@pytest.mark.parametrize("tipo", TIPOS)
def test_paginacion_total_fuera_rango_y_una_sentencia(datos, sentencias, tipo):
    for i in range(5):
        if tipo == TIPOS[2]:
            datos.cupo("EN_OFERTA")
        else:
            c = datos.cita()
            datos.pred(c)
            if tipo == TIPOS[1]:
                datos.inter(c)
    sentencias.clear()
    r = datos.lista(tipo, limite=2, desplazamiento=2)
    assert len(sentencias) == 1
    assert r.total == 5 and len(r.items) == 2
    r2 = datos.lista(tipo, limite=2, desplazamiento=20)
    assert r2.total == 5 and r2.items == []
    clave = tipo.lower()
    assert getattr(datos.resumen().pendientes, clave) == 5
    assert datos.lista(tipo).items == datos.lista(tipo).items


@pytest.mark.parametrize("tipo", TIPOS)
def test_listado_vacio_con_total(datos, tipo):
    r = datos.lista(tipo)
    assert r.total == 0 and r.items == []


def test_orden_riesgo_probabilidad_fecha_id(datos):
    bajo = datos.cita()
    datos.pred(bajo, "MEDIO")
    primero = datos.cita(fecha_hora_cita=AHORA + timedelta(hours=2))
    datos.pred(primero)
    segundo = datos.cita(fecha_hora_cita=primero.fecha_hora_cita)
    datos.pred(segundo)
    assert [i.id_cita for i in datos.lista().items] == [primero.id_cita, segundo.id_cita, bajo.id_cita]


@pytest.mark.parametrize(("viejo", "nuevo", "ids_ordenados"), [
    ("ALTO", "BAJO", True), ("BAJO", "ALTO", True), ("MEDIO", "ALTO", False),
])
def test_paridad_prediccion_panel_citas_intervenciones(datos, db, viejo, nuevo, ids_ordenados):
    c = datos.cita()
    if ids_ordenados:
        datos.pred(c, viejo, fecha_hora_inferencia=AHORA - timedelta(hours=1))
        reciente = datos.pred(c, nuevo, fecha_hora_inferencia=AHORA)
    else:
        reciente = datos.pred(c, nuevo, fecha_hora_inferencia=AHORA)
        datos.pred(c, viejo, fecha_hora_inferencia=AHORA - timedelta(hours=1))
    assert inter_consultas.obtener_prediccion_reciente(db, c.id_cita).id_prediccion == reciente.id_prediccion
    assert datos.resumen().citas.por_riesgo[nuevo] == 1
    elegibles = inter_service.listar_citas_elegibles(db, ahora=AHORA, nivel_riesgo=nuevo)
    assert elegibles.total == int(nuevo != "BAJO")
    if elegibles.total:
        assert elegibles.items[0].riesgo.id_prediccion == reciente.id_prediccion
        assert datos.lista().items[0].id_prediccion == reciente.id_prediccion
    total, filas = citas_consultas.listar(db, desde=AHORA.date(), hasta=AHORA.date(), especialidad=None,
        medico=None, estado=None, nivel_riesgo=nuevo, con_intervencion=None, texto=None, limite=20, desplazamiento=0)
    assert total == 1 and filas[0].id_prediccion == reciente.id_prediccion
    for riesgo in ("ALTO", "MEDIO"):
        esperado = int(riesgo == nuevo)
        assert inter_service.listar_citas_elegibles(db, ahora=AHORA, nivel_riesgo=riesgo).total == esperado


def test_empate_timestamp_mayor_id_y_reintento_m05_conservado(datos, db):
    c = datos.cita(estado_actual="CONFIRMADA")
    datos.pred(c, "BAJO", fecha_hora_inferencia=AHORA)
    reciente = datos.pred(c, "ALTO", fecha_hora_inferencia=AHORA)
    assert datos.resumen().citas.por_riesgo["ALTO"] == 1
    datos.inter(c, "FALLIDA")
    r = inter_service.listar_citas_elegibles(db, ahora=AHORA)
    assert r.total == 1 and r.items[0].riesgo.id_prediccion == reciente.id_prediccion
    assert datos.lista().total == 0
    datos.inter(c, "FALLIDA")
    assert inter_service.listar_citas_elegibles(db, ahora=AHORA).total == 0


def test_ofertas_sin_eventos_y_confirmacion_excluida(datos, usuarios, db):
    cupo = datos.cupo("EN_OFERTA")
    assert datos.lista(TIPOS[2]).items[0].id_cupo_liberado == cupo.id_cupo_liberado
    for candidato in (100, 101, 102):
        db.add(AuditoriaEvento(modulo="REASIGNACION", accion="OFERTAR", entidad_afectada="cupos_liberados",
            id_entidad=cupo.id_cupo_liberado, datos_after={"id_candidato": candidato}, direccion_ip="127.0.0.1"))
    db.flush()
    assert datos.lista(TIPOS[2]).total == datos.resumen().pendientes.ofertas_en_curso == 1
    datos.reasignar(cupo, usuarios["RECEPCION"])
    assert datos.lista(TIPOS[2]).total == 0


@pytest.mark.parametrize("tipo", TIPOS)
def test_filtro_especialidad_pendientes(datos, tipo):
    for especialidad in ("CARDIOLOGIA", "PEDIATRIA"):
        if tipo == TIPOS[2]:
            datos.cupo("EN_OFERTA", especialidad=especialidad)
        else:
            c = datos.cita(especialidad=especialidad)
            datos.pred(c)
            if tipo == TIPOS[1]:
                datos.inter(c)
    assert datos.lista(tipo).total == 2
    assert datos.lista(tipo, especialidad="CARDIOLOGIA").total == 1
