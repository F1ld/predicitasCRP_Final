"""Pruebas de límites de arquitectura y workflows para Fase 4 - Bloque B.

Verifica:
1. Contratos públicos de Citas, Intervenciones y Lista de Espera.
2. Invariante de DTOs inmutables para desacoplar modelos ORM.
3. Operaciones componibles sin commit prematuro (RNF-014).
4. Unicidad de HistorialEstadoCita por transición legal.
5. Ausencia de imports ORM cruzados prohibidos entre servicios de negocio.
"""
import ast
from dataclasses import FrozenInstanceError, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.modules.auditoria.models import AuditoriaEvento
from app.modules.auth.public import Principal
from app.modules.citas import public as citas_public
from app.modules.citas.models import Cita, HistorialEstadoCita
from app.modules.intervenciones import public as intervenciones_public
from app.modules.lista_espera import public as lista_espera_public
from app.modules.lista_espera.models import CupoLiberado

APP = Path(__file__).resolve().parents[2] / "app"


def imports_de_modulo(archivo_path: Path):
    """Extrae imports directos y 'from ... import' del archivo."""
    tree = ast.parse(archivo_path.read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                yield f"{mod}.{alias.name}"


# ---------------------------------------------------------------- AST & Límites

def test_citas_service_no_importa_modelos_de_otros_modulos():
    citas_service_file = APP / "modules" / "citas" / "service.py"
    imported = set(imports_de_modulo(citas_service_file))
    
    # Prohibido importar modelos ORM de intervenciones o lista de espera
    assert "app.modules.intervenciones.models.Intervencion" not in imported
    assert "app.modules.lista_espera.models.CupoLiberado" not in imported


def test_lista_espera_service_no_importa_citas_privado():
    le_service_file = APP / "modules" / "lista_espera" / "service.py"
    imported = set(imports_de_modulo(le_service_file))
    
    # Prohibido importar modelos o reglas internas de citas
    assert "app.modules.citas.models.Cita" not in imported
    assert "app.modules.citas.reglas.LIMA" not in imported


def test_intervenciones_service_no_importa_historial_estado_cita():
    int_service_file = APP / "modules" / "intervenciones" / "service.py"
    imported = set(imports_de_modulo(int_service_file))
    
    # La creación de historial de estado pertenece exclusivamente a Citas
    assert "app.modules.citas.models.HistorialEstadoCita" not in imported


# ---------------------------------------------------------------- DTOs y Contratos

def test_contrato_citas_consulta_es_dataclass_inmutable():
    assert is_dataclass(citas_public.CitaConsulta)
    dto = citas_public.CitaConsulta(
        id_cita=101,
        id_cita_externa="CIT-101",
        paciente_anon_id="PAC-1",
        especialidad="CARDIOLOGIA",
        medico="Dr. Test",
        fecha_hora_cita=datetime.now(timezone.utc),
        estado_actual="RECIBIDA",
        franja_horaria="MANANA",
    )
    with pytest.raises(FrozenInstanceError):
        dto.estado_actual = "CONFIRMADA"


def test_contrato_cupo_liberado_snapshot_es_inmutable():
    assert is_dataclass(lista_espera_public.CupoLiberadoSnapshot)
    dto = lista_espera_public.CupoLiberadoSnapshot(
        id_cupo_liberado=201,
        id_cita_origen=101,
        especialidad="CARDIOLOGIA",
        medico="Dr. Test",
        fecha_hora_cupo=datetime.now(timezone.utc),
        estado_cupo="DISPONIBLE",
        origen_liberacion="CANCELACION_EXTERNA",
        liberado_en=datetime.now(timezone.utc),
    )
    with pytest.raises(FrozenInstanceError):
        dto.estado_cupo = "REASIGNADO"


def test_contrato_intervencion_snapshot_es_inmutable():
    assert is_dataclass(intervenciones_public.IntervencionSnapshot)
    dto = intervenciones_public.IntervencionSnapshot(
        id_intervencion=301,
        id_cita=101,
        canal_contacto="WHATSAPP",
        estado_intervencion="PENDIENTE",
        respuesta_paciente=None,
        consentimiento_optout=False,
        fecha_hora_envio=None,
        fecha_hora_respuesta=None,
    )
    with pytest.raises(FrozenInstanceError):
        dto.estado_intervencion = "ENVIADA"


# ---------------------------------------------------------------- Semántica Transaccional Componible

def _usuario_prueba() -> Principal:
    ahora = datetime.now(timezone.utc)
    return Principal(
        id_usuario=99,
        nombre_completo="Admin Test",
        correo_institucional="admin@crp.pe",
        rol="ADMINISTRADOR",
        activo=True,
        creado_en=ahora,
        actualizado_en=ahora,
    )


def test_transicionar_cita_interno_no_hace_commit_y_agrega_un_solo_historial():
    """RNF-014: transicionar_cita_interno debe ser componible y NO hacer commit."""
    mock_db = MagicMock()
    mock_db.commit = MagicMock()

    cita_mock = Cita(
        id_cita=123,
        id_cita_externa="CIT-123",
        paciente_anon_id="PAC-123",
        sede="SAN_ISIDRO",
        especialidad="PEDIATRIA",
        medico="Dra. Test",
        fecha_hora_cita=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        fecha_registro_cita=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
        tipo_paciente="NUEVO",
        canal_origen="WEB",
        estado_actual="RECIBIDA",
        antelacion_dias=40,
        franja_horaria="MANANA",
        dia_semana="MARTES",
    )
    mock_db.get.return_value = cita_mock
    usuario = _usuario_prueba()
    
    resultado = citas_public.transicionar_cita_interno(
        mock_db,
        cita_mock.id_cita,
        "CONFIRMADA",
        usuario=usuario,
        ip="127.0.0.1",
        motivo="Prueba de composabilidad",
        registrar_auditoria=False,
    )

    # 1. No debe haber llamado a commit()
    mock_db.commit.assert_not_called()

    # 2. Debe haber agregado exactamente una fila de HistorialEstadoCita
    llamadas_add = [call[0][0] for call in mock_db.add.call_args_list]
    historiales = [item for item in llamadas_add if isinstance(item, HistorialEstadoCita)]
    assert len(historiales) == 1
    assert historiales[0].estado_anterior == "RECIBIDA"
    assert historiales[0].estado_nuevo == "CONFIRMADA"
    assert resultado.estado_actual == "CONFIRMADA"


def test_crear_cupo_liberado_interno_no_hace_commit():
    """RNF-014: crear_cupo_liberado_interno debe ser componible y NO hacer commit."""
    mock_db = MagicMock()
    mock_db.commit = MagicMock()
    usuario = _usuario_prueba()
    
    cupo = lista_espera_public.crear_cupo_liberado_interno(
        mock_db,
        id_cita_origen=123,
        especialidad="PEDIATRIA",
        medico="Dra. Test",
        fecha_hora_cupo=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        origen_liberacion="CANCELACION_EXTERNA",
        usuario=usuario,
        ip="127.0.0.1",
        modulo_auditoria="REASIGNACION",
    )

    # 1. No debe haber llamado a commit()
    mock_db.commit.assert_not_called()

    # 2. Debe haber agregado el cupo liberado y el evento de auditoría
    llamadas_add = [call[0][0] for call in mock_db.add.call_args_list]
    cupos = [item for item in llamadas_add if isinstance(item, CupoLiberado)]
    auditorias = [item for item in llamadas_add if isinstance(item, AuditoriaEvento)]
    assert len(cupos) == 1
    assert len(auditorias) == 1
    mock_db.flush.assert_called_once()
    assert cupo.estado_cupo == "DISPONIBLE"
    assert cupo.origen_liberacion == "CANCELACION_EXTERNA"
