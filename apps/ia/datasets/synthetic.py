"""Generador sintético extraído sin rediseñar algoritmo ni secuencia PRNG.

Resultados SIMULADOS (RF-056/RN16), no pacientes reales. Las tasas y pesos son
supuestos de modelado del piloto. Defaults legacy conservados para paridad;
las ejecuciones acreditadas deben proporcionar fecha/semilla/cantidades.
"""
import math
import random
from datetime import date, datetime, timedelta

from datasets.temporal import LIMA, derivar_variables

MEDICOS = {
    "CARDIOLOGIA": ["Dr. Ramírez", "Dra. Quispe", "Dr. Valdivia"],
    "TRAUMATOLOGIA": ["Dra. Vargas", "Dr. Salcedo", "Dr. Paredes"],
    "PEDIATRIA": ["Dr. Mendoza", "Dra. Morales", "Dra. Cárdenas"],
}
HORAS_MANANA = [(h, m) for h in range(8, 13) for m in (0, 30)]
HORAS_TARDE = [(h, m) for h in range(14, 19) for m in (0, 30)]
PESOS_CANAL = {"PRESENCIAL": -0.65, "WEB": 0.25, "CALL_CENTER": 0.60}
PESOS_ESPECIALIDAD = {"CARDIOLOGIA": -0.30, "PEDIATRIA": 0.15, "TRAUMATOLOGIA": 0.35}
PESOS_DIA = {"LUNES": -0.15, "MARTES": 0.00, "MIERCOLES": 0.00, "JUEVES": 0.05, "VIERNES": 0.35, "SABADO": -0.25}


def _sigmoide(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


def _calibrar(zs: list[float], objetivo: float) -> float:
    bajo, alto = -25.0, 25.0
    for _ in range(80):
        medio = (bajo + alto) / 2.0
        tasa = sum(_sigmoide(z + medio) for z in zs) / len(zs)
        if tasa < objetivo:
            bajo = medio
        else:
            alto = medio
    return (bajo + alto) / 2.0


def _fecha_laborable(rng: random.Random, inicio: date, fin: date) -> date:
    dias_rango = max(0, (fin - inicio).days)
    while True:
        dia = inicio + timedelta(days=rng.randint(0, dias_rango))
        if dia.weekday() != 6:
            return dia


def _muestrear_antelacion(rng: random.Random) -> int:
    u = rng.random()
    if u < 0.45:
        return rng.randint(0, 7)
    if u < 0.80:
        return rng.randint(8, 21)
    return rng.randint(22, 60)


def _muestrear_historial_paciente(rng: random.Random, tipo_paciente: str) -> tuple[int, int, int]:
    if tipo_paciente == "NUEVO":
        asistencias = 0
        inasistencias = 0
        reprogramaciones = rng.choices([0, 1, 2], weights=[82, 13, 5])[0]
        return asistencias, inasistencias, reprogramaciones
    total_previas = rng.randint(1, 14)
    perfil_incumplidor = rng.random() < 0.24
    if perfil_incumplidor:
        tasa_individual = rng.uniform(0.35, 0.85)
        inasistencias = max(1, min(total_previas, round(total_previas * tasa_individual)))
        reprogramaciones = rng.choices([0, 1, 2, 3], weights=[35, 35, 20, 10])[0]
    else:
        tasa_individual = rng.uniform(0.0, 0.18)
        inasistencias = min(total_previas - 1, round(total_previas * tasa_individual))
        reprogramaciones = rng.choices([0, 1, 2], weights=[85, 12, 3])[0]
    asistencias = max(0, total_previas - inasistencias)
    if asistencias == 0 and inasistencias == 0:
        asistencias = 1
    return asistencias, inasistencias, reprogramaciones


def _calcular_logit_clinico(*, antelacion, tipo_paciente, canal, franja, especialidad,
                          dia_semana, asistencias, inasistencias, reprogramaciones, rng):
    tasa_previa = inasistencias / (asistencias + inasistencias + 1.0)
    z_lineal = (
        0.085 * (antelacion - 14)
        + 1.35 * inasistencias
        - 0.28 * asistencias
        + 2.40 * tasa_previa
        + 0.85 * reprogramaciones
        + (0.90 if tipo_paciente == "NUEVO" else -0.20)
        + PESOS_CANAL[canal]
        + (0.55 if franja == "TARDE" else -0.15)
        + PESOS_ESPECIALIDAD[especialidad]
        + PESOS_DIA.get(dia_semana, 0.0)
    )
    z_interacciones = 0.0
    if inasistencias >= 2 and antelacion >= 14:
        z_interacciones += 2.60
    if tipo_paciente == "NUEVO" and antelacion >= 20 and canal in ("CALL_CENTER", "WEB"):
        z_interacciones += 2.35
    if reprogramaciones >= 1 and (inasistencias >= 1 or antelacion >= 18):
        z_interacciones += 1.95
    if franja == "TARDE" and canal == "CALL_CENTER" and antelacion >= 15:
        z_interacciones += 1.50
    if tipo_paciente == "CONTINUADOR" and asistencias >= 3 and inasistencias == 0 and reprogramaciones == 0 and antelacion <= 14:
        z_interacciones -= 2.50
    ruido = rng.gauss(0.0, 0.42)
    return z_lineal + z_interacciones + ruido


def _registro_base(rng, numero, dia, corte, prefijo):
    especialidad = rng.choice(list(MEDICOS))
    franja = "MANANA" if rng.random() < 0.55 else "TARDE"
    hora, minuto = rng.choice(HORAS_MANANA if franja == "MANANA" else HORAS_TARDE)
    fecha_hora = datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=LIMA)
    antelacion_objetivo = _muestrear_antelacion(rng)
    registro = (fecha_hora - timedelta(days=antelacion_objetivo)).replace(
        hour=rng.randint(8, 18), minute=rng.choice((0, 15, 30, 45)))
    registro = min(registro, corte, fecha_hora - timedelta(minutes=30))
    derivadas = derivar_variables(fecha_hora, registro)
    antelacion_real = min(60, derivadas["antelacion_dias"])
    if derivadas["antelacion_dias"] > 60:
        registro = (fecha_hora - timedelta(days=60)).replace(hour=10, minute=0)
        derivadas = derivar_variables(fecha_hora, registro)
        antelacion_real = derivadas["antelacion_dias"]
    tipo = "NUEVO" if rng.random() < 0.30 else "CONTINUADOR"
    asistencias, inasistencias, reprogramaciones = _muestrear_historial_paciente(rng, tipo)
    canal = rng.choices(["WEB", "CALL_CENTER", "PRESENCIAL"], weights=[50, 30, 20])[0]
    id_pac_num = numero if tipo == "NUEVO" else rng.randint(1, 650)
    registro_dict = {
        "id_cita_externa": f"CIT-{prefijo}-{numero:06d}", "paciente_anon_id": f"PAC-{prefijo}-{id_pac_num:05d}",
        "sede": "SAN_ISIDRO", "especialidad": especialidad, "medico": rng.choice(MEDICOS[especialidad]),
        "fecha_hora_cita": fecha_hora.isoformat(), "fecha_registro_cita": registro.isoformat(),
        "antelacion_dias": antelacion_real, "tipo_paciente": tipo, "canal_origen": canal,
        "franja_horaria": derivadas["franja_horaria"], "dia_semana": derivadas["dia_semana"],
        "inasistencias_previas": inasistencias, "reprogramaciones_prev": reprogramaciones, "asistencias_previas": asistencias,
    }
    z = _calcular_logit_clinico(antelacion=antelacion_real, tipo_paciente=tipo, canal=canal,
        franja=derivadas["franja_horaria"], especialidad=especialidad, dia_semana=derivadas["dia_semana"],
        asistencias=asistencias, inasistencias=inasistencias, reprogramaciones=reprogramaciones, rng=rng)
    return registro_dict, z


