"""Fallos tras flush en coordinadores reales; observación por otra conexión."""
import json
from pathlib import Path
import secrets
import sys
from unittest.mock import patch
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.citas import importer, service as citas
from app.modules.citas.models import Cita, HistorialEstadoCita
from app.modules.citas.schemas import CambioEstadoIn
from app.modules.intervenciones import service as intervenciones
from app.modules.intervenciones.models import Intervencion
from app.modules.intervenciones.schemas import IntervencionRespuestaIn
from app.modules.lista_espera import casos, service as espera
from app.modules.lista_espera.schemas import ReasignacionIn
from app.modules.usuarios.models import Usuario
from app.workflows import citas as wc, intervenciones as wi
from probar_concurrencia_d import NOW, escenario, observar


def snapshot(ids):
    with Session(engine) as db:
        return {**observar(ids), "auditorias_totales": db.scalar(select(func.count()).select_from(AuditoriaEvento)),
            "historiales_totales": db.scalar(select(func.count()).select_from(HistorialEstadoCita)),
            "citas_totales": db.scalar(select(func.count()).select_from(Cita)),
            "estados_citas": [db.get(Cita, i).estado_actual for i in ids["citas"]],
            "respuestas": [(db.get(Intervencion, i).estado_intervencion, db.get(Intervencion, i).respuesta_paciente,
                str(db.get(Intervencion, i).fecha_hora_respuesta)) for i in ids["intervenciones"]]}


def main():
    url = urlsplit(get_settings().database_url)
    if not (url.hostname or "").startswith("predicitas-fase4-") or url.path != "/predicitas_fase4_test":
        raise SystemExit("Solo laboratorio D aislado")
    target = Path(sys.argv[1])
    if target.exists():
        raise SystemExit("No sobrescribir evidencia")
    with Session(engine) as db:
        user = Usuario(nombre_completo="QA rollback D", correo_institucional=f"rd-{secrets.token_hex(8)}@example.invalid",
                       password_hash="NO-LOGIN-QA-D", rol="RECEPCION")
        db.add(user)
        db.commit()
        actor_id = user.id_usuario
    results = {}
    class FalloSimulado(RuntimeError):
        pass
    for name, tipo, modulo, accion in (("cancelacion", "cancelar_liberar", wc, "LIBERAR"),
        ("respuesta_legacy", "cancelar_liberar", wi, "LIBERAR"),
        ("reasignacion", "reasignar_cupo", casos, "REASIGNAR"), ("importacion", "responder", importer, "IMPORT")):
        ids = escenario(actor_id, tipo)
        before, reached = snapshot(ids), []
        original = modulo.registrar_evento
        def fallar(db, **kwargs):
            event = original(db, **kwargs)
            if kwargs["accion"] == accion:
                db.flush()
                reached.append(True)
                raise FalloSimulado("D después del flush")
            return event
        with Session(engine) as db:
            user = db.get(Usuario, actor_id)
            with patch.object(modulo, "registrar_evento", fallar):
                try:
                    if name == "cancelacion":
                        citas.cambiar_estado(db, ids["citas"][0], CambioEstadoIn(estado_nuevo="CANCELADA", liberar_cupo=True), user, "127.0.0.1", NOW)
                    elif name == "respuesta_legacy":
                        intervenciones.registrar_respuesta_intervencion(db, ids["intervenciones"][0],
                            IntervencionRespuestaIn(respuesta_paciente="SOLICITA_LIBERACION"), usuario=user,
                            ip="127.0.0.1", cambiar_cita=True, validar_transicion=False)
                    elif name == "reasignacion":
                        espera.reasignar_cupo(db, ids["cupos"][0], ReasignacionIn(id_candidato=ids["candidatos"][0],
                            confirmacion_humana=True), usuario=user, ip="127.0.0.1")
                    else:
                        importer.importar_citas(db, [{"id_cita_externa": "CIT-D-ROLL-" + secrets.token_hex(6),
                            "paciente_anon_id": "PAC-D-ROLL", "sede": "SAN_ISIDRO", "especialidad": "CARDIOLOGIA",
                            "medico": "QA D", "fecha_hora_cita": "2026-11-10T09:00:00-05:00",
                            "fecha_registro_cita": "2026-11-01T09:00:00-05:00", "tipo_paciente": "NUEVO", "canal_origen": "WEB"}],
                            id_usuario=actor_id, ip="127.0.0.1", origen="QA rollback D", ahora=NOW)
                except FalloSimulado:
                    db.rollback()
                else:
                    raise AssertionError("No se indujo el fallo")
        after = snapshot(ids)
        assert reached and before == after
        results[name] = {"failure_after_flush": True, "independent_connection_rollback": True,
                         "before": before, "after": after}
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"checks": results, "scope": "Datos QA conservados solo en laboratorio nuevo"}, stream, indent=2)
        stream.write("\n")
    print("Rollback D: cuatro coordinadores tras flush, sin mutaciones parciales: PASÓ")


if __name__ == "__main__":
    main()
