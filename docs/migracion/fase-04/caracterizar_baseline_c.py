"""Reproduce dos contratos legacy sin escrituras ni conexión: solo baseline C."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.errores import ReglaDeNegocioInvalida
from app.modules.lista_espera.service import reasignar_cupo
from app.modules.lista_espera.schemas import ReasignacionIn
from app.modules.reportes.router import alias_reporte_intervenciones


def main():
    try:
        alias_reporte_intervenciones(formato="json", usuario=SimpleNamespace(id_usuario=1), db=MagicMock())
    except TypeError as exc:
        assert "unexpected keyword argument '_'" in str(exc)
    else:
        raise AssertionError("El baseline no reproduce S-05; revisar punto de retorno")
    try:
        reasignar_cupo(MagicMock(), 1, ReasignacionIn(id_candidato=1, confirmacion_humana=False),
                       usuario=SimpleNamespace(id_usuario=1), ip="127.0.0.1")
    except ReglaDeNegocioInvalida as exc:
        assert exc.codigo_http == 400 and exc.codigo == "SOLICITUD_INVALIDA"
    else:
        raise AssertionError("El baseline no rechaza confirmación falsa")
    with Path(sys.argv[1]).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"s05_typeerror_reproduced": True, "false_confirmation_status": 400,
                   "false_confirmation_code": "SOLICITUD_INVALIDA", "database_access": False}, stream, indent=2)
        stream.write("\n")
    print("S-05 reproducido y contrato 400 de confirmación humana caracterizado, sin BD")


if __name__ == "__main__":
    main()
