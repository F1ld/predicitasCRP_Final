"""Seed manual desde CSV sintético explícito; nunca genera ni reinicializa datos.

Uso: python -m scripts.seed --csv /datos/seed.csv --sha256 HASH --confirmar-bd NOMBRE
Contraseña de nuevos usuarios: SEED_PASSWORD local o entrada interactiva oculta.
Una carga parcial requiere --reconciliar; diferencias existentes nunca se pisan.
"""
import argparse
import csv
from dataclasses import asdict, dataclass
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys

from sqlalchemy import func, select, text

import app.bootstrap.models  # noqa: F401
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.auditoria.public import registrar_evento
from app.modules.citas.importer import validar_fila
from app.modules.citas.models import Cita, HistorialEstadoCita
from app.modules.citas.public import importar_citas_interno
from app.modules.citas.reglas import ESTADOS_DESENLACE, ahora_lima, contar_previos
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.politicas import validar_clave

COLUMNAS = (
    "id_cita_externa", "paciente_anon_id", "sede", "especialidad", "medico",
    "fecha_hora_cita", "fecha_registro_cita", "tipo_paciente", "canal_origen",
    "inasistencias_previas", "reprogramaciones_prev", "asistencias_previas", "estado_actual",
)
MAX_BYTES = 2 * 1024 * 1024
MAX_FILAS = 5000
SEED_LOCK = 60420261107
USUARIOS_DEMO = [
    ("Administrador Demo", "admin@predicitas.crp", "ADMINISTRADOR"),
    ("Recepcion Demo", "recepcion@predicitas.crp", "RECEPCION"),
    ("Tecnico IA Demo", "tecnico.ia@predicitas.crp", "TECNICO_IA"),
]


class SeedError(ValueError):
    def __init__(self, codigo, **conteos):
        self.codigo, self.conteos = codigo, conteos
        super().__init__(codigo)


@dataclass(frozen=True)
class ResultadoSeed:
    sha256: str
    recibidas: int
    existentes: int
    insertadas: int
    usuarios_creados: int
    reconciliada: bool


def leer_csv(ruta: Path, esperado: str):
    ruta = Path(ruta)
    if not ruta.is_absolute() or ruta.is_symlink() or not ruta.is_file():
        raise SeedError("CSV_ABSOLUTO_REGULAR_REQUERIDO")
    with ruta.open("rb") as stream:
        contenido = stream.read(MAX_BYTES + 1)
    if len(contenido) > MAX_BYTES:
        raise SeedError("CSV_SUPERA_2_MIB")
    digest = hashlib.sha256(contenido).hexdigest()
    if not re.fullmatch(r"[a-f0-9]{64}", esperado) or digest != esperado:
        raise SeedError("HASH_CSV_INCORRECTO")
    try:
        reader = csv.DictReader(io.StringIO(contenido.decode("utf-8-sig"), newline=""), strict=True)
        if reader.fieldnames != list(COLUMNAS):
            raise SeedError("CABECERA_NO_CANONICA")
        rows = []
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise SeedError("COLUMNAS_INCONSISTENTES")
            rows.append({k: v for k, v in row.items() if v != ""})
            if len(rows) > MAX_FILAS:
                raise SeedError("CSV_SUPERA_5000_FILAS")
    except (UnicodeError, csv.Error):
        raise SeedError("CSV_UTF8_INVALIDO") from None
    if not rows:
        raise SeedError("CSV_SIN_FILAS")
    return rows, digest


def _obtener_password():
    password = os.environ.get("SEED_PASSWORD")
    if not password:
        if not sys.stdin.isatty():
            raise SeedError("SEED_PASSWORD_REQUERIDA_PARA_USUARIOS_NUEVOS")
        password = getpass.getpass("Contraseña de los nuevos usuarios demo: ")
    return password


