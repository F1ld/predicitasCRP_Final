"""HTTP concurrente real + PostgreSQL: filas precargadas y espera observada.

Solo laboratorio nuevo fase4_test. No borra escenarios; no modifica originales.
Se ejecuta también contra /app empaquetado, sin montar las fuentes del backend.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import secrets
import sys
import threading
import time
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine, get_db
from app.core.reloj import LIMA, reloj
from app.core.security import hash_password
from app.main import app
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.citas.importer import importar_citas
from app.modules.citas.models import Cita, HistorialEstadoCita
from app.modules.citas.public import transicionar_cita_interno
from app.modules.ia.models import PrediccionIA
from app.modules.intervenciones.models import Intervencion
from app.modules.intervenciones.router import modo_sombra
from app.modules.lista_espera.models import CupoLiberado, ListaEspera, Reasignacion
from app.modules.lista_espera.public import crear_cupo_liberado_interno
from app.modules.lista_espera.service import registrar_oferta
from app.modules.usuarios.models import Usuario

NOW = datetime(2026, 11, 6, 8, tzinfo=LIMA)


def escenario(actor_id, tipo):
    marca = secrets.token_hex(6)
    cids, cupids, iids, lids = [], [], [], []
    with Session(engine, expire_on_commit=False) as db:
        actor = db.get(Usuario, actor_id)
        for n in range(2 if tipo in ("reasignar_candidato", "ofertar_candidato") else 1):
            datos = {"id_cita_externa": f"CIT-D-{marca}-{n}", "paciente_anon_id": f"PAC-D-{marca}-{n}",
                "sede": "SAN_ISIDRO", "especialidad": "CARDIOLOGIA", "medico": "QA D sintético",
                "fecha_hora_cita": "2026-11-10T09:00:00-05:00", "fecha_registro_cita": "2026-11-01T09:00:00-05:00",
                "tipo_paciente": "NUEVO", "canal_origen": "WEB"}
            assert importar_citas(db, [datos], id_usuario=actor_id, ip="127.0.0.1", origen="QA concurrencia D", ahora=NOW).aceptadas == 1
            cita = db.scalar(select(Cita).where(Cita.id_cita_externa == datos["id_cita_externa"]))
            cids.append(cita.id_cita)
            if tipo.startswith(("ofertar", "reasignar")) or tipo == "cerrar":
                transicionar_cita_interno(db, cita.id_cita, "LIBERADA", usuario=actor, ip="127.0.0.1")
                cupo = crear_cupo_liberado_interno(db, id_cita_origen=cita.id_cita, especialidad=cita.especialidad,
                    medico=cita.medico, fecha_hora_cupo=cita.fecha_hora_cita, origen_liberacion="INTERVENCION_VOLUNTARIA",
                    usuario=actor, ip="127.0.0.1")
                cupids.append(cupo.id_cupo_liberado)
            if tipo == "crear_intervencion":
                db.add(PrediccionIA(id_cita=cita.id_cita, version_modelo="SIM_QA_D", probabilidad_no_show="0.8",
                    nivel_riesgo="ALTO", umbral_aplicado="0.45", features_snapshot={}))
        if tipo.startswith(("ofertar", "reasignar")) or tipo == "cerrar":
            for n in range(2 if tipo == "ofertar_cupo" else 1):
                candidato = ListaEspera(paciente_anon_id=f"PAC-D-CAND-{marca}-{n}", especialidad_req="CARDIOLOGIA",
                    franja_preferida="MANANA", estado_candidato="ACTIVO")
                db.add(candidato)
                db.flush()
                lids.append(candidato.id_candidato)
        if tipo in ("liberar", "cancelar_liberar", "responder"):
            for _ in range(2 if tipo == "liberar" else 1):
                inter = Intervencion(id_cita=cids[0], id_operador=actor_id, canal_contacto="SMS",
                    plantilla_mensaje="RECORDATORIO_CONFIRMACION_V1", consentimiento_optout=False,
                    estado_intervencion="ENTREGADA" if tipo == "responder" else "RESPONDIDA",
                    respuesta_paciente=None if tipo == "responder" else "SOLICITA_LIBERACION",
                    fecha_hora_envio=NOW - timedelta(hours=1))
                db.add(inter)
                db.flush()
                iids.append(inter.id_intervencion)
        db.commit()
        if tipo == "cerrar":
            registrar_oferta(db, cupids[0], lids[0], usuario=actor, ip="127.0.0.1")
    return {"citas": cids, "cupos": cupids, "intervenciones": iids, "candidatos": lids}


def observar(ids):
    with Session(engine) as db:
        cupos = list(db.scalars(select(CupoLiberado).where(CupoLiberado.id_cita_origen.in_(ids["citas"])).order_by(CupoLiberado.id_cupo_liberado)))
        reasig = list(db.scalars(select(Reasignacion).where(Reasignacion.id_cupo_liberado.in_([c.id_cupo_liberado for c in cupos]))))
        cupids = [c.id_cupo_liberado for c in cupos]
        audit = db.execute(select(AuditoriaEvento.accion, func.count()).where(
            ((AuditoriaEvento.entidad_afectada == "cupos_liberados") & AuditoriaEvento.id_entidad.in_(cupids)) |
            ((AuditoriaEvento.entidad_afectada == "intervenciones") & (AuditoriaEvento.datos_after["id_cita"].astext.in_([str(i) for i in ids["citas"]]) | AuditoriaEvento.id_entidad.in_(ids["intervenciones"]))) |
            ((AuditoriaEvento.entidad_afectada == "reasignaciones") & AuditoriaEvento.id_entidad.in_([r.id_reasignacion for r in reasig]))
        ).group_by(AuditoriaEvento.accion)).all()
        return {"cupos": [c.estado_cupo for c in cupos], "reasignaciones": len(reasig),
            "candidatos": [db.get(ListaEspera, i).estado_candidato for i in ids["candidatos"]],
            "intervenciones": db.scalar(select(func.count()).select_from(Intervencion).where(Intervencion.id_cita.in_(ids["citas"]))),
            "historial_final": db.scalar(select(func.count()).select_from(HistorialEstadoCita).where(
                HistorialEstadoCita.id_cita.in_(ids["citas"]), HistorialEstadoCita.estado_nuevo.in_(("LIBERADA", "CANCELADA")))),
            "audit": dict(audit)}


def peticiones(tipo, ids):
    cupos, candidatos, inter = ids["cupos"], ids["candidatos"], ids["intervenciones"]
    if tipo.startswith("reasignar"):
        return [(f"/cupos/{cupos[n if len(cupos) == 2 else 0]}/reasignar", {"id_candidato": candidatos[0], "confirmacion_humana": True}) for n in range(2)]
    if tipo.startswith("ofertar"):
        return [(f"/cupos/{cupos[n if len(cupos) == 2 else 0]}/ofertas", {"id_candidato": candidatos[n if len(candidatos) == 2 else 0]}) for n in range(2)]
    if tipo == "liberar":
        return [(f"/intervenciones/{i}/liberar-cupo", None) for i in inter]
    if tipo == "cancelar_liberar":
        return [(f"/citas/{ids['citas'][0]}/estado", {"estado_nuevo": "CANCELADA", "liberar_cupo": True}), (f"/intervenciones/{inter[0]}/liberar-cupo", None)]
    if tipo == "responder":
        return [(f"/intervenciones/{inter[0]}/respuesta", {"respuesta_paciente": "CONFIRMA"})] * 2
    if tipo == "cerrar":
        return [(f"/cupos/{cupos[0]}/ofertas/rechazo", None)] * 2
    return [("/intervenciones", {"id_cita": ids["citas"][0], "canal_contacto": "SMS",
        "plantilla_mensaje": "RECORDATORIO_CONFIRMACION_V1", "consentimiento_confirmado": True})] * 2


def carrera(tipo, ids, headers):
    tabla = "lista_espera" if tipo.endswith("_candidato") else ("cupos_liberados" if ids["cupos"] else "citas")
    patron = re.compile(r"FROM\s+" + tabla + r"\b", re.I)
    barrier, first, release = threading.Barrier(2), threading.Event(), threading.Event()
    mutex, pids, winner = threading.Lock(), {}, []
    marca = secrets.token_hex(8)
    def sesion_peticion():
        with Session(engine, expire_on_commit=False, autoflush=False) as db:
            db.execute(text("SET LOCAL lock_timeout='12s'"))
            db.execute(text("SET LOCAL statement_timeout='20s'"))
            preload = []
            for model, key in ((Cita, "citas"), (CupoLiberado, "cupos"), (ListaEspera, "candidatos"), (Intervencion, "intervenciones")):
                preload.extend(db.get(model, i) for i in ids[key])
            db.info["preloaded"] = preload  # referencias fuertes: no permitir GC del identity map
            conn = db.connection()
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            with mutex:
                slot = len(pids)
                pids[slot] = pid
            conn.info["qa_race"] = (marca, slot)
            barrier.wait(timeout=10)
            yield db
    def after_cursor(conn, cursor, statement, parameters, context, executemany):
        info = conn.info.get("qa_race")
        if not info or info[0] != marca or "FOR UPDATE" not in statement.upper() or not patron.search(statement):
            return
        with mutex:
            if winner:
                return
            winner.append(info[1])
        first.set()
        if not release.wait(timeout=12):
            raise AssertionError("No se liberó el primer lock de QA")
    app.dependency_overrides[get_db] = sesion_peticion
    event.listen(engine, "after_cursor_execute", after_cursor)
    requests = peticiones(tipo, ids)
    def enviar(item):
        with TestClient(app) as client:
            response = client.post(item[0], headers=headers, json=item[1])
            return {"status": response.status_code,
                "codigo": response.json().get("error", {}).get("codigo") if response.status_code >= 400 else None}
    observed = False
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(enviar, req) for req in requests]
            try:
                assert first.wait(timeout=10), "Ninguna solicitud alcanzó FOR UPDATE"
                waiter = pids[1 - winner[0]]
                with Session(engine) as observer:
                    until = time.monotonic() + 8
                    while time.monotonic() < until:
                        blockers = observer.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": waiter})
                        if pids[winner[0]] in blockers:
                            observed = True
                            break
                        time.sleep(0.02)
            finally:
                release.set()
            results = [f.result(timeout=25) for f in futures]
        assert observed, "No hubo contención demostrada en PostgreSQL"
        assert sum(200 <= r["status"] < 300 for r in results) == 1 and sum(r["status"] == 409 for r in results) == 1, results
        return {"responses": results, "database_lock_wait_observed": True, "preloaded_identity_map": True, "lock_table": tabla}
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", after_cursor)
        app.dependency_overrides.pop(get_db, None)


def main():
    url = urlsplit(get_settings().database_url)
    if not (url.hostname or "").startswith("predicitas-fase4-") or url.path != "/predicitas_fase4_test":
        raise SystemExit("Solo laboratorio D aislado")
    target = Path(sys.argv[1])
    if target.exists():
        raise SystemExit("No sobrescribir evidencia D")
    password, marca = secrets.token_hex(20), secrets.token_hex(8)
    with Session(engine) as db:
        assert db.scalar(text("SELECT current_user")) == "predicitas_app"
        usuario = Usuario(nombre_completo="QA D sintético", correo_institucional=f"d-{marca}@example.invalid",
                          password_hash=hash_password(password), rol="RECEPCION")
        db.add(usuario)
        db.commit()
        actor_id, correo = usuario.id_usuario, usuario.correo_institucional
    with TestClient(app) as client:
        login = client.post("/auth/login", data={"username": correo, "password": password})
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    app.dependency_overrides[reloj] = lambda: NOW
    app.dependency_overrides[modo_sombra] = lambda: False
    results = {}
    try:
        for tipo in ("reasignar_cupo", "reasignar_candidato", "ofertar_cupo", "ofertar_candidato",
                     "liberar", "cancelar_liberar", "responder", "cerrar", "crear_intervencion"):
            ids = escenario(actor_id, tipo)
            before = observar(ids)
            result = carrera(tipo, ids, headers)
            after = observar(ids)
            if tipo.startswith("reasignar"):
                assert after["reasignaciones"] == 1 and after["cupos"].count("REASIGNADO") == 1
                assert after["candidatos"] == ["ASIGNADO"] and after["audit"].get("REASIGNAR", 0) == 1
            elif tipo.startswith("ofertar"):
                assert after["cupos"].count("EN_OFERTA") == 1 and after["candidatos"].count("CONTACTADO") == 1
                assert after["audit"].get("OFERTAR", 0) == 1
            elif tipo in ("liberar", "cancelar_liberar"):
                assert len(after["cupos"]) == 1 and after["historial_final"] == before["historial_final"] + 1
                assert after["audit"].get("LIBERAR", 0) == before["audit"].get("LIBERAR", 0) + 1
            elif tipo == "cerrar":
                assert after["cupos"] == ["DISPONIBLE"] and after["candidatos"] == ["ACTIVO"]
                assert after["audit"].get("RECHAZAR", 0) == 1
            elif tipo == "crear_intervencion":
                assert after["intervenciones"] == 1 and after["audit"].get("CREATE", 0) == 1
            else:
                assert after["audit"].get("RESPUESTA", 0) == 1 and not after["cupos"]
            results[tipo] = {**result, "before": before, "after": after}
    finally:
        app.dependency_overrides.clear()
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"checks": results, "scope": "Dos solicitudes HTTP concurrentes por escenario, conexiones independientes, sin borrar datos QA"}, stream, indent=2)
        stream.write("\n")
    print("Concurrencia D: 9 escenarios con espera PostgreSQL observada y un único éxito efectivo: PASÓ")


if __name__ == "__main__":
    main()
