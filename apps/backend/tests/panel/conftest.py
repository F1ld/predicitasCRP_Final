"""Datos sintéticos de Panel; requiere explícitamente una base de pruebas."""
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import event

from app.core.database import engine
from app.core.reloj import LIMA, reloj
from app.main import app
from app.modules.citas.models import Cita
from app.modules.ia.models import PrediccionIA
from app.modules.intervenciones.models import Intervencion
from app.modules.lista_espera.models import CupoLiberado, ListaEspera, Reasignacion
from app.modules.panel import service

AHORA = datetime(2026, 11, 9, 9, tzinfo=LIMA)


@pytest.fixture(scope="session", autouse=True)
def solo_base_pruebas():
    if "test" not in (engine.url.database or "").lower():
        pytest.fail("Panel requiere DATABASE_URL de pruebas (nombre con 'test'); no usar la base operativa")


@pytest.fixture
def datos(db):
    class Datos:
        secuencia = count(1)

        def cita(self, **cambios):
            n = next(self.secuencia)
            campos = dict(id_cita_externa=f"PAN-{n}", paciente_anon_id=f"PAC-PAN-{n}",
                sede="SAN_ISIDRO", especialidad="CARDIOLOGIA", medico="Medico sintetico",
                fecha_hora_cita=AHORA + timedelta(hours=5), fecha_registro_cita=AHORA - timedelta(days=7),
                antelacion_dias=7, tipo_paciente="NUEVO", canal_origen="WEB", franja_horaria="TARDE",
                dia_semana="LUNES", estado_actual="RECIBIDA")
            obj = Cita(**(campos | cambios))
            db.add(obj)
            db.flush()
            return obj

        def pred(self, cita, nivel="ALTO", **cambios):
            campos = dict(id_cita=cita.id_cita, version_modelo=f"PAN-{next(self.secuencia)}",
                probabilidad_no_show=Decimal({"ALTO": "0.7", "MEDIO": "0.4", "BAJO": "0.1"}[nivel]),
                nivel_riesgo=nivel, umbral_aplicado=Decimal("0.450"), features_snapshot={},
                fecha_hora_inferencia=AHORA - timedelta(days=1))
            obj = PrediccionIA(**(campos | cambios))
            db.add(obj)
            db.flush()
            return obj

        def inter(self, cita, estado="ENVIADA", **cambios):
            campos = dict(id_cita=cita.id_cita, canal_contacto="WHATSAPP",
                plantilla_mensaje="RECORDATORIO_CONFIRMACION_V1", estado_intervencion=estado,
                fecha_hora_envio=AHORA - timedelta(days=2))
            obj = Intervencion(**(campos | cambios))
            db.add(obj)
            db.flush()
            return obj

        def cupo(self, estado="DISPONIBLE", **cambios):
            cita = self.cita()
            campos = dict(id_cita_origen=cita.id_cita, especialidad=cita.especialidad,
                medico=cita.medico, fecha_hora_cupo=cita.fecha_hora_cita, estado_cupo=estado,
                origen_liberacion="CANCELACION_EXTERNA", liberado_en=AHORA - timedelta(days=2))
            obj = CupoLiberado(**(campos | cambios))
            db.add(obj)
            db.flush()
            return obj

        def reasignar(self, cupo, operador):
            candidato = ListaEspera(paciente_anon_id=f"CAN-PAN-{next(self.secuencia)}",
                especialidad_req=cupo.especialidad, franja_preferida="INDIFERENTE", estado_candidato="ASIGNADO")
            db.add(candidato)
            db.flush()
            obj = Reasignacion(id_cupo_liberado=cupo.id_cupo_liberado, id_candidato=candidato.id_candidato,
                id_operador_confirma=operador.id_usuario, confirmacion_humana=True,
                medio_confirmacion="LLAMADA_CONFIRMADA", fecha_hora_reasigna=AHORA - timedelta(days=1))
            db.add(obj)
            db.flush()
            return obj

        def resumen(self, **cambios):
            return service.obtener_resumen(db, **(dict(fecha=AHORA.date(), especialidad=None, ahora=AHORA) | cambios))

        def lista(self, tipo="CITAS_SIN_INTERVENCION", **cambios):
            return service.listar_pendientes(db, **(dict(fecha=AHORA.date(), especialidad=None,
                ahora=AHORA, tipo=tipo, limite=20, desplazamiento=0) | cambios))

    return Datos()


@pytest.fixture
def sentencias(db):
    sql = []
    conexion = db.connection()
    def registrar(conn, cursor, statement, parameters, context, executemany):
        sql.append(statement)
    event.listen(conexion, "before_cursor_execute", registrar)
    yield sql
    event.remove(conexion, "before_cursor_execute", registrar)


@pytest.fixture
def reloj_panel():
    app.dependency_overrides[reloj] = lambda: AHORA
    yield AHORA
    app.dependency_overrides.pop(reloj, None)
