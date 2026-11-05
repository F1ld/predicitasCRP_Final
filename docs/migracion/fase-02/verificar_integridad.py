"""Verificación final de originales, secretos privados y catálogo del clon."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "fase-00"))
from registrar_bases_y_dumps import capture


def run(*args):
    return subprocess.run(args, text=True, encoding="utf-8", capture_output=True, check=True).stdout


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "final"
    assert stage in ("final", "post_reinicio")
    output = HERE / f"integridad_{stage}.json"
    if output.exists():
        raise SystemExit("No sobrescribir evidencia")
    lab = json.loads((HERE / "laboratorio.json").read_text(encoding="utf-8"))
    prep = json.loads((HERE / "preparacion.json").read_text(encoding="utf-8"))
    private = Path(lab["private_directory"])
    originals = []
    for entry in lab["original_volumes"]:
        source = entry["source"]
        assert not run("docker", "ps", "-q", "--filter", f"volume={source}").strip(), "Original tiene escritor inesperado"
        name = source + f"-despues-{stage}.tar"
        run("docker", "run", "--rm", "--network", "none", "--mount", f"type=volume,source={source},target=/source,readonly", "--mount", f"type=bind,source={private},target=/backup", "--entrypoint", "tar", "postgres:16", "-cpf", f"/backup/{name}", "-C", "/source", ".")
        digest = hashlib.sha256((private / name).read_bytes()).hexdigest()
        originals.append({"source": source, "sha256_before": entry["sha256"], "sha256_after": digest, "identical": digest == entry["sha256"]})
    secrets = []
    with zipfile.ZipFile(prep["private_archive"]) as archive:
        for old, new in ((".env", ".env"), ("backend-predicitas/.env", "apps/backend/.env"), ("frontend-predicitas/.env", "apps/frontend/.env")):
            secrets.append({"path": new, "bytes_unchanged": archive.read(old) == (ROOT / new).read_bytes()})
    db_after = capture("predicitas-fase2-validacion-db")
    before = json.loads((HERE / "bd_antes.json").read_text(encoding="utf-8"))
    different = [key for key in before if before[key] != db_after.get(key)]
    catalog_output = HERE / ("bd_despues.json" if stage == "final" else "bd_post_reinicio.json")
    with catalog_output.open("x", encoding="utf-8") as stream:
        json.dump(db_after, stream, indent=2)
    skills = [{"path": name, "exists_and_empty": (ROOT / name).is_dir() and not list((ROOT / name).iterdir())} for name in ("apps/backend/Skills", "apps/frontend/Skills")]
    data = {"original_volumes": originals, "env_files": secrets, "skills": skills, "clone_catalog_differences": different, "same_nine_table_counts_and_fingerprints": before["counts_and_fingerprints"] == db_after["counts_and_fingerprints"], "same_catalog_and_sequences": not different}
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert all(x["identical"] for x in originals)
    assert all(x["bytes_unchanged"] for x in secrets)
    assert all(x["exists_and_empty"] for x in skills)
    assert not different, different
    print("3 volúmenes originales idénticos; 3 .env intactos; catálogo, datos y secuencias del clon conservados; Skills vacías.")


if __name__ == "__main__":
    main()
