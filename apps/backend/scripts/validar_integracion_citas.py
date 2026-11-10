"""Verifica los traspasos HTTP con IA real en una base temporal recién migrada."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.core.reloj import LIMA
from app.core.security import hash_password
from app.main import app
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.usuarios.models import Usuario
from tests.test_ia_endpoints import CITAS_PRUEBA_IA


def verificar():
    if engine.url.host != "127.0.0.1" or engine.url.database != "predicitas_integracion_test":
        raise RuntimeError("Usa exclusivamente la base temporal predicitas_integracion_test.")
    clave = "SoloLaboratorioIntegracion!"
    with SessionLocal.begin() as db:
        if db.scalar(select(Usuario.id_usuario).limit(1)) is not None:
            raise RuntimeError("Se requiere una base recién migrada y sin usuarios.")
        for rol in ("RECEPCION", "TECNICO_IA"):
            db.add(Usuario(nombre_completo=rol, correo_institucional=f"{rol.lower()}@integracion.test",
                           rol=rol, password_hash=hash_password(clave)))

    ahora = datetime.now(LIMA)
    fecha = (ahora + timedelta(days=2)).replace(hour=16, minute=30, second=0, microsecond=0)
    if fecha.weekday() == 6:
        fecha += timedelta(days=1)
    datos = {
        **CITAS_PRUEBA_IA[0],
        "fecha_hora_cita": fecha.isoformat(),
        "fecha_registro_cita": (fecha - timedelta(days=32)).isoformat(),
    }
    # El alta manual asigna el estado inicial en el servidor.
    datos.pop("estado_actual")
    with TestClient(app) as cliente:
        def peticion(metodo, ruta, estado, headers=None, **kwargs):
            respuesta = cliente.request(metodo, ruta, headers=headers, **kwargs)
            assert respuesta.status_code == estado, (metodo, ruta, respuesta.status_code, respuesta.text)
            return respuesta.json()

        def sesion(rol):
            login = peticion("POST", "/auth/login", 200, data={"username": f"{rol}@integracion.test", "password": clave})
            return {"Authorization": "Bearer " + login["access_token"]}

        recepcion, tecnico = sesion("recepcion"), sesion("tecnico_ia")
        peticion("GET", "/citas", 401)
        peticion("POST", "/citas", 403, tecnico, json=datos)
        cita = peticion("POST", "/citas", 201, recepcion, json=datos)
        ruta_cita = f"/citas/{cita['id_cita']}"
        peticion("POST", f"{ruta_cita}/prediccion", 403, tecnico)

        def elegibles():
            return peticion("GET", "/intervenciones/elegibles", 200, recepcion)["items"]

        assert all(item["id_cita"] != cita["id_cita"] for item in elegibles())
        prediccion = peticion("POST", f"{ruta_cita}/prediccion", 200, recepcion)
        assert prediccion["nivel_riesgo"] in ("ALTO", "MEDIO") and prediccion["es_simulacion"] is True
        assert any(item["id_cita"] == cita["id_cita"] for item in elegibles())

        nueva = {"id_cita": cita["id_cita"], "canal_contacto": "WHATSAPP",
                 "plantilla_mensaje": "RECORDATORIO_CONFIRMACION_V1", "consentimiento_confirmado": True}
        peticion("POST", "/intervenciones", 403, tecnico, json=nueva)
        intervencion = peticion("POST", "/intervenciones", 201, recepcion, json=nueva)
        assert all(item["id_cita"] != cita["id_cita"] for item in elegibles())
        ruta_intervencion = f"/intervenciones/{intervencion['id_intervencion']}"
        for estado in ("ENVIADA", "ENTREGADA"):
            peticion("POST", f"{ruta_intervencion}/estado", 200, recepcion, json={"estado_intervencion": estado})
        respuesta = peticion("POST", f"{ruta_intervencion}/respuesta", 200, recepcion,
                             json={"respuesta_paciente": "SOLICITA_LIBERACION", "optout": False})
        assert "LIBERAR_CUPO" in respuesta["acciones_disponibles"]
        assert peticion("GET", ruta_cita, 200, recepcion)["estado_actual"] == "RECIBIDA"
        liberar = f"{ruta_intervencion}/liberar-cupo"
        cupo = peticion("POST", liberar, 201, recepcion, json={"motivo": "Liberación sintética de laboratorio"})
        assert cupo["estado_cupo"] == "DISPONIBLE" and cupo["id_cita_origen"] == cita["id_cita"]
        peticion("POST", liberar, 409, recepcion, json={})
        ruta_cupo = f"/cupos/{cupo['id_cupo_liberado']}"
        candidato = peticion("POST", "/lista-espera", 200, recepcion, json={
            "paciente_anon_id": "PAC-INTEGRACION-ESPERA", "especialidad_req": datos["especialidad"],
            "franja_preferida": "TARDE", "prioridad_registro": 1,
        })
        id_candidato = candidato["id_candidato"]
        assert [item["id_candidato"] for item in peticion("GET", f"{ruta_cupo}/candidatos", 200, recepcion)] == [id_candidato]
        peticion("POST", f"{ruta_cupo}/ofertas", 403, tecnico, json={"id_candidato": id_candidato})
        oferta = peticion("POST", f"{ruta_cupo}/ofertas", 200, recepcion, json={"id_candidato": id_candidato})
        assert oferta["estado_cupo"] == "EN_OFERTA" and oferta["oferta_vigente"]["id_candidato"] == id_candidato
        confirmacion = {"id_candidato": id_candidato, "medio_confirmacion": "LLAMADA_CONFIRMADA"}
        rechazada = peticion("POST", f"{ruta_cupo}/reasignar", 400, recepcion,
                             json={**confirmacion, "confirmacion_humana": False})
        assert rechazada["error"]["codigo"] == "SOLICITUD_INVALIDA"
        vigente = peticion("GET", ruta_cupo, 200, recepcion)
        assert vigente["estado_cupo"] == "EN_OFERTA" and vigente["reasignacion"] is None
        reasignacion = peticion("POST", f"{ruta_cupo}/reasignar", 200, recepcion,
                               json={**confirmacion, "confirmacion_humana": True})
        persistido = peticion("GET", ruta_cupo, 200, recepcion)
        origen = peticion("GET", ruta_cita, 200, recepcion)
        assert persistido["estado_cupo"] == "REASIGNADO" and persistido["oferta_vigente"] is None
        assert persistido["reasignacion"]["id_reasignacion"] == reasignacion["id_reasignacion"]
        assert origen["estado_actual"] == "LIBERADA" and origen["historial"][-1]["estado_nuevo"] == "LIBERADA"
        assert origen["predicciones"][0]["id_prediccion"] == prediccion["id_prediccion"]
        assert origen["intervenciones"][0]["respuesta_paciente"] == "SOLICITA_LIBERACION"
        assert origen["reasignacion"]["id_reasignacion"] == reasignacion["id_reasignacion"]

    with SessionLocal() as db:
        acciones = list(db.scalars(select(AuditoriaEvento.accion)))
        for accion in ("PREDICT", "RESPUESTA", "LIBERAR", "OFERTAR", "REASIGNAR"):
            assert acciones.count(accion) == 1, (accion, acciones)
    print(f"Integración aprobada con {prediccion['version_modelo']} ({prediccion['nivel_riesgo']}). "
          "Permisos, rechazo sin confirmación, persistencia y auditoría verificados.")


if __name__ == "__main__":
    verificar()
