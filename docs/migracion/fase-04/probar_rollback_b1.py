"""Prueba destructiva solo sobre datos sintéticos NUEVOS del laboratorio B.1.

No borra datos: conserva el escenario fallido en el volumen nuevo de pruebas.
No usar fuera del harness; exige host fase4, BD test y rol operativo.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import sys
from unittest.mock import patch
from urllib.parse import urlsplit

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.citas.importer import importar_citas
from app.modules.citas.models import Cita, HistorialEstadoCita
from app.modules.intervenciones import service
from app.modules.intervenciones.models import Intervencion
from app.modules.intervenciones.schemas import IntervencionRespuestaIn
from app.modules.lista_espera.models import CupoLiberado
from app.modules.usuarios.models import Usuario


def observar(id_cita, id_inter):
    # Una conexión distinta y transacción nueva: no usa el identity map del fallo.
    with Session(engine) as db:
        return {"estado_cita": db.get(Cita, id_cita).estado_actual,
                "estado_intervencion": db.get(Intervencion, id_inter).estado_intervencion,
                "cupos": db.scalar(select(func.count()).select_from(CupoLiberado).where(CupoLiberado.id_cita_origen == id_cita)),
                "historiales": db.scalar(select(func.count()).select_from(HistorialEstadoCita).where(HistorialEstadoCita.id_cita == id_cita)),
                "auditorias": db.scalar(select(func.count()).select_from(AuditoriaEvento))}


def main():
    url = urlsplit(get_settings().database_url)
    if not (url.hostname or "").startswith("predicitas-fase4-") or url.path != "/predicitas_fase4_test":
        raise SystemExit("Solo laboratorio fase4_test aislado")
    target = Path(sys.argv[1])
    if target.exists():
        raise SystemExit("No sobrescribir evidencia B.1")
    marca = secrets.token_hex(6)
    with Session(engine) as db:
        assert db.scalar(text("SELECT current_user")) == "predicitas_app"
        user = Usuario(nombre_completo="QA B1 sintético", correo_institucional=f"b1-{marca}@example.invalid",
                       password_hash="NO-LOGIN-QA-B1", rol="RECEPCION")
        db.add(user)
        db.flush()
        datos = {"id_cita_externa": f"CIT-B1-{marca}", "paciente_anon_id": f"PAC-B1-{marca}",
                 "sede": "SAN_ISIDRO", "especialidad": "CARDIOLOGIA", "medico": "QA sintético",
                 "fecha_hora_cita": "2026-11-10T09:00:00-05:00", "fecha_registro_cita": "2026-11-01T09:00:00-05:00",
                 "tipo_paciente": "NUEVO", "canal_origen": "WEB"}
        result = importar_citas(db, [datos], id_usuario=user.id_usuario, ip="127.0.0.1", origen="QA B1",
                               ahora=datetime(2026, 11, 5, tzinfo=timezone.utc))
        assert result.aceptadas == 1
        cita = db.scalar(select(Cita).where(Cita.id_cita_externa == datos["id_cita_externa"]))
        inter = Intervencion(id_cita=cita.id_cita, id_operador=user.id_usuario, canal_contacto="SMS",
                             plantilla_mensaje="RECORDATORIO_CONFIRMACION_V1", estado_intervencion="PENDIENTE",
                             consentimiento_optout=False)
        db.add(inter)
        db.commit()
        id_cita, id_inter, id_user = cita.id_cita, inter.id_intervencion, user.id_usuario
    before = observar(id_cita, id_inter)
    reached = []
    original = service.registrar_evento
    class FalloSimulado(RuntimeError):
        pass
    def fallar(db, **kwargs):
        if kwargs["accion"] == "LIBERAR":
            # El cupo ya se insertó con flush dentro de la transacción no confirmada.
            assert db.scalar(select(CupoLiberado).where(CupoLiberado.id_cita_origen == id_cita)) is not None
            reached.append(True)
            raise FalloSimulado("B1 tras flush")
        return original(db, **kwargs)
    with Session(engine) as db:
        user = db.get(Usuario, id_user)
        with patch.object(service, "registrar_evento", fallar):
            try:
                service.registrar_respuesta_intervencion(db, id_inter,
                    IntervencionRespuestaIn(respuesta_paciente="SOLICITA_LIBERACION"), usuario=user,
                    ip="127.0.0.1", cambiar_cita=True, validar_transicion=False)
            except FalloSimulado:
                db.rollback()
            else:
                raise AssertionError("No se indujo el fallo después del flush")
    after = observar(id_cita, id_inter)
    assert reached and before == after
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"failure_after_cupo_flush": True, "rollback_visible_from_independent_connection": True,
                   "before": before, "after": after, "runtime_role": "predicitas_app",
                   "scope": "Escenario sintético conservado solo en laboratorio nuevo; no prueba concurrencia"}, stream, indent=2)
        stream.write("\n")
    print("Rollback B.1 de cita, intervención, cupo, historial y auditoría: PASÓ entre conexiones independientes")


if __name__ == "__main__":
    main()
