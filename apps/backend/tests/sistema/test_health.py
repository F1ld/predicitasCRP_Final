from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from unittest.mock import MagicMock

from app import main
from app.main import app

client = TestClient(app)


def test_health():
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


def test_readiness_consulta_postgresql(monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(main.engine, "connect", connect)
    assert client.get("/health/ready").json() == {"estado": "ok"}
    connection = connect.return_value.__enter__.return_value
    connection.execute.assert_called_once()
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"
    connect.return_value.__exit__.assert_called_once()


def test_readiness_oculta_fallo_de_postgresql(monkeypatch):
    connect = MagicMock(side_effect=OperationalError(None, None, RuntimeError("detalle privado")))
    monkeypatch.setattr(main.engine, "connect", connect)
    respuesta = client.get("/health/ready")
    assert respuesta.status_code == 503
    assert respuesta.json() == {"estado": "no_disponible"}
    assert client.get("/health").status_code == 200
