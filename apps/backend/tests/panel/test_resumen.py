from datetime import date, timedelta, timezone

import pytest

from app.core.dominio import ESTADOS_CITA, ESTADOS_CUPO, ESTADOS_INTERVENCION
from app.modules.panel.service import contexto
from tests.panel.conftest import AHORA


def test_vacio(datos):
    r = datos.resumen()
    assert r.citas.total == r.intervenciones.total == r.cupos.total_liberados == 0
    assert r.cupos.tasa_recuperacion_pct is None
    assert set(r.citas.por_estado) == set(ESTADOS_CITA)
    assert set(r.intervenciones.por_estado) == set(ESTADOS_INTERVENCION)
    assert set(r.cupos.por_estado) == set(ESTADOS_CUPO)
    assert all(v == 0 for v in r.citas.por_riesgo.values())


def test_estados_y_riesgos_incluyen_finalizados(datos):
    niveles = ["ALTO", "MEDIO", "BAJO", None, "ALTO", "MEDIO", "BAJO"]
    for estado, nivel in zip(ESTADOS_CITA, niveles):
        cita = datos.cita(estado_actual=estado)
        if nivel:
            datos.pred(cita, nivel)
    r = datos.resumen()
    assert r.citas.total == 7
    assert all(v == 1 for v in r.citas.por_estado.values())
    assert r.citas.por_riesgo == {"ALTO": 2, "MEDIO": 2, "BAJO": 2, "SIN_PREDICCION": 1}


def test_relaciones_no_multiplican_y_estados_intervencion_no_acumulan(datos):
    c = datos.cita()
    datos.pred(c, "ALTO")
    datos.pred(c, "BAJO", fecha_hora_inferencia=AHORA)
    for estado in ESTADOS_INTERVENCION:
        datos.inter(c, estado)
    r = datos.resumen()
    assert r.citas.total == r.intervenciones.citas_con_intervencion == 1
    assert r.citas.por_riesgo["BAJO"] == 1
    assert r.intervenciones.total == 5
    assert all(v == 1 for v in r.intervenciones.por_estado.values())


def test_cupos_disponibilidad_y_recuperacion(datos, usuarios):
    for estado in ESTADOS_CUPO:
        cupo = datos.cupo(estado)
        if estado == "REASIGNADO":
            datos.reasignar(cupo, usuarios["RECEPCION"])
    datos.cupo(fecha_hora_cupo=AHORA - timedelta(hours=1))
    r = datos.resumen()
    assert r.cupos.total_liberados == 5
    assert r.cupos.por_estado["DISPONIBLE"] == 2
    assert r.cupos.disponibles_para_ofrecer == 1
    assert r.cupos.ofertas_en_curso == r.pendientes.ofertas_en_curso == 1
    assert r.cupos.reasignados_confirmados == 1
    assert r.cupos.tasa_recuperacion_pct == 20


@pytest.mark.parametrize(("n", "confirmados", "tasa"), [(3, 1, 33.33), (4, 2, 50), (1, 0, 0), (1, 1, 100)])
def test_porcentaje(datos, usuarios, n, confirmados, tasa):
    for i in range(n):
        cupo = datos.cupo("REASIGNADO" if i < confirmados else "DISPONIBLE")
        if i < confirmados:
            datos.reasignar(cupo, usuarios["RECEPCION"])
    assert datos.resumen().cupos.tasa_recuperacion_pct == tasa


@pytest.mark.parametrize("estado", ["DISPONIBLE", "EN_OFERTA", "REASIGNADO"])
def test_confirmacion_es_fuente_de_recuperacion_sin_reparar_estado(datos, usuarios, estado):
    cupo = datos.cupo(estado)
    datos.reasignar(cupo, usuarios["ADMINISTRADOR"])
    r = datos.resumen()
    assert r.cupos.reasignados_confirmados == 1
    assert r.cupos.disponibles_para_ofrecer == r.cupos.ofertas_en_curso == 0
    assert r.cupos.por_estado[estado] == 1
    assert cupo.estado_cupo == estado


def test_estado_reasignado_sin_confirmacion_no_acredita_recuperacion(datos):
    datos.cupo("REASIGNADO")
    assert datos.resumen().cupos.reasignados_confirmados == 0


def test_especialidad_y_fecha_programada_no_fecha_evento(datos):
    c = datos.cita(especialidad="PEDIATRIA")
    datos.pred(c)
    datos.inter(c, "RESPONDIDA", fecha_hora_respuesta=AHORA - timedelta(days=1))
    datos.cita(fecha_hora_cita=AHORA + timedelta(days=1))
    datos.cita()
    datos.cupo(especialidad="PEDIATRIA")
    r = datos.resumen(especialidad="PEDIATRIA")
    assert r.citas.total == 1
    assert r.intervenciones.total == 1
    assert r.cupos.total_liberados == 1
    assert r.fecha == AHORA.date()


def test_limites_dia_lima_con_instantes_utc(datos):
    inicio = AHORA.replace(hour=0)
    for momento in [inicio - timedelta(microseconds=1), inicio,
                    inicio + timedelta(days=1) - timedelta(microseconds=1), inicio + timedelta(days=1)]:
        datos.cita(fecha_hora_cita=momento.astimezone(timezone.utc))
        datos.cupo(fecha_hora_cupo=momento.astimezone(timezone.utc))
    assert datos.resumen().citas.total == 6  # dos citas seleccionadas + cuatro orígenes de cupo del día
    assert datos.resumen().cupos.total_liberados == 2


def test_reloj_utc_fecha_por_defecto_es_lima():
    ahora = AHORA.replace(hour=2, tzinfo=timezone.utc)
    ctx, inicio, fin = contexto(None, None, ahora)
    assert ctx["fecha"] == date(2026, 11, 8)
    assert inicio.hour == fin.hour == 0
    assert fin - inicio == timedelta(days=1)
    with pytest.raises(ValueError, match="zona horaria"):
        contexto(None, None, ahora.replace(tzinfo=None))


def test_estado_actual_de_jornada_pasada(datos):
    c = datos.cita(fecha_hora_cita=AHORA - timedelta(days=1), estado_actual="ATENDIDA")
    datos.pred(c)
    r = datos.resumen(fecha=(AHORA - timedelta(days=1)).date())
    assert r.citas.total == r.citas.por_estado["ATENDIDA"] == 1
    assert r.pendientes.citas_sin_intervencion == 0


def test_una_sentencia_solo_lectura_sin_n_mas_uno(datos, db, sentencias, monkeypatch):
    monkeypatch.setattr(db, "commit", lambda: pytest.fail("No debe hacer commit"))
    r1 = datos.resumen()
    assert len(sentencias) == 1
    sentencias.clear()
    for _ in range(30):
        c = datos.cita()
        datos.pred(c)
        datos.inter(c)
    sentencias.clear()
    r2 = datos.resumen()
    assert len(sentencias) == 1
    assert sentencias[0].lstrip().upper().startswith("WITH")
    assert "FOR UPDATE" not in sentencias[0].upper()
    assert r1.citas.total == 0 and r2.citas.total == 30
