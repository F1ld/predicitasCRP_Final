import csv
import io

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.core.exportacion import TIPO_XLSX
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.reportes import service
from tests.conftest import cabecera
from tests.panel.conftest import datos, solo_base_pruebas  # noqa: F401

COLUMNAS = (
    "ID Cupo Liberado", "Fecha Hora Cupo", "Especialidad", "Medico", "Horas Disponible",
    "Paciente Asignado", "Operador Confirma", "Estado Cupo",
)


def _exportaciones(db):
    return list(db.scalars(select(AuditoriaEvento).where(
        AuditoriaEvento.modulo == "REPORTES", AuditoriaEvento.accion == "EXPORT",
    )))


@pytest.mark.parametrize("ruta", ["/reportes/rep-03", "/reportes/reasignaciones"])
@pytest.mark.parametrize("formato", ["csv", "xlsx"])
def test_exportacion_audita_una_vez_con_actor_y_filtros(client, db, usuarios, ruta, formato):
    actor = usuarios["RECEPCION"]
    headers = cabecera(client, actor)
    filtros = {"desde": "2026-11-09", "hasta": "2026-11-10",
               "especialidad": "cardiologia", "id_operador": actor.id_usuario}
    assert client.get(ruta, headers=headers, params=filtros).status_code == 200
    assert _exportaciones(db) == []

    respuesta = client.get(ruta, headers=headers, params={**filtros, "formato": formato})
    assert respuesta.status_code == 200, respuesta.text
    evento, = _exportaciones(db)
    assert evento.id_usuario == actor.id_usuario and evento.entidad_afectada == "rep-03"
    assert evento.creado_en is not None and evento.direccion_ip
    assert evento.datos_after == {
        "formato": formato, "filtros": {**filtros, "especialidad": "CARDIOLOGIA"},
    }


def test_rechazos_de_formato_y_acceso_no_auditan(client, db, usuarios):
    ruta = "/reportes/rep-03"
    tecnico = cabecera(client, usuarios["TECNICO_IA"])
    recepcion = cabecera(client, usuarios["RECEPCION"])
    assert client.get(ruta, params={"formato": "xlsx"}).status_code == 401
    assert client.get(ruta, headers=tecnico, params={"formato": "xlsx"}).status_code == 403
    assert client.get(ruta, headers=recepcion, params={"formato": "pdf"}).status_code == 422
    assert _exportaciones(db) == []


@pytest.mark.parametrize(("formato", "generador"), [("csv", "generar_rep03_csv"), ("xlsx", "responder")])
def test_error_de_generacion_no_audita(client, db, usuarios, monkeypatch, formato, generador):
    headers = cabecera(client, usuarios["RECEPCION"])

    def fallar(*args, **kwargs):
        raise RuntimeError("No se pudo generar el archivo")

    monkeypatch.setattr(service, generador, fallar)
    with pytest.raises(RuntimeError, match="No se pudo generar"):
        client.get("/reportes/reasignaciones", headers=headers, params={"formato": formato})
    assert _exportaciones(db) == []


@pytest.mark.parametrize("ruta", ["/reportes/rep-03", "/reportes/reasignaciones"])
def test_xlsx_exporta_las_mismas_filas_filtradas(client, usuarios, datos, ruta):
    operador = usuarios["RECEPCION"]
    headers = cabecera(client, operador)
    cupo = datos.cupo(estado="REASIGNADO")
    datos.reasignar(cupo, operador)
    datos.cupo(especialidad="PEDIATRIA")
    filtros = {"especialidad": "CARDIOLOGIA", "id_operador": operador.id_usuario}

    consulta = client.get(ruta, headers=headers, params=filtros)
    assert consulta.status_code == 200, consulta.text
    fila, = consulta.json()["filas"]
    descarga = client.get(ruta, headers=headers, params={**filtros, "formato": "xlsx"})
    assert descarga.status_code == 200, descarga.text
    assert descarga.headers["content-type"] == TIPO_XLSX
    assert descarga.headers["content-disposition"].startswith('attachment; filename="rep-03_')
    assert descarga.headers["content-disposition"].endswith('.xlsx"')
    with io.BytesIO(descarga.content) as archivo:
        libro = load_workbook(archivo, read_only=True)
        try:
            assert list(libro.active.values) == [COLUMNAS, (
                fila["id_cupo_liberado"], fila["fecha_hora_cupo"], fila["especialidad"], fila["medico"],
                fila["horas_disponible"], fila["paciente_anon_id_asignado"], fila["id_operador_confirma"],
                fila["estado_cupo"],
            )]
        finally:
            libro.close()


def test_rep03_vacio_y_csv_compatible(client, usuarios):
    headers = cabecera(client, usuarios["RECEPCION"])
    ruta = "/reportes/rep-03"
    xlsx = client.get(ruta, headers=headers, params={"formato": "xlsx"})
    assert xlsx.status_code == 200, xlsx.text
    libro = load_workbook(io.BytesIO(xlsx.content))
    assert list(libro.active.values) == [COLUMNAS]
    libro.close()

    descarga = client.get(ruta, headers=headers, params={"formato": "csv"})
    assert descarga.status_code == 200, descarga.text
    assert descarga.headers["content-disposition"] == 'attachment; filename="rep-03.csv"'
    assert descarga.content.startswith(b"\xef\xbb\xbf")
    assert list(csv.reader(io.StringIO(descarga.content.decode("utf-8-sig")))) == [list(COLUMNAS)]
