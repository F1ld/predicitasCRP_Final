"""Único registro global ORM. Importar antes de inspeccionar metadata/Alembic."""
from app.modules.auditoria.models import AuditoriaEvento  # noqa: F401
from app.modules.usuarios.models import Usuario  # noqa: F401
from app.modules.citas.models import Cita, HistorialEstadoCita  # noqa: F401
from app.modules.ia.models import PrediccionIA  # noqa: F401
from app.modules.intervenciones.models import Intervencion  # noqa: F401
from app.modules.lista_espera.models import CupoLiberado, ListaEspera, Reasignacion  # noqa: F401
