"""Paridad del generador, exportación y roundtrip; solo datos sintéticos QA."""
from datetime import date
import json
from pathlib import Path
import sys

SCENARIOS = [
    ("legacy_defaults", {}),
    ("seed_full", dict(historicas=1000, proximas=80, semilla=42, desde="2026-11-06", tasa_no_show=0.20, con_invalidas=False)),
    ("historical", dict(historicas=1000, proximas=0, semilla=42, desde="2026-10-29", con_invalidas=False)),
    ("upcoming", dict(historicas=0, proximas=80, semilla=42, desde="2026-11-06", con_invalidas=False)),
    ("empty", dict(historicas=0, proximas=0, con_invalidas=True)),
    ("small_custom", dict(historicas=1, proximas=1, prefijo="QA", semilla=9, con_invalidas=False)),
    ("invalid_rows", dict(historicas=50, proximas=10, semilla=7, con_invalidas=True, tasa_no_show=0.22)),
    ("leap_date", dict(historicas=40, proximas=10, desde="2024-02-29", semilla=123, con_invalidas=False)),
    ("alternative", dict(historicas=80, proximas=10, desde="2026-10-01", semilla=11, tasa_no_show=0.18, con_invalidas=False)),
]


def null_rows():
    common = {"paciente_anon_id": "PAC-QA-B-NULL", "sede": "SAN_ISIDRO", "especialidad": "CARDIOLOGIA",
        "medico": 'Dra. Núñez, "QA"\nTurno', "tipo_paciente": "CONTINUADOR", "canal_origen": "WEB",
        "inasistencias_previas": 0, "asistencias_previas": 0, "reprogramaciones_prev": 0}
    return [
        {**common, "id_cita_externa": "CIT-QA-B-H1", "fecha_hora_cita": "2026-10-20T09:00:00-05:00", "fecha_registro_cita": "2026-10-01T09:00:00-05:00", "estado_actual": "ATENDIDA", "target_no_show": 0},
        {**common, "id_cita_externa": "CIT-QA-B-H2", "fecha_hora_cita": "2026-10-21T09:00:00-05:00", "fecha_registro_cita": "2026-10-01T09:00:00-05:00", "estado_actual": "NO_SHOW", "target_no_show": 1},
        *[{**common, "id_cita_externa": f"CIT-QA-B-F{n}", "fecha_hora_cita": stamp,
            "fecha_registro_cita": "2026-11-01T09:00:00-05:00", "estado_actual": None,
            "inasistencias_previas": None, "asistencias_previas": None, "reprogramaciones_prev": None,
            "target_no_show": 1} for n, stamp in enumerate(("2026-11-10T14:00:00+00:00", "2026-11-10T09:00:00"), start=1)],
    ]


def main():
    mode, destination = sys.argv[1:]
    target = Path(destination)
    assert not target.exists()
    if mode == "reference":
        from app.modules.citas.synthetic import generar_citas
    elif mode == "candidate":
        from datasets.synthetic import generar_citas
    else:
        raise ValueError("Modo no autorizado")
    cases = {}
    for name, params in SCENARIOS:
        actual = dict(params)
        if "desde" in actual:
            actual["desde"] = date.fromisoformat(actual["desde"])
        cases[name] = generar_citas(**actual)
    if mode == "candidate":
        from datasets.operational_csv import guardar_csv_operacional, leer_csv_operacional, COLUMNAS
        from datasets.training_rows import fila_entrenamiento
        from datasets.temporal import LIMA
        from datetime import datetime
        rows = cases["seed_full"]
        path = guardar_csv_operacional(rows, ruta_nueva=target.parent / "seed_operacional.csv")
        assert leer_csv_operacional(path) == [{k: str(r[k]) for k in COLUMNAS} for r in rows]
        mapped = [fila_entrenamiento(r, corte=datetime(2026, 11, 6, 8, tzinfo=LIMA)) for r in rows[:1000]]
        assert len(mapped) == 1000 and all(len(r["features"]) == 9 for r in mapped)
        extras = null_rows()
        guardar_csv_operacional(extras, ruta_nueva=target.parent / "nulls_operacional.csv")
        for name, data in (("seed_source.json", rows), ("nulls_source.json", extras)):
            with (target.parent / name).open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(cases, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"Generador {mode}: {len(cases)} escenarios completados")


if __name__ == "__main__":
    main()
