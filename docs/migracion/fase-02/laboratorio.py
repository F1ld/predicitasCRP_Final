"""Copia RO del principal y laboratorio aislado. Nunca arranca el PostgreSQL original."""
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "fase-00"))
from registrar_bases_y_dumps import capture


def run(*args, input=None):
    p = subprocess.run(args, input=input, text=True, encoding="utf-8", capture_output=True)
    if p.returncode:
        raise RuntimeError(f"Fallo {args[0]}: {p.stderr}")
    return p.stdout


def main():
    output = HERE / "laboratorio.json"
    if output.exists():
        raise SystemExit("No sobrescribir evidencia")
    prep = json.loads((HERE / "preparacion.json").read_text(encoding="utf-8"))
    private = Path(prep["private_archive"]).parent
    config = json.loads(run("docker", "compose", "-f", "docker-compose.yml", "--env-file", ".env", "config", "--format", "json"))
    env = config["services"]["backend"]["environment"]
    runid = private.name.replace("fase2-", "predicitas-fase2-")
    volume = runid + "-pgdata"
    network = runid + "-net"
    db = runid + "-db"
    volumes = []
    for source in ("predicitas-crp_pgdata", "predicitas-backend_pgdata", "predicitas-guia-qa_qa_pgdata"):
        run("docker", "volume", "inspect", source)
        if run("docker", "ps", "-q", "--filter", f"volume={source}").strip():
            raise SystemExit("Volumen original tiene escritores; detener y revisar")
        filename = source + ".tar"
        run("docker", "run", "--rm", "--network", "none", "--mount", f"type=volume,source={source},target=/source,readonly", "--mount", f"type=bind,source={private},target=/backup", "--entrypoint", "tar", "postgres:16", "-cpf", f"/backup/{filename}", "-C", "/source", ".")
        digest = hashlib.sha256((private / filename).read_bytes()).hexdigest()
        volumes.append({"source": source, "readonly": True, "sha256": digest})
    existing = run("docker", "volume", "ls", "--format", "{{.Name}}").splitlines()
    if volume in existing:
        raise SystemExit("No reutilizar volumen de laboratorio")
    run("docker", "volume", "create", "--label", "predicitas.purpose=fase2-isolated-test", volume)
    run("docker", "run", "--rm", "--network", "none", "--mount", f"type=volume,source={volume},target=/clone", "--mount", f"type=bind,source={private},target=/backup,readonly", "--entrypoint", "tar", "postgres:16", "-xpf", "/backup/predicitas-crp_pgdata.tar", "-C", "/clone")
    run("docker", "network", "create", "--internal", "--label", "predicitas.purpose=fase2-isolated-test", network)
    run("docker", "run", "-d", "--name", db, "--network", network, "--label", "predicitas.purpose=fase2-isolated-test", "--mount", f"type=volume,source={volume},target=/var/lib/postgresql/data", "postgres:16")
    for _ in range(60):
        p = subprocess.run(["docker", "exec", db, "pg_isready", "-U", "predicitas_owner", "-d", "predicitas"], capture_output=True)
        if p.returncode == 0:
            break
        time.sleep(1)
    else:
        raise SystemExit("PostgreSQL laboratorio no listo")
    catalog = capture(db)
    (HERE / "bd_antes.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    for filename, program, options in (("crp.dump", "pg_dump", ["-Fc", "-d", "predicitas"]), ("globals_privado.sql", "pg_dumpall", ["--globals-only"])):
        run("docker", "exec", db, program, "-U", "predicitas_owner", *options, "-f", f"/tmp/{filename}")
        run("docker", "cp", f"{db}:/tmp/{filename}", str(private / filename))
    run("docker", "exec", "-i", db, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "predicitas_owner", "-d", "postgres", input="CREATE DATABASE predicitas_fase2_test OWNER predicitas_owner;")
    for name, database in (("smoke.env", "predicitas"), ("tests.env", "predicitas_fase2_test")):
        app_url = env["DATABASE_URL"].replace("@db:5432/predicitas", f"@{db}:5432/{database}")
        owner_url = env["DATABASE_URL_MIGRACIONES"].replace("@db:5432/predicitas", f"@{db}:5432/{database}")
        if f"@{db}:5432/{database}" not in app_url or f"@{db}:5432/{database}" not in owner_url:
            raise SystemExit("URL no cumple guarda de laboratorio")
        with (private / name).open("x", encoding="utf-8") as f:
            f.write(f"DATABASE_URL={app_url}\nDATABASE_URL_MIGRACIONES={owner_url}\nSECRET_KEY={secrets.token_hex(32)}\nPYTHONPATH=/workspace\nPYTHONDONTWRITEBYTECODE=1\nENVIRONMENT=fase2_test\n")
    data = {"private_directory": str(private), "db": db, "network": network, "volume": volume, "original_volumes": volumes, "database_ports_published": False, "source_started": False, "source_seeded": False}
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps({"db": db, "counts": catalog["counts_and_fingerprints"]}))


if __name__ == "__main__":
    main()
