r"""QA local y reversible del frontend, separado del servidor normal.

Desde la raíz: python frontend\tests\validar_diseno.py
O desde backend: python ..\frontend\tests\validar_diseno.py
Expone la API en 8001 para pruebas de navegador. Todas las escrituras quedan
dentro de una transacción externa con rollback. No elimina archivos existentes.
Los endpoints /__qa solo existen en este proceso de prueba, nunca en producción.
"""
import csv
import asyncio
import io
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
os.chdir(RAIZ / "backend")
sys.path.insert(0, str(RAIZ / "backend"))

import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import Usuario
from app.modules.citas.importer import importar_citas
from app.modules.citas.models import Cita
from app.modules.citas.synthetic import generar_citas

marca = uuid.uuid4().hex[:8]
prefijo = f"UX-{marca}"
conexion = engine.connect()
transaccion = conexion.begin()
sesion = Session(bind=conexion, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False)
# FastAPI puede ejecutar la entrada y salida de una dependencia generadora
# síncrona en trabajadores distintos; Lock permite liberar desde otro hilo.
cerrojo = threading.Lock()
usuarios = {}
resultados = []
cerrar = False
pausa = 0
servidor = None

def base_qa():
    yield sesion

class SerializarQA:
    """La conexión transaccional de QA atiende una petición completa a la vez."""
    def __init__(self, aplicacion):
        self.aplicacion = aplicacion
        self.bucle = None
        self.bloqueo = None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.aplicacion(scope, receive, send)
        bucle = asyncio.get_running_loop()
        if self.bucle is not bucle:
            self.bucle = bucle
            self.bloqueo = asyncio.Lock()
        async with self.bloqueo:
            await self.aplicacion(scope, receive, send)

def csv_bytes(registros):
    salida = io.StringIO(newline="")
    escritor = csv.DictWriter(salida, fieldnames=list(registros[0]))
    escritor.writeheader()
    escritor.writerows(registros)
    return salida.getvalue().encode("utf-8")

def comprobar(nombre, condicion):
    assert condicion, nombre
    resultados.append({"prueba": nombre, "resultado": "OK"})
    print(f"OK: {nombre}", flush=True)