def aplicar_seed(db, registros, *, digest, confirmar_bd, reconciliar=False,
                 obtener_password=_obtener_password, ahora=None):
    """Componible: el llamador confirma o revierte usuarios+citas+historial+auditoría.

    No modifica usuarios/citas existentes. Las celdas vacías mantienen los defaults
    e inferencia RN17 del importador. Si faltan contadores se verifica su valor
    inferido en el contexto completo, sin corregir un contador ya persistido.
    """
    if db.get_bind().dialect.name != "postgresql":
        raise SeedError("POSTGRESQL_REQUERIDO")
    if db.scalar(text("select current_database()")) != confirmar_bd:
        raise SeedError("BD_NO_CONFIRMADA")
    if not db.scalar(text("select pg_try_advisory_xact_lock(:key)"), {"key": SEED_LOCK}):
        raise SeedError("OTRO_SEED_EN_CURSO")
    if not re.fullmatch(r"[a-f0-9]{64}", digest) or not 1 <= len(registros) <= MAX_FILAS:
        raise SeedError("ENTRADA_INVALIDA")
    ahora = ahora or ahora_lima()
    normalizadas = {}
    for fila, raw in enumerate(registros, start=1):
        try:
            reg, derivadas = validar_fila(raw, ahora)
        except ValueError:
            raise SeedError("FILA_INVALIDA", fila=fila) from None
        if (not re.fullmatch(r"CIT-SIM-[A-Za-z0-9_-]+", reg.id_cita_externa)
                or not re.fullmatch(r"PAC-SIM-[A-Za-z0-9_-]+", reg.paciente_anon_id)):
            raise SeedError("SOLO_IDENTIFICADORES_SINTETICOS", fila=fila)
        if reg.id_cita_externa in normalizadas:
            raise SeedError("ID_DUPLICADO_EN_CSV", fila=fila)
        normalizadas[reg.id_cita_externa] = (reg, derivadas, raw)
    existentes = db.scalars(select(Cita).where(Cita.id_cita_externa.in_(normalizadas))
                            .order_by(Cita.id_cita).with_for_update()).all()
    ids = {c.id_cita_externa for c in existentes}
    # Contexto RN17: desenlaces persistidos + históricos que faltan en este CSV.
    # Evita declarar reconciliada una carga donde un contador omitido quedó
    # incompleto porque su histórico anterior se importó después.
    pacientes = {reg.paciente_anon_id for reg, _, _ in normalizadas.values()}
    desenlaces = {p: [] for p in pacientes}
    for paciente, fecha, estado in db.execute(select(Cita.paciente_anon_id, Cita.fecha_hora_cita,
            Cita.estado_actual).where(Cita.paciente_anon_id.in_(pacientes), Cita.estado_actual.in_(ESTADOS_DESENLACE))):
        desenlaces[paciente].append((fecha, estado))
    for ident, (reg, _, _) in normalizadas.items():
        if ident not in ids and reg.estado_actual in ESTADOS_DESENLACE:
            desenlaces[reg.paciente_anon_id].append((reg.fecha_hora_cita, reg.estado_actual))
    historial = {}
    if existentes:
        for h in db.scalars(select(HistorialEstadoCita).where(
                HistorialEstadoCita.id_cita.in_([c.id_cita for c in existentes]))):
            historial.setdefault(h.id_cita, set()).add((h.estado_anterior, h.estado_nuevo))
    conflicts = 0
    for cita in existentes:
        reg, derivadas, _ = normalizadas[cita.id_cita_externa]
        expected = {k: v for k, v in reg.model_dump().items() if v is not None}
        inasistencias, asistencias = contar_previos(desenlaces[reg.paciente_anon_id], reg.fecha_registro_cita)
        if reg.inasistencias_previas is None:
            expected["inasistencias_previas"] = inasistencias
        if reg.asistencias_previas is None:
            expected["asistencias_previas"] = asistencias
        expected |= derivadas | {"target_no_show": ESTADOS_DESENLACE.get(reg.estado_actual)}
        transitions = {(None, "RECIBIDA")}
        if reg.estado_actual != "RECIBIDA":
            transitions.add(("RECIBIDA", reg.estado_actual))
        if (any(getattr(cita, k) != v for k, v in expected.items())
                or not transitions <= historial.get(cita.id_cita, set())):
            conflicts += 1
    if conflicts:
        raise SeedError("CITAS_EXISTENTES_DIFERENTES_O_SIN_HISTORIAL", conflictos=conflicts)
    faltantes = [raw for ident, (_, _, raw) in normalizadas.items() if ident not in ids]
    if existentes and faltantes and not reconciliar:
        raise SeedError("CARGA_PARCIAL_REQUIERE_RECONCILIAR", existentes=len(ids), faltantes=len(faltantes))
    usuarios, nuevos = {}, []
    for nombre, correo, rol in USUARIOS_DEMO:
        usuario = db.execute(select(Usuario).where(func.lower(Usuario.correo_institucional) == correo)
                             .with_for_update()).scalar_one_or_none()
        if usuario is not None and (usuario.rol != rol or not usuario.activo):
            raise SeedError("USUARIO_DEMO_INCOMPATIBLE")
        usuarios[rol] = usuario
        if usuario is None:
            nuevos.append((nombre, correo, rol))
    if nuevos:
        password = obtener_password()
        try:
            password = validar_clave(password)
        except ValueError:
            raise SeedError("CLAVE_NUEVA_INVALIDA") from None
        pwd_hash = hash_password(password)
        for nombre, correo, rol in nuevos:
            # Bootstrap de identidad: no hay administrador previo que pueda actuar.
            usuario = Usuario(nombre_completo=nombre, correo_institucional=correo,
                              password_hash=pwd_hash, rol=rol, activo=True)
            db.add(usuario)
            usuarios[rol] = usuario
        db.flush()
        for _, _, rol in nuevos:
            registrar_evento(db, modulo="USUARIOS", accion="SEED_CREATE", entidad_afectada="usuarios",
                id_entidad=usuarios[rol].id_usuario, id_usuario=usuarios["ADMINISTRADOR"].id_usuario,
                direccion_ip="127.0.0.1", datos_after={"rol": rol, "origen": "seed:sha256:" + digest})
    if faltantes:
        resultado = importar_citas_interno(db, faltantes,
            id_usuario=usuarios["ADMINISTRADOR"].id_usuario, ip="127.0.0.1",
            origen="seed:sha256:" + digest, ahora=ahora)
        if resultado.rechazadas or resultado.aceptadas != len(faltantes):
            raise SeedError("IMPORTACION_INCOMPLETA", rechazadas=resultado.rechazadas)
    db.flush()
    return ResultadoSeed(digest, len(registros), len(ids), len(faltantes), len(nuevos), bool(ids and faltantes))


def ejecutar_seed(ruta, *, esperado, confirmar_bd, reconciliar=False):
    registros, digest = leer_csv(ruta, esperado)
    with SessionLocal.begin() as db:
        resultado = aplicar_seed(db, registros, digest=digest, confirmar_bd=confirmar_bd, reconciliar=reconciliar)
    return resultado  # éxito solo tras commit; cualquier excepción revierte la transacción.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--confirmar-bd", required=True)
    parser.add_argument("--reconciliar", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = ejecutar_seed(args.csv, esperado=args.sha256, confirmar_bd=args.confirmar_bd,
                               reconciliar=args.reconciliar)
    except SeedError as exc:
        parser.exit(1, json.dumps({"error": exc.codigo, **exc.conteos}) + "\n")
    except Exception:
        parser.exit(1, 'Seed cancelado; transacción revertida. Revise configuración/BD sin publicar credenciales.\n')
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
