"""Verifica en un clon las claves demo existentes sin login, escrituras o passwords en salida."""
import json
from pathlib import Path

from sqlalchemy import select
import yaml

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import verify_password
from app.modules.auth.models import Usuario


def main():
    url = get_settings().database_url
    if "predicitas-fase0-20261103-2200-restore:5432/predicitas" not in url:
        raise SystemExit("Solo se permite el servidor restaurado de fase0.")
    compose = yaml.safe_load(Path("/original-compose.yml").read_text(encoding="utf-8-sig"))
    command = compose["services"]["seed"]["command"]
    password = command[command.index("--password") + 1]
    emails = ("admin@predicitas.crp", "recepcion@predicitas.crp", "tecnico.ia@predicitas.crp")
    result = []
    with SessionLocal() as session:
        for email in emails:
            user = session.scalar(select(Usuario).where(Usuario.correo_institucional == email))
            result.append({"demo_account": email, "exists": user is not None, "role": user.rol if user else None, "active": user.activo if user else None, "matches_seed_password_configured_in_original_compose": bool(user and verify_password(password, user.password_hash))})
        session.rollback()
    summary = {"source": "copia restaurada del dump principal, no volumen original", "method": "verificacion local del hash sin autenticacion HTTP ni cambios de password", "password_or_hash_published": False, "writes_performed": False, "accounts": result, "credential_source_for_private_local_use": "services.seed.command en docker-compose.yml original; no se duplica la clave en este informe"}
    with Path("/evidence/credenciales_demo_verificadas.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
