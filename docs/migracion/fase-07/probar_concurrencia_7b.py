"""Sesiones PostgreSQL independientes: carreras y rollback visible externamente."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
from pathlib import Path
import threading
import sys
from unittest.mock import patch

sys.path.insert(0, "/app")

from sqlalchemy import func, select

import app.bootstrap.models
from app.core.database import SessionLocal
from app.core.errores import Conflicto
from app.core.security import hash_password
from app.modules.auth.public import Principal
from app.modules.citas.importer import importar_citas
from app.modules.citas.models import Cita
from app.modules.citas.public import transicionar_cita_interno
from app.modules.ia import service
from app.modules.ia.models import PrediccionIA
from app.modules.ia.puerto import ResultadoMotor
from app.modules.usuarios.models import Usuario
from tests.test_ia_endpoints import CITAS_PRUEBA_IA


class Doble:
    def __init__(self, db, before=None):
        self.db, self.before = db, before

    def version(self):
        assert not self.db.in_transaction()
        return "carrera-7b"

    def predecir(self, features, *, version):
        assert not self.db.in_transaction()
        if self.before:
            self.before()
        return ResultadoMotor(version_modelo=version, probabilidad_no_show=Decimal("0.285"),
            nivel_riesgo="BAJO", umbral_aplicado=Decimal("0.450"), features_snapshot=features.snapshot(),
            explicabilidad_resumen="Concurrencia [Simulado]")

    def predecir_lote(self, features, *, version):
        return [self.predecir(f, version=version) for f in features]


def main():
    with SessionLocal() as db:
        user = Usuario(nombre_completo="Laboratorio 7B", correo_institucional="carreras7b@predicitas.crp",
            password_hash=hash_password("SoloLaboratorio7B123"), rol="ADMINISTRADOR", activo=True)
        db.add(user)
        db.flush()
        principal = Principal(user.id_usuario, user.nombre_completo, user.correo_institucional,
                              user.rol, user.activo, user.creado_en, user.actualizado_en)
        importar_citas(db, [r | {"id_cita_externa": r["id_cita_externa"] + "-RACE"} for r in CITAS_PRUEBA_IA],
            id_usuario=principal.id_usuario, ip="127.0.0.1", origen="7b-carrera")
        ids = list(db.scalars(select(Cita.id_cita).order_by(Cita.id_cita)))
    barrier = threading.Barrier(2)
    def request():
        with SessionLocal() as db:
            return service.predecir_cita(db, ids[0], usuario=principal, ip="127.0.0.1",
                motor=Doble(db, lambda: barrier.wait(timeout=10))).id_prediccion
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(request) for _ in range(2)]
        predictions = [f.result(timeout=20) for f in futures]
    assert predictions[0] == predictions[1]
    with SessionLocal() as check:
        assert check.scalar(select(func.count(PrediccionIA.id_prediccion))) == 1

    # Cambio real confirmado por otra sesión mientras se calcula el snapshot.
    def change_features():
        with SessionLocal.begin() as other:
            other.get(Cita, ids[1]).reprogramaciones_prev += 1
    with SessionLocal() as db:
        try:
            service.predecir_cita(db, ids[1], usuario=principal, ip="127.0.0.1", motor=Doble(db, change_features))
        except Conflicto:
            pass
        else:
            raise AssertionError("Se guardó un snapshot obsoleto")
    def close_cita():
        with SessionLocal.begin() as other:
            transicionar_cita_interno(other, ids[1], "ATENDIDA", usuario=principal, ip="127.0.0.1")
    with SessionLocal() as db:
        try:
            service.predecir_cita(db, ids[1], usuario=principal, ip="127.0.0.1", motor=Doble(db, close_cita))
        except Conflicto:
            pass
        else:
            raise AssertionError("Se predijo una cita que terminó durante el cálculo")

    # Fallo tras flush: otra conexión no observa cambios y el rollback es total.
    with SessionLocal() as db:
        def fail(*a, **k):
            assert db.scalar(select(func.count(PrediccionIA.id_prediccion))) == 2
            with SessionLocal() as other:
                assert other.scalar(select(func.count(PrediccionIA.id_prediccion))) == 1
            raise RuntimeError("Auditoría interrumpida después de flush")
        with patch.object(service, "registrar_evento", fail):
            try:
                service.predecir_cita(db, ids[0], usuario=principal, ip="127.0.0.1",
                    motor=type("NuevaVersion", (Doble,), {"version": lambda self: "version-fallida"})(db))
            except RuntimeError:
                pass
            else:
                raise AssertionError("No se propagó fallo de auditoría")
    with SessionLocal() as other:
        assert other.scalar(select(func.count(PrediccionIA.id_prediccion))) == 1
        assert other.get(Cita, ids[1]).estado_actual == "ATENDIDA"
    summary = dict(doble_peticion_misma_fila=True, requests=2, predicciones=1,
        cambio_features_otra_sesion_rechazado=True, cierre_cita_otra_sesion_rechazado=True,
        rollback_tras_flush_observado_independientemente=True)
    Path("/results/concurrencia.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
