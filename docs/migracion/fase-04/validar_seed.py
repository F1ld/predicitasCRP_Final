"""Complemento seed: laboratorio exclusivo, paquete D y publicación sanitizada."""
import argparse
from pathlib import Path
import re

from validar import ROOT, HERE, accion, escribir, fuentes, leer, preparar, protegidos, salida, sha, verificar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("ejecutar", "publicar", "verificar"))
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"seed-[a-z0-9-]{3,32}", args.run_id):
        raise ValueError("run-id seed exclusivo requerido")
    raw = ROOT / "runtime/test-results/fase-04" / args.run_id
    target = HERE / "evidencia" / args.run_id
    if args.action == "verificar":
        manifest = leer(target / "manifest.json")
        assert manifest["run_id"] == args.run_id
        for item in manifest["files"]:
            assert Path(item["name"]).name == item["name"]
            assert sha(target / item["name"]) == item["sha256"]
        print("Integridad de evidencia seed verificada; no reejecuta el laboratorio")
        return
    if args.action == "publicar":
        meta = leer(raw / "laboratorio.json")
        assert verificar(meta) == "exited"
        assert fuentes(ROOT) == meta["initial_sources"] and protegidos() == meta["protected_files"]
        assert leer(raw / "seed.accion.json")["exit_code"] == 0
        result = leer(raw / "seed.json")
        assert result["rerun"]["all_persisted_rows_identical"] and result["rollback"]["after_close_empty"]
        target.mkdir(parents=True, exist_ok=False)
        escribir(target / "resumen.json", {"run_id": args.run_id, "commit_tested": meta["commit_tested"],
            "image_id": leer(raw / "paquete.json")["image_id"], "packaged_backend_without_source_mount": True,
            "laboratory_state": "exited", "protected_unchanged": True, "source_files": meta["initial_sources"],
            "result": result})
        escribir(target / "manifest.json", {"run_id": args.run_id,
            "files": [{"name": "resumen.json", "sha256": sha(target / "resumen.json")}]})
        print("Evidencia complementaria seed publicada sin secretos ni logs")
        return
    assert not salida(["git", "status", "--porcelain"], cwd=ROOT), "Registrar herramientas antes de validar"
    image = leer(HERE / "evidencia/bloque-d-20261106-04/resumen.json")["image_id"]
    assert salida(["docker", "image", "inspect", "--format", "{{.Id}}", image]) == image
    commit = salida(["git", "rev-parse", "HEAD"], cwd=ROOT)
    preparar(raw, args.run_id, baseline_ref=commit, scope="SEED")
    meta = leer(raw / "laboratorio.json")
    try:
        # Confirmar que /app contiene exactamente el seed/backend registrado.
        code = "import hashlib,json; from pathlib import Path; print(json.dumps({p.as_posix():hashlib.sha256(p.read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest() for folder in ('app','scripts') for p in Path(folder).rglob('*.py')}))"
        import json
        packaged = json.loads(salida(["docker", "run", "--rm", "--network", "none", image, "python", "-c", code]))
        import hashlib
        def normalized_hash(path):
            return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        assert all(digest == normalized_hash(ROOT / "apps/backend" / name) for name, digest in packaged.items())
        escribir(raw / "paquete.json", {"image_id": image, "packaged_sources_match": True})
        env = dict(line.split("=", 1) for line in Path(meta["private_env"]).read_text().splitlines() if "=" in line)
        runtime_env = Path(meta["private_env"]).with_name("runtime.env")
        with runtime_env.open("x", encoding="utf-8", newline="\n") as stream:
            for key in ("DATABASE_URL", "SECRET_KEY", "ENVIRONMENT"):
                stream.write(f"{key}={env[key]}\n")
        command = ["docker", "run", "--rm", "--network", meta["network"], "--env-file", str(runtime_env),
            "--mount", f"type=bind,source={HERE},target=/checks,readonly",
            "--mount", f"type=bind,source={raw},target=/results", "-w", "/app", "-e", "PYTHONPATH=/app",
            image, "python", "/checks/probar_seed.py", "/results/seed.json"]
        if accion(raw, "seed", command):
            raise RuntimeError("Seed falló: conservar intento; revisar logs privados")
        assert fuentes(ROOT) == meta["initial_sources"] and protegidos() == meta["protected_files"]
    finally:
        if verificar(meta) == "running":
            accion(raw, "detener", ["docker", "stop", meta["db"]])


if __name__ == "__main__":
    main()
