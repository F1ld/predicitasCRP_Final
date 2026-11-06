"""Laboratorio NUEVO de fase 4. Nunca adopta ni arranca recursos preexistentes.

Python del host: solo stdlib; aplicación/tests: imagen Python 3.12 de fase 3 por ID.
Fuentes montadas RO; hashes antes/después, sin exigir ni crear commits.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
IMAGE = "sha256:99b2976a7f143fce8c0d9813556612b4babe7b8f6612e7964674c5b5e6684cd3"
DATABASE = "predicitas_fase4_test"
S03 = "tests.test_reasignacion::test_flujo_completo_lista_espera_matching_y_reasignacion_con_confirmacion_humana"
CAMBIO_S03 = {S03: ["failure", "passed"]}


def escribir(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def leer(path):
    return json.loads(path.read_text(encoding="utf-8"))


def salida(command, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", **kwargs)
    if result.returncode:
        # No incluir command/stderr: las acciones de provisión pueden contener secretos.
        raise RuntimeError(f"Falló una acción de laboratorio ({command[0]}, salida {result.returncode})")
    return result.stdout.strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fuentes(base):
    paths = []
    for folder in ("apps/backend/app", "apps/backend/tests", "apps/backend/migrations", "apps/backend/scripts",
                   "docs/migracion/fase-04"):
        paths.extend((base / folder).rglob("*.py"))
    paths.extend((base / "apps/backend" / name) for name in ("requirements.txt", "Dockerfile", "pytest.ini", "alembic.ini"))
    paths.extend((base / "apps/frontend/tests" / name) for name in ("validar_diseno.py", "rutas_validacion.py"))
    return {p.relative_to(base).as_posix(): sha(p) for p in sorted(paths) if p.is_file()}


def protegidos():
    paths = [ROOT / p for p in (".env", "apps/backend/.env", "apps/frontend/.env",
                              "apps/backend/app/modules/ia/artifacts/modelo_predicitas_v1.joblib",
                              "artifacts/models/legacy-import/modelo_predicitas_v1.joblib")]
    paths.extend((ROOT / "data/samples").rglob("*.csv"))
    paths.extend((ROOT / "apps/backend/data").glob("*.csv"))
    paths.extend((ROOT / "apps/frontend/tests/fixtures").glob("*.csv"))
    paths.append(ROOT / "citas_para_importar_variado.csv")
    paths.extend((ROOT / "apps/backend/migrations/versions").glob("*.py"))
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths if p.is_file()}


def contenedor(meta, raw, source, *, network=True, image=None):
    return ["docker", "run", "--rm", "--network", meta["network"] if network else "none",
            "--mount", f"type=bind,source={source},target=/repo,readonly",
            "--mount", f"type=bind,source={HERE},target=/fase4,readonly",
            "--mount", f"type=bind,source={raw},target=/results",
            "-w", "/repo/apps/backend", "-e", "PYTHONPATH=/repo/apps/backend",
            "-e", "PYTHONDONTWRITEBYTECODE=1", "--env-file", meta["private_env"], image or IMAGE]


def accion(raw, nombre, command):
    log = raw / f"{nombre}.log"
    with log.open("x", encoding="utf-8", newline="\n") as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    escribir(raw / f"{nombre}.accion.json", {"exit_code": result.returncode, "log_sha256": sha(log)})
    print(f"{nombre}: salida {result.returncode}", flush=True)
    return result.returncode


def verificar(meta):
    if meta["database"] != DATABASE or not meta["db"].startswith("predicitas-fase4-"):
        raise ValueError("Laboratorio no autorizado")
    info = json.loads(salida(["docker", "inspect", meta["db"]]))[0]
    volumes = [m for m in info["Mounts"] if m["Type"] == "volume"]
    if len(info["Mounts"]) != 1 or len(volumes) != 1 or volumes[0]["Name"] != meta["volume"]:
        raise ValueError("Montajes inesperados")
    if volumes[0]["Destination"] != "/var/lib/postgresql/data":
        raise ValueError("Destino inesperado")
    if info["HostConfig"].get("PortBindings") or info["HostConfig"].get("NetworkMode") == "host":
        raise ValueError("Laboratorio con puertos host")
    if set(info["NetworkSettings"]["Networks"]) != {meta["network"]}:
        raise ValueError("Red inesperada")
    if info["Config"]["Labels"].get("predicitas.purpose") != "fase4-isolated-test":
        raise ValueError("Etiqueta incorrecta")
    network = json.loads(salida(["docker", "network", "inspect", meta["network"]]))[0]
    if not network["Internal"]:
        raise ValueError("La red debe ser interna")
    env = dict(line.split("=", 1) for line in Path(meta["private_env"]).read_text().splitlines() if "=" in line)
    for key in ("DATABASE_URL", "DATABASE_URL_MIGRACIONES"):
        url = urlsplit(env[key])
        if url.hostname != meta["db"] or url.path != "/" + DATABASE:
            raise ValueError("Env privado no corresponde al laboratorio")
    return info["State"]["Status"]


def preparar(raw, run_id, baseline_ref="2f4140e", scope="A"):
    # Reservar primero identidad exclusiva; ante fallo se conserva todo para diagnóstico.
    raw.mkdir(parents=True, exist_ok=False)
    commit_tested = salida(["git", "rev-parse", "HEAD"], cwd=ROOT)
    commit = salida(["git", "rev-parse", "--verify", baseline_ref + "^{commit}"], cwd=ROOT)
    if scope == "A" and not commit_tested.startswith("2f4140e"):
        raise ValueError("Revisar nuevo punto de retorno antes de preparar otro laboratorio")
    if scope in ("B1", "C", "D"):
        expected = {"B1": "2f95273", "C": "6da1c49", "D": "2ad167e"}[scope]
        if not commit.startswith(expected):
            raise ValueError(f"Bloque {scope} exige baseline explícito: {expected}")
        if salida(["git", "status", "--porcelain"], cwd=ROOT):
            raise ValueError("Registrar implementación antes de validar")
        if subprocess.run(["git", "merge-base", "--is-ancestor", commit, commit_tested], cwd=ROOT).returncode:
            raise ValueError("Baseline no es ancestro del código probado")
    backup = ROOT / "backups" / f"fase4-{run_id}"
    backup.mkdir(parents=True, exist_ok=False)
    archive = backup / "codigo-previo.zip"
    salida(["git", "archive", "--format=zip", f"--output={archive}", commit], cwd=ROOT)
    source = backup / "baseline"
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError("Ruta insegura en archive")
        bundle.extractall(source)
    for modelo in (Path("apps/backend/app/modules/ia/artifacts/modelo_predicitas_v1.joblib"),
                   Path("artifacts/models/legacy-import/modelo_predicitas_v1.joblib")):
        (source / modelo).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / modelo, source / modelo)
        assert sha(ROOT / modelo) == sha(source / modelo)
    private = Path(os.environ["LOCALAPPDATA"]) / "Temp/opencode" / f"fase4-{run_id}"
    private.mkdir(exist_ok=False)
    user = salida(["whoami"])
    salida(["icacls", str(private), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"])
    prefix = f"predicitas-fase4-{run_id}"
    meta = {"run_id": run_id, "commit_base": commit, "image_id": IMAGE, "db": prefix + "-db",
            "commit_tested": commit_tested, "scope": scope,
            "database": DATABASE, "network": prefix + "-net", "volume": prefix + "-test-pgdata",
            "private_env": str(private / "backend.env"), "baseline_source": str(source),
            "archive_sha256": sha(archive), "protected_files": protegidos(),
            "initial_sources": fuentes(ROOT), "started_utc": datetime.now(timezone.utc).isoformat()}
    owner_password, app_password = secrets.token_hex(24), secrets.token_hex(24)
    (private / "postgres.env").write_text(
        f"POSTGRES_USER=predicitas_owner\nPOSTGRES_DB={DATABASE}\nPOSTGRES_PASSWORD={owner_password}\n", encoding="utf-8")
    Path(meta["private_env"]).write_text(
        f"DATABASE_URL=postgresql+psycopg://predicitas_app:{app_password}@{meta['db']}/{DATABASE}\n"
        f"DATABASE_URL_MIGRACIONES=postgresql+psycopg://predicitas_owner:{owner_password}@{meta['db']}/{DATABASE}\n"
        f"SECRET_KEY={secrets.token_hex(32)}\nENVIRONMENT=test\n", encoding="utf-8")
    # Guardar antes de crear recursos para permitir parada conservadora si algo falla.
    escribir(raw / "laboratorio.json", meta)
    for kind, key in (("network", "network"), ("volume", "volume"), ("container", "db")):
        probe = subprocess.run(["docker", kind, "inspect", meta[key]], capture_output=True)
        if probe.returncode == 0:
            raise ValueError("Nombre de recurso preexistente: no se permite adopción")
    salida(["docker", "network", "create", "--internal", "--label", "predicitas.purpose=fase4-isolated-test", meta["network"]])
    salida(["docker", "volume", "create", "--label", "predicitas.purpose=fase4-isolated-test", meta["volume"]])
    salida(["docker", "run", "-d", "--name", meta["db"], "--network", meta["network"],
            "--label", "predicitas.purpose=fase4-isolated-test", "--env-file", str(private / "postgres.env"),
            "--mount", f"type=volume,source={meta['volume']},target=/var/lib/postgresql/data", "postgres:16"])
    for _ in range(60):
        ready = subprocess.run(["docker", "exec", meta["db"], "pg_isready", "-U", "predicitas_owner", "-d", DATABASE], capture_output=True)
        if ready.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("PostgreSQL no listo; detener conservando recursos")
    assert verificar(meta) == "running"
    salida(["docker", "exec", "-i", meta["db"], "psql", "-U", "predicitas_owner", "-d", DATABASE, "-v", "ON_ERROR_STOP=1"],
           input=f"CREATE ROLE predicitas_app LOGIN PASSWORD '{app_password}';")
    if accion(raw, "alembic_baseline", [*contenedor(meta, raw, source), "alembic", "upgrade", "head"]):
        raise RuntimeError("Migración de laboratorio falló")
    print("Laboratorio nuevo listo: red interna, sin puertos host, sin volúmenes originales.", flush=True)


def casos(path):
    result = {}
    for case in ET.parse(path).iter("testcase"):
        key = case.attrib.get("classname", "") + "::" + case.attrib["name"]
        result[key] = next((name for name in ("error", "failure", "skipped") if case.find(name) is not None), "passed")
    return result


def resumen(raw, meta):
    before, after = leer(raw / "baseline_captura.json"), leer(raw / "actual_captura.json")
    parity = {key: before[key] == after[key] for key in before}
    old, new = casos(raw / "baseline_diagnostico.xml"), casos(raw / "actual_diagnostico.xml")
    changed = {name: [state, new.get(name)] for name, state in old.items() if new.get(name) != state}
    added = {name: state for name, state in new.items() if name not in old}
    complete_before, complete_after = casos(raw / "baseline_completo.xml"), casos(raw / "actual_completo.xml")
    public = {"run_id": meta["run_id"], "commit_base": meta["commit_base"], "image_id": IMAGE,
               "block": meta.get("scope", "A"),
               "commit_tested": meta.get("commit_tested"),
               "scope": f"Fase 4 bloque {meta.get('scope', 'A')}; fase completa EN CURSO", "parity": parity,
              "baseline": {state: list(old.values()).count(state) for state in set(old.values())},
              "actual": {state: list(new.values()).count(state) for state in set(new.values())},
              "changed_old_cases": changed, "new_cases": added,
              "coverage_percent": leer(raw / "actual_coverage.json")["totals"]["percent_covered"],
              "protected_unchanged": protegidos() == meta["protected_files"],
              "source_files": leer(raw / "actual_sources.json"),
              "complete_collection_unchanged": complete_before == complete_after,
              "complete_exit_codes": {mode: leer(raw / f"{mode}_completo.accion.json")["exit_code"]
                                      for mode in ("baseline", "actual")},
              "transactions": leer(raw / "transacciones_identidad.json"),
              "full_suite": "Se conserva resultado explícito de colección; no se declara suite verde",
               "frontend": "No reejecutado", "laboratory_state": verificar(meta)}
    if meta.get("scope") == "B1":
        public["b1_rollback"] = leer(raw / "b1_rollback.json")
        assert public["b1_rollback"]["rollback_visible_from_independent_connection"]
        assert leer(raw / "b1_focalizadas.accion.json")["exit_code"] == 0
        assert leer(raw / "b1_rollback.accion.json")["exit_code"] == 0
    if meta.get("scope") == "C":
        public["c_rollback"] = leer(raw / "c_rollback.json")
        public["baseline_c_contracts"] = leer(raw / "baseline_c_contratos.json")
        assert all(v["independent_connection_rollback"] for v in public["c_rollback"]["checks"].values())
        assert public["baseline_c_contracts"]["s05_typeerror_reproduced"]
        assert leer(raw / "c_focalizadas.accion.json")["exit_code"] == 0
        assert leer(raw / "c_rollback.accion.json")["exit_code"] == 0
        assert leer(raw / "actual_diagnostico.accion.json")["exit_code"] == 0
        assert changed == CAMBIO_S03, "Solo se permite corregir S-03, no ocultar otros cambios"
    if meta.get("scope") == "D":
        public["packaged_image"] = leer(raw / "imagen_d.json")
        public["concurrency"] = leer(raw / "d_concurrencia.json")
        public["rollback"] = leer(raw / "d_rollback.json")
        public["image_id"] = public["packaged_image"]["image_id"]
        assert all(public["packaged_image"]["parity"].values()) and public["packaged_image"]["source_mount_absent"]
        assert len(public["concurrency"]["checks"]) == 9
        assert all(c["database_lock_wait_observed"] and c["preloaded_identity_map"] for c in public["concurrency"]["checks"].values())
        assert len(public["rollback"]["checks"]) == 4
        assert all(c["independent_connection_rollback"] for c in public["rollback"]["checks"].values())
        for check in ("actual_diagnostico", "paquete_runtime", "d_concurrencia", "d_rollback"):
            assert leer(raw / f"{check}.accion.json")["exit_code"] == 0
    escribir(raw / "resumen.json", public)
    assert all(parity.values()) and set(added.values()) == {"passed"}
    assert changed == (CAMBIO_S03 if meta.get("scope") == "C" else {})
    assert public["protected_unchanged"] and public["coverage_percent"] >= 75
    assert public["complete_collection_unchanged"]
    assert public["complete_exit_codes"]["baseline"] == public["complete_exit_codes"]["actual"]
    assert fuentes(ROOT) == public["source_files"], "Fuentes posteriores distintas de las probadas"
    print(json.dumps({k: public[k] for k in ("parity", "baseline", "actual", "coverage_percent", "protected_unchanged", "laboratory_state")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accion", choices=("preparar", "baseline", "actual", "detener", "resumen"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--baseline-ref", default="2f4140e", help="B.1: 2f95273; C: 6da1c49; fijar explícitamente")
    parser.add_argument("--scope", choices=("A", "B1", "C", "D"), default="A")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,40}", args.run_id):
        raise ValueError("run-id inválido")
    raw = ROOT / "runtime/test-results/fase-04" / args.run_id
    if args.accion == "preparar":
        preparar(raw, args.run_id, args.baseline_ref, args.scope)
        return
    meta = leer(raw / "laboratorio.json")
    state = verificar(meta)
    if args.accion == "detener":
        if state != "running":
            raise ValueError("Laboratorio no está en ejecución")
        accion(raw, "detener", ["docker", "stop", meta["db"]])
        return
    if args.accion == "resumen":
        resumen(raw, meta)
        return
    if state != "running":
        raise ValueError("Laboratorio no está en ejecución")
    mode = args.accion
    source = Path(meta["baseline_source"]) if mode == "baseline" else ROOT
    before = fuentes(source)
    escribir(raw / f"{mode}_sources.json", before)
    image = leer(raw / "imagen_d.json")["image_id"] if mode == "actual" and meta.get("scope") == "D" else IMAGE
    base = contenedor(meta, raw, source, image=image)
    if mode == "baseline" and meta.get("scope") == "C":
        if accion(raw, "baseline_c_contratos", [*base, "python", "/fase4/caracterizar_baseline_c.py", "/results/baseline_c_contratos.json"]):
            raise RuntimeError("Baseline C no coincide con los contratos caracterizados")
    if mode == "actual":
        if accion(raw, "alembic_actual", [*base, "alembic", "upgrade", "head"]):
            raise RuntimeError("Falló el entorno Alembic actualizado en laboratorio")
    if accion(raw, f"{mode}_captura", [*base, "python", "/fase4/capturar.py", f"/results/{mode}_captura.json"]):
        raise RuntimeError("Captura falló; revisar logs privados")
    accion(raw, f"{mode}_completo", [*base, "python", "-m", "pytest", f"--junitxml=/results/{mode}_completo.xml"])
    accion(raw, f"{mode}_diagnostico", [*base, "python", "-m", "pytest", "--ignore=tests/ia",
           f"--junitxml=/results/{mode}_diagnostico.xml", f"--cov-report=json:/results/{mode}_coverage.json"])
    if mode == "actual":
        if meta.get("scope") == "D":
            from imagen_d import runtime
            package = runtime(meta, raw, image)
            if accion(raw, "paquete_runtime", [*package, "python", "-m", "pytest", "tests/auth", "tests/citas",
                    "tests/intervenciones", "tests/lista_espera", "tests/usuarios", "tests/test_reasignacion.py",
                    "tests/test_intervenciones.py", "tests/test_ia_endpoints.py", "tests/test_ia_predictor.py",
                    "--no-cov", "--junitxml=/results/paquete_runtime.xml"]):
                raise RuntimeError("Regresión empaquetada D falló")
            if accion(raw, "d_concurrencia", [*package, "python", "/checks/probar_concurrencia_d.py", "/results/d_concurrencia.json"]):
                raise RuntimeError("Falló concurrencia D; no cerrar fase")
            if accion(raw, "d_rollback", [*package, "python", "/checks/probar_rollback_d.py", "/results/d_rollback.json"]):
                raise RuntimeError("Falló rollback D; no cerrar fase")
        if meta.get("scope") == "C":
            if accion(raw, "c_focalizadas", [*base, "python", "-m", "pytest", "--no-cov",
                    "tests/sistema/test_routers_c_fase4.py", "tests/lista_espera/test_ofertas_c_fase4.py",
                    "tests/intervenciones/test_lecturas_reportes_c_fase4.py", "tests/test_reasignacion.py",
                    "--junitxml=/results/c_focalizadas.xml"]):
                raise RuntimeError("Fallaron pruebas focalizadas C")
            if accion(raw, "c_rollback", [*base, "python", "/fase4/probar_rollback_c.py", "/results/c_rollback.json"]):
                raise RuntimeError("Falló rollback C entre conexiones independientes")
        if meta.get("scope") == "B1":
            if accion(raw, "b1_focalizadas", [*base, "python", "-m", "pytest", "--no-cov",
                    "tests/sistema/test_limites_flujos_fase4.py", "tests/sistema/test_contratos_b1_fase4.py",
                    "tests/intervenciones/test_auditoria_b1_fase4.py", "--junitxml=/results/b1_focalizadas.xml"]):
                raise RuntimeError("Fallaron pruebas focalizadas B.1")
            if accion(raw, "b1_rollback", [*base, "python", "/fase4/probar_rollback_b1.py", "/results/b1_rollback.json"]):
                raise RuntimeError("Falló rollback B.1 entre conexiones independientes")
        if accion(raw, "transacciones_identidad", [*base, "python", "/fase4/probar_transacciones_identidad.py",
                                                  "/results/transacciones_identidad.json"]):
            raise RuntimeError("Falló comprobación entre conexiones independientes")
    if fuentes(source) != before:
        raise ValueError("Fuentes cambiaron durante validación; repetir con ejecución separada")
    if protegidos() != meta["protected_files"]:
        raise ValueError("Archivos protegidos cambiaron")


if __name__ == "__main__":
    main()
