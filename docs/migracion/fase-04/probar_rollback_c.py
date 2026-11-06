"""Rollback real de ofertas/cierres/exportación en laboratorio C nuevo y aislado."""
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
from app.modules.citas.models import Cita
from app.modules.lista_espera import public, service
from app.modules.lista_espera.models import CupoLiberado, ListaEspera
from app.modules.reportes import service as reportes
from app.modules.usuarios.models import Usuario


def observar(id_cupo, id_candidato):
    with Session(engine) as db:
        return {"estado_cupo": db.get(CupoLiberado, id_cupo).estado_cupo,
                "estado_candidato": db.get(ListaEspera, id_candidato).estado_candidato,
                "auditorias": db.scalar(select(func.count()).select_from(AuditoriaEvento))}


def main():
    url = urlsplit(get_settings().database_url)
    if not (url.hostname or "").startswith("predicitas-fase4-") or url.path != "/predicitas_fase4_test":
        raise SystemExit("Solo laboratorio fase4_test aislado")
    target = Path(sys.argv[1])
    if target.exists():
        raise SystemExit("No sobrescribir evidencia C")
    marca = secrets.token_hex(6)
    with Session(engine) as db:
        assert db.scalar(text("SELECT current_user")) == "predicitas_app"
        actor = Usuario(nombre_completo="QA C sintético", correo_institucional=f"c-{marca}@example.invalid",
                        password_hash="NO-LOGIN-QA-C", rol="RECEPCION")
        db.add(actor)
        db.flush()
        data = {"id_cita_externa": f"CIT-C-{marca}", "paciente_anon_id": f"PAC-C-{marca}",
                "sede": "SAN_ISIDRO", "especialidad": "CARDIOLOGIA", "medico": "QA sintético",
                "fecha_hora_cita": "2026-11-10T09:00:00-05:00", "fecha_registro_cita": "2026-11-01T09:00:00-05:00",
                "tipo_paciente": "NUEVO", "canal_origen": "WEB"}
        assert importar_citas(db, [data], id_usuario=actor.id_usuario, ip="127.0.0.1", origen="QA C",
            ahora=datetime(2026, 11, 6, tzinfo=timezone.utc)).aceptadas == 1
        cita = db.scalar(select(Cita).where(Cita.id_cita_externa == data["id_cita_externa"]))
        cupo = public.crear_cupo_liberado_interno(db, id_cita_origen=cita.id_cita,
            especialidad=cita.especialidad, medico=cita.medico, fecha_hora_cupo=cita.fecha_hora_cita,
            origen_liberacion="CANCELACION_EXTERNA", usuario=actor, ip="127.0.0.1")
        candidato = ListaEspera(paciente_anon_id=f"PAC-CAND-{marca}", especialidad_req="CARDIOLOGIA",
                               franja_preferida="MANANA", estado_candidato="ACTIVO")
        db.add(candidato)
        db.commit()
        id_cupo, id_candidato, id_actor = cupo.id_cupo_liberado, candidato.id_candidato, actor.id_usuario
    results = {}
    class FalloSimulado(RuntimeError):
        pass
    for operacion, modulo, accion in (("oferta", service, "OFERTAR"), ("cierre", service, "DESISTIR"),
                                      ("exportacion", reportes, "EXPORT")):
        if operacion == "cierre":
            with Session(engine) as db:
                service.registrar_oferta(db, id_cupo, id_candidato, usuario=db.get(Usuario, id_actor), ip="127.0.0.1")
        before = observar(id_cupo, id_candidato)
        original = modulo.registrar_evento
        reached = []
        def fallar(db, **kwargs):
            event = original(db, **kwargs)
            if kwargs["accion"] == accion:
                db.flush()  # estados y evento insertados, pero aún sin commit
                reached.append(True)
                raise FalloSimulado("C después de flush")
            return event
        with Session(engine) as db:
            actor = db.get(Usuario, id_actor)
            with patch.object(modulo, "registrar_evento", fallar):
                try:
                    if operacion == "oferta":
                        service.registrar_oferta(db, id_cupo, id_candidato, usuario=actor, ip="127.0.0.1")
                    elif operacion == "cierre":
                        service.cerrar_oferta(db, id_cupo, cierre="SIN_RESPUESTA", usuario=actor, ip="127.0.0.1")
                    else:
                        reportes.preparar_rep02(db, usuario=actor, ip="127.0.0.1", formato="csv")
                except FalloSimulado:
                    db.rollback()
                else:
                    raise AssertionError("No se alcanzó el fallo inducido")
        after = observar(id_cupo, id_candidato)
        assert reached and before == after
        results[operacion] = {"failure_after_flush": True, "independent_connection_rollback": True,
                              "before": before, "after": after}
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"checks": results, "runtime_role": "predicitas_app",
                   "scope": "Datos QA solo en volumen nuevo; no es prueba concurrente"}, stream, indent=2)
        stream.write("\n")
    print("Rollback C de oferta, cierre y exportación: PASÓ entre conexiones independientes")


if __name__ == "__main__":
    main()
