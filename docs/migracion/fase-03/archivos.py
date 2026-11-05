"""Preparación y centralización conservadora; no conecta a BD ni carga Joblib."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
MODEL = "apps/backend/app/modules/ia/artifacts/modelo_predicitas_v1.joblib"
COPIES = {
    "citas_para_importar_variado.csv": "data/samples/importacion/citas_para_importar_variado.csv",
    "apps/backend/data/citas_demo.csv": "data/samples/importacion/citas_demo.csv",
    MODEL: "artifacts/models/legacy-import/modelo_predicitas_v1.joblib",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def preparar():
    if (HERE / "preparacion.json").exists():
        raise SystemExit("No sobrescribir preparación")
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    names = sorted(set(filter(None, tracked)) | {".env", "apps/backend/.env", "apps/frontend/.env", MODEL})
    files = [{"path": name, "sha256": sha(ROOT / name), "bytes": (ROOT / name).stat().st_size} for name in names]
    old = json.loads((HERE.parent / "fase-02/respaldo_cierre.json").read_text(encoding="utf-8"))
    if sha(Path(old["private_archive"])) != old["sha256"]:
        raise SystemExit("Respaldo de fase 2 no coincide")
    private = Path(os.environ["LOCALAPPDATA"]) / "PrediCitasBackups" / ("fase3-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    private.mkdir(parents=True, exist_ok=False)
    principal = f"{os.environ['USERDOMAIN']}\\{os.environ['USERNAME']}:(OI)(CI)F"
    subprocess.run(["icacls", str(private), "/inheritance:r", "/grant:r", principal], check=True, capture_output=True)
    archive = private / "antes_fase3_privado.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as output:
        for name in names:
            output.write(ROOT / name, name)
    write_new(HERE / "preparacion.json", {"date_utc": datetime.now(timezone.utc).isoformat(), "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "private_archive": str(archive), "archive_sha256": sha(archive), "phase2_backup_reverified": True, "files": files, "risk_policy": "Sin borrar CSV, sobrescribir artefactos, cambiar credenciales, restaurar/sembrar/migrar principal ni promover/reentrenar sin confirmación."})
    print(f"Respaldo privado y hashes preparados: {len(files)} archivos")


def centralizar():
    if (HERE / "copias.json").exists():
        raise SystemExit("Centralización ya registrada")
    prep = json.loads((HERE / "preparacion.json").read_text(encoding="utf-8"))
    hashes = {item["path"]: item["sha256"] for item in prep["files"]}
    for source, target in COPIES.items():
        if (ROOT / target).exists() or sha(ROOT / source) != hashes[source]:
            raise SystemExit(f"Origen cambió o destino existe: {source}")
    duplicate = ROOT / "apps/backend/data/citas_para_importar_variado.csv"
    assert sha(duplicate) == sha(ROOT / "citas_para_importar_variado.csv")
    for folder in ("data/samples/importacion", "data/fixtures", "data/raw", "data/processed", "data/manifests", "artifacts/models/legacy-import", "artifacts/reports", "runtime/exports", "runtime/tmp", "runtime/test-results"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    records = []
    for source, target in COPIES.items():
        with (ROOT / source).open("rb") as src, (ROOT / target).open("xb") as dst:
            shutil.copyfileobj(src, dst)
        assert sha(ROOT / source) == sha(ROOT / target)
        if source == MODEL:
            (ROOT / target).chmod(stat.S_IREAD)  # Solo copia nueva; no cambia artefacto activo.
        records.append({"source": source, "destination": target, "sha256": sha(ROOT / target), "source_preserved": True, "identical": True, "destination_readonly_attribute": source == MODEL})
    write_new(HERE / "copias.json", {"copies": records, "legacy_csv_copies_preserved": True, "model_loaded_or_promoted": False, "note": "Ubicación canónica nueva; copias previas de CSV solo compatibilidad congelada. Joblib legacy es copia de preservación, no modelo activo ni versión aprobada."})
    print("Muestras canónicas y copia legacy verificadas; originales conservados.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accion", choices=("preparar", "centralizar"))
    args = parser.parse_args()
    preparar() if args.accion == "preparar" else centralizar()
