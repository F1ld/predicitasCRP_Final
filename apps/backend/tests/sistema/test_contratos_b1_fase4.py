"""B.1: límites reales y rechazo sin efectos; no requiere BD."""
import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import inspect

from app.core.errores import NoEncontrado, TransicionInvalida
from app.modules.citas import public as citas
from app.modules.citas.models import Cita
from app.modules.intervenciones import public as intervenciones
from app.modules.intervenciones.models import Intervencion
from app.modules.lista_espera import public as lista
from app.modules.lista_espera.models import CupoLiberado
from tests.sistema.test_limites_flujos_fase4 import _usuario_prueba

APP = Path(__file__).resolve().parents[2] / "app"


def cita_ejemplo():
    return Cita(id_cita=123, id_cita_externa="CIT-B1", paciente_anon_id="PAC-B1", especialidad="PEDIATRIA",
                medico="Prueba", fecha_hora_cita=datetime(2026, 11, 10, tzinfo=timezone.utc),
                estado_actual="RECIBIDA", franja_horaria="MANANA")


@pytest.mark.parametrize("operacion", [citas.transicionar_cita_interno, citas.transicionar])
def test_reprogramar_sin_fecha_no_muta_ni_escribe(operacion):
    db = MagicMock()
    row = cita_ejemplo()
    db.get.return_value = row
    fecha = row.fecha_hora_cita
    with pytest.raises(TransicionInvalida, match="nueva_fecha_hora_cita"):
        operacion(db, row.id_cita, "REPROGRAMADA", usuario=_usuario_prueba(), ip="127.0.0.1")
    assert row.estado_actual == "RECIBIDA" and row.fecha_hora_cita == fecha
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_transicion_por_id_retorna_snapshot_y_conserva_lock():
    db = MagicMock()
    row = cita_ejemplo()
    db.get.return_value = row
    result = citas.transicionar_cita_interno(db, 123, "CONFIRMADA", usuario=_usuario_prueba(), ip="127.0.0.1")
    db.get.assert_called_once_with(Cita, 123, with_for_update=True, populate_existing=True)
    assert inspect(result, raiseerr=False) is None
    assert result.estado_actual == row.estado_actual == "CONFIRMADA"
    with pytest.raises(FrozenInstanceError):
        result.estado_actual = "LIBERADA"
    db.commit.assert_not_called()


def test_transicion_inexistente_no_escribe():
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(NoEncontrado):
        citas.transicionar_cita_interno(db, 999, "CONFIRMADA", usuario=_usuario_prueba(), ip="127.0.0.1")
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_consulta_cupo_realmente_devuelve_snapshot():
    db = MagicMock()
    db.scalar.return_value = CupoLiberado(id_cupo_liberado=1, id_cita_origen=123, especialidad="PEDIATRIA", medico="Prueba",
                                        fecha_hora_cupo=datetime.now(timezone.utc), estado_cupo="DISPONIBLE",
                                        origen_liberacion="INTERVENCION_VOLUNTARIA")
    result = lista.obtener_cupo_por_cita_origen(db, 123)
    assert isinstance(result, lista.CupoLiberadoSnapshot) and inspect(result, raiseerr=False) is None
    with pytest.raises(FrozenInstanceError):
        result.estado_cupo = "REASIGNADO"


def test_validacion_intervencion_usa_snapshot_sin_exponer_orm():
    db = MagicMock()
    db.get.return_value = Intervencion(id_intervencion=4, id_cita=123, canal_contacto="SMS",
                                      estado_intervencion="RESPONDIDA", consentimiento_optout=False)
    result = intervenciones.obtener_intervencion_snapshot(db, 4)
    assert inspect(result, raiseerr=False) is None and result.id_cita == 123
    assert intervenciones.validar_intervencion_de_cita(db, 4, 123)
    assert not intervenciones.validar_intervencion_de_cita(db, 4, 999)
    with pytest.raises(FrozenInstanceError):
        result.estado_intervencion = "ENVIADA"


def test_cupo_generado_es_snapshot_y_no_permite_id_auditoria_nulo():
    db = MagicMock()
    def flush():
        for call in db.add.call_args_list:
            if isinstance(call.args[0], CupoLiberado):
                call.args[0].id_cupo_liberado = 456
    db.flush.side_effect = flush
    result = lista.crear_cupo_liberado_interno(
        db, id_cita_origen=123, especialidad="PEDIATRIA", medico="Prueba", fecha_hora_cupo=datetime.now(timezone.utc),
        origen_liberacion="INTERVENCION_VOLUNTARIA", usuario=_usuario_prueba(), ip="127.0.0.1",
        datos_after_extra={"id_cupo_liberado": None})
    assert isinstance(result, lista.CupoLiberadoSnapshot) and inspect(result, raiseerr=False) is None
    event = db.add.call_args_list[-1].args[0]
    assert event.id_entidad == event.datos_after["id_cupo_liberado"] == 456
    db.commit.assert_not_called()


@pytest.mark.parametrize("modulo", ["citas", "intervenciones", "lista_espera"])
def test_servicios_b1_no_importan_modelos_o_reglas_privados_ajenos(modulo):
    tree = ast.parse((APP / "modules" / modulo / "service.py").read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        paths = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
        if isinstance(node, ast.ImportFrom):
            paths = [f"{node.module}.{alias.name}" for alias in node.names]
        for path in paths:
            parts = path.split(".")
            if len(parts) > 3 and parts[:2] == ["app", "modules"] and parts[2] != modulo:
                assert parts[3] not in {"models", "reglas", "repository"}, path


def test_public_cupos_no_expone_fabrica_privada():
    import inspect as firma
    assert "fabrica_cupo" not in firma.signature(lista.crear_cupo_liberado_interno).parameters