try:
    for rol in ("ADMINISTRADOR", "RECEPCION", "TECNICO_IA"):
        usuario = Usuario(nombre_completo=f"Equipo de validación {rol}",
                          correo_institucional=f"ux.{rol.lower()}.{marca}@predicitas.crp",
                          password_hash=hash_password("ValidacionLocal123"), rol=rol)
        sesion.add(usuario)
        usuarios[rol] = usuario
    sesion.commit()
    registros = generar_citas(historicas=0, proximas=45, prefijo=prefijo)
    # Citas controladas para ensayar transiciones sin tocar las citas demo existentes.
    for registro in registros[:3]:
        registro["estado_actual"] = "RECIBIDA"
    importar_citas(sesion, registros, id_usuario=None, ip="127.0.0.1", origen="QA diseño con rollback")
    app.dependency_overrides[get_db] = base_qa
    with TestClient(app) as cliente:
        comprobar("Salud API", cliente.get("/health").json() == {"estado": "ok"})
        for origen in ("http://localhost:5173", "http://127.0.0.1:5173"):
            respuesta = cliente.options("/citas", headers={"Origin": origen, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
            comprobar(f"CORS {origen}", respuesta.status_code == 200 and respuesta.headers.get("access-control-allow-origin") == origen)
        comprobar("Citas sin token: 401", cliente.get("/citas").status_code == 401)
        comprobar("Token inválido: 401", cliente.get("/auth/me", headers={"Authorization": "Bearer token-invalido"}).status_code == 401)
        comprobar("Login incorrecto: 401", cliente.post("/auth/login", data={"username": usuarios["RECEPCION"].correo_institucional, "password": "incorrecta"}).status_code == 401)
        cabeceras = {}
        for rol, usuario in usuarios.items():
            respuesta = cliente.post("/auth/login", data={"username": usuario.correo_institucional, "password": "ValidacionLocal123"})
            comprobar(f"Login {rol}", respuesta.status_code == 200 and bool(respuesta.json().get("access_token")))
            cabeceras[rol] = {"Authorization": f"Bearer {respuesta.json()['access_token']}"}
            comprobar(f"Me {rol}", cliente.get("/auth/me", headers=cabeceras[rol]).json()["rol"] == rol)
        recepcion = cabeceras["RECEPCION"]
        tecnico = cabeceras["TECNICO_IA"]
        parametros = {"q": f"CIT-{prefijo}-", "desde": "2026-10-20", "limite": 20}
        primera = cliente.get("/citas", params=parametros, headers=recepcion).json()
        segunda = cliente.get("/citas", params={**parametros, "desplazamiento": 20}, headers=recepcion).json()
        comprobar("Bandeja y total reales", primera["total"] == 45 and len(primera["items"]) == 20)
        comprobar("Paginación sin repetir filas", len(segunda["items"]) == 20 and not ({c['id_cita'] for c in primera['items']} & {c['id_cita'] for c in segunda['items']}))
        filtro = cliente.get("/citas", params={**parametros, "especialidad": "CARDIOLOGIA", "estado": "RECIBIDA", "hasta": "2026-11-30"}, headers=recepcion).json()
        comprobar("Filtros de especialidad, estado y fechas", bool(filtro["items"]) and all(c["especialidad"] == "CARDIOLOGIA" and c["estado_actual"] == "RECIBIDA" for c in filtro["items"]))
        comprobar("Búsqueda vacía", cliente.get("/citas", params={"q": f"NO-EXISTE-{marca}"}, headers=recepcion).json()["total"] == 0)
        comprobar("Técnico puede leer citas", cliente.get("/citas", headers=tecnico).status_code == 200)
        comprobar("Cita inexistente: 404", cliente.get("/citas/999999999", headers=recepcion).status_code == 404)
        control = sesion.scalar(select(Cita).where(Cita.id_cita_externa == registros[0]["id_cita_externa"]))
        comprobar("Técnico no modifica: 403", cliente.post(f"/citas/{control.id_cita}/estado", json={"estado_nuevo": "CONFIRMADA"}, headers=tecnico).status_code == 403)
        comprobar("LIBERADA manual: 422", cliente.post(f"/citas/{control.id_cita}/estado", json={"estado_nuevo": "LIBERADA"}, headers=recepcion).status_code == 422)
        cambio = cliente.post(f"/citas/{control.id_cita}/estado", json={"estado_nuevo": "CONFIRMADA", "motivo": "Validación UX"}, headers=recepcion)
        comprobar("Confirmación e historial", cambio.status_code == 200 and cambio.json()["historial"][-1]["motivo_cambio"] == "Validación UX")
        atendida = cliente.post(f"/citas/{control.id_cita}/estado", json={"estado_nuevo": "ATENDIDA"}, headers=recepcion)
        comprobar("ATENDIDA: target 0", atendida.status_code == 200 and atendida.json()["target_no_show"] == 0)
        comprobar("Estado final: 409", cliente.post(f"/citas/{control.id_cita}/estado", json={"estado_nuevo": "CONFIRMADA"}, headers=recepcion).status_code == 409)
        otra = sesion.scalar(select(Cita).where(Cita.id_cita_externa == registros[1]["id_cita_externa"]))
        no_show = cliente.post(f"/citas/{otra.id_cita}/estado", json={"estado_nuevo": "NO_SHOW"}, headers=recepcion)
        comprobar("NO_SHOW: target 1", no_show.status_code == 200 and no_show.json()["target_no_show"] == 1)
        datos_csv = csv_bytes(generar_citas(historicas=0, proximas=20, prefijo=f"UXAPI-{marca}"))
        archivo = {"archivo": ("citas.csv", datos_csv, "text/csv")}
        comprobar("Técnico no importa: 403", cliente.post("/citas/importar", headers=tecnico, files=archivo).status_code == 403)
        carga = cliente.post("/citas/importar", headers=recepcion, files=archivo).json()
        comprobar("CSV: 20 aceptadas y 4 rechazadas", (carga["recibidas"], carga["aceptadas"], carga["rechazadas"]) == (24, 20, 4))
        repetida = cliente.post("/citas/importar", headers=recepcion, files=archivo).json()
        comprobar("CSV repetido: 0 aceptadas y 24 rechazadas", (repetida["aceptadas"], repetida["rechazadas"]) == (0, 24))
        for nombre, contenido in (("Sin filas", b"id_cita_externa,paciente_anon_id\n"), ("No UTF-8", b"\xff\xfe"), ("Mayor a 2 MB", b"x" * (2 * 1024 * 1024 + 1)), ("Más de 5000 filas", b"id_cita_externa\n" + b"dato\n" * 5001)):
            comprobar(f"{nombre}: 422", cliente.post("/citas/importar", headers=recepcion, files={"archivo": ("invalido.csv", contenido, "text/csv")}).status_code == 422)
        comprobar("Logout: 204", cliente.post("/auth/logout", headers=recepcion).status_code == 204)

    carpeta = Path(__file__).parent / "fixtures"
    carpeta.mkdir(exist_ok=True)
    fixture = carpeta / f"citas-diseno-{marca}.csv"
    fixture.write_bytes(csv_bytes(generar_citas(historicas=0, proximas=20, prefijo=f"UXWEB-{marca}")))
    manifiesto = {"marca": marca, "prefijo": f"CIT-{prefijo}-", "usuarios": {rol: u.correo_institucional for rol, u in usuarios.items()}, "csv": str(fixture), "pruebas_api": resultados}
    (Path(__file__).parent / "ultima_validacion_diseno.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")

    # El servidor normal conserva sus orígenes originales. Solo este proceso QA
    # permite el Vite aislado en 5175 para no detener el Vite del usuario en 5173.
    aplicacion_qa = SerializarQA(CORSMiddleware(app, allow_origins=["http://127.0.0.1:5175"], allow_methods=["*"], allow_headers=["*"]))

    @app.post("/__qa/expirar")
    def expirar_sesion():
        with cerrojo:
            usuarios["RECEPCION"].activo = False
            sesion.commit()
        return {"estado": "usuario QA temporalmente inactivo"}

    @app.post("/__qa/reactivar")
    def reactivar_sesion():
        with cerrojo:
            usuarios["RECEPCION"].activo = True
            sesion.commit()
        return {"estado": "usuario QA activo"}

    @app.post("/__qa/pausar")
    def pausar_servidor():
        global pausa
        pausa = 25
        servidor.should_exit = True
        return {"pausa_segundos": pausa}

    @app.post("/__qa/finalizar")
    def finalizar():
        global cerrar
        cerrar = True
        servidor.should_exit = True
        return {"estado": "cerrando QA y revirtiendo transacción"}

    print(json.dumps(manifiesto, ensure_ascii=False), flush=True)
    while not cerrar:
        servidor = uvicorn.Server(uvicorn.Config(aplicacion_qa, host="127.0.0.1", port=8001, log_level="warning", timeout_graceful_shutdown=2))
        servidor.run()
        if pausa:
            time.sleep(pausa)
            pausa = 0
        elif not cerrar:
            break
finally:
    app.dependency_overrides.clear()
    sesion.close()
    transaccion.rollback()
    conexion.close()
    print("QA finalizado: transacción revertida.", flush=True)