def generar_citas(historicas=1000, proximas=80, semilla=42, desde=date(2026, 10, 29),
                  tasa_no_show=0.20, con_invalidas=True, prefijo="SIM") -> list[dict]:
    rng = random.Random(semilla)
    corte = datetime(desde.year, desde.month, desde.day, tzinfo=LIMA) - timedelta(hours=6)
    inicio_historico = desde - timedelta(days=200)
    fin_historico = desde - timedelta(days=2)
    registros = []
    base = [_registro_base(rng, n, _fecha_laborable(rng, inicio_historico, fin_historico), corte, prefijo)
            for n in range(1, historicas + 1)]
    if base:
        intercepto = _calibrar([z for _, z in base], tasa_no_show)
        for registro, z in base:
            prob = _sigmoide(z + intercepto)
            no_show = rng.random() < prob
            registros.append({**registro, "estado_actual": "NO_SHOW" if no_show else "ATENDIDA", "target_no_show": 1 if no_show else 0})
    for n in range(historicas + 1, historicas + proximas + 1):
        dia = _fecha_laborable(rng, desde, desde + timedelta(days=13))
        registro, _ = _registro_base(rng, n, dia, corte, prefijo)
        registros.append({**registro, "estado_actual": "RECIBIDA", "target_no_show": None})
    if con_invalidas and registros:
        molde = dict(registros[-1])
        posterior = (datetime.fromisoformat(molde["fecha_hora_cita"]) + timedelta(days=2)).isoformat()
        registros += [
            {**molde, "id_cita_externa": f"CIT-{prefijo}-INV-001", "sede": "MIRAFLORES"},
            {**molde, "id_cita_externa": f"CIT-{prefijo}-INV-002", "especialidad": "DERMATOLOGIA"},
            {**molde, "id_cita_externa": registros[0]["id_cita_externa"]},
            {**molde, "id_cita_externa": f"CIT-{prefijo}-INV-003", "fecha_registro_cita": posterior},
        ]
    return registros
