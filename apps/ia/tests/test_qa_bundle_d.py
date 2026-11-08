"""Generación explícita reproducible de fixtures; nunca importa backend."""
import hashlib
import json
import os
import subprocess
import sys


def test_bundle_is_explicit_reproducible_and_never_overwritten(tmp_path):
    env = dict(os.environ)
    env.pop("IA_API_KEY", None)
    env.pop("DATABASE_URL", None)
    command = [sys.executable, "-B", "-m", "datasets.qa_bundle", "--salida"]
    a, b = tmp_path / "a", tmp_path / "b"
    for target in (a, b):
        result = subprocess.run(command + [str(target)], env=env, capture_output=True)
        assert result.returncode == 0, result.stderr
    assert {p.name: p.read_bytes() for p in a.iterdir()} == {p.name: p.read_bytes() for p in b.iterdir()}
    manifest = json.loads((a / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["es_simulacion"]
    assert manifest["files"]["rendimiento"]["rows"] == 5000
    assert manifest["files"]["citas"]["rows"] == 44
    assert manifest["files"]["predictor"]["rows"] == 1080
    for key, info in manifest["files"].items():
        assert hashlib.sha256((a / (key + ".csv")).read_bytes()).hexdigest() == info["sha256"]
    before = (a / "manifest.json").read_bytes()
    assert subprocess.run(command + [str(a)], env=env, capture_output=True).returncode != 0
    assert (a / "manifest.json").read_bytes() == before
