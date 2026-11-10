"""Planes reproducibles del panel sobre datos sintéticos, SOLO en base de pruebas.

Ejecutar con un propietario de una base desechable cuyo nombre contenga panel_test:
python -m scripts.validar_panel --salida /results/planes-panel.json
Los registros se revierten al terminar. No acepta la base operativa del piloto.
"""
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import insert, text
from sqlalchemy.orm import Session

import app.bootstrap.models  # noqa: F401 (registro completo para resolver FK)
from app.core.database import engine
from app.core.reloj import LIMA
from app.modules.citas.models import Cita
from app.modules.ia.models import PrediccionIA
from app.modules.intervenciones.models import Intervencion
from app.modules.lista_espera.models import CupoLiberado
from app.modules.panel.consultas import sentencia_pendientes, sentencia_resumen
from app.modules.panel.service import obtener_resumen


def validar(salida: Path):
    if "panel_test" not in (engine.url.database or ""):
        raise SystemExit("Solo se permite una base desechable con 'panel_test' en su nombre")
    ahora = datetime(2026, 11, 9, 9, tzinfo=LIMA)
    inicio = ahora.replace(hour=0)
    fin = inicio + timedelta(days=1)
    resultados = {}
    with engine.connect() as conn:
        transaccion = conn.begin()
        db = Session(bind=conn)
        try:
            ids = list(db.scalars(insert(Cita).returning(Cita.id_cita), [dict(
                id_cita_externa=f"PERF-PANEL-{i}", paciente_anon_id=f"PERF-PAC-{i // 2}", sede="SAN_ISIDRO",
                especialidad="CARDIOLOGIA" if i % 2 else "PEDIATRIA", medico="Medico sintetico",
                fecha_hora_cita=ahora + timedelta(hours=2, minutes=i % 240),
                fecha_registro_cita=ahora - timedelta(days=7), antelacion_dias=7, tipo_paciente="NUEVO",
                canal_origen="WEB", franja_horaria="TARDE", dia_semana="LUNES", estado_actual="RECIBIDA",
            ) for i in range(5000)]))
            db.execute(insert(PrediccionIA), [dict(id_cita=id_cita, version_modelo=f"PERF-{version}",
                probabilidad_no_show="0.700", nivel_riesgo="ALTO", umbral_aplicado="0.450",
                features_snapshot={}, fecha_hora_inferencia=ahora - timedelta(days=2-version))
                for id_cita in ids for version in range(2)])
            db.execute(insert(Intervencion), [dict(id_cita=id_cita, canal_contacto="WHATSAPP",
                plantilla_mensaje="RECORDATORIO_CONFIRMACION_V1", estado_intervencion="ENVIADA",
                consentimiento_optout=(i % 20 == 0), fecha_hora_envio=ahora - timedelta(days=1))
                for i, id_cita in enumerate(ids[:2500])])
            db.execute(insert(CupoLiberado), [dict(id_cita_origen=id_cita,
                especialidad="CARDIOLOGIA", medico="Medico sintetico", fecha_hora_cupo=ahora + timedelta(hours=3),
                estado_cupo="EN_OFERTA" if i % 2 else "DISPONIBLE", origen_liberacion="CANCELACION_EXTERNA")
                for i, id_cita in enumerate(ids[:500])])
            # Solo base desechable, rol propietario. No se agrega ningún índice por esta medición.
            for tabla in ("citas", "predicciones_ia", "intervenciones", "cupos_liberados", "reasignaciones"):
                db.execute(text(f"ANALYZE {tabla}"))
            resumen = obtener_resumen(db, fecha=ahora.date(), especialidad=None, ahora=ahora)
            assert resumen.citas.total == 5000 and resumen.intervenciones.total == 2500
            assert resumen.cupos.total_liberados == 500
            for especialidad in (None, "CARDIOLOGIA"):
                params = dict(inicio=inicio, fin=fin, especialidad=especialidad, ahora=ahora)
                consultas = {"resumen": sentencia_resumen(**params)}
                for tipo in ("CITAS_SIN_INTERVENCION", "INTERVENCIONES_SIN_RESPUESTA", "OFERTAS_EN_CURSO"):
                    consultas[tipo] = sentencia_pendientes(**params, tipo=tipo, limite=20, desplazamiento=0)
                for nombre, stmt in consultas.items():
                    sql = str(stmt.compile(dialect=conn.dialect, compile_kwargs={"literal_binds": True}))
                    plan = db.scalar(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql))
                    resultados[f"{especialidad or 'TODAS'}:{nombre}"] = plan[0]
            salida.parent.mkdir(parents=True, exist_ok=True)
            salida.write_text(json.dumps({"citas": len(ids), "predicciones": 10000,
                "intervenciones": 2500, "cupos": 500, "planes": resultados}, indent=2), encoding="utf-8")
            for nombre, plan in resultados.items():
                print(f"{nombre}: {plan['Execution Time']:.2f} ms")
        finally:
            db.close()
            transaccion.rollback()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    validar(parser.parse_args().salida)
