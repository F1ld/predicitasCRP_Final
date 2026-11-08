"""Fase 6 A: pipeline sin BD ni promoción, solo directorios temporales."""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import joblib
import pytest
from jsonschema.exceptions import ValidationError

from training import pipeline as p

CONTRACTS = Path("/contracts")
FECHA = datetime(2026, 11, 7, tzinfo=timezone.utc)


def generate(parent, **changes):
    args = dict(version_dataset="qa-f6", semilla=42, fecha_corte=date(2026, 10, 29),
        generado_en=FECHA, fuente="SINTETICO_GENERADO", directorio=parent,
        contracts=CONTRACTS, proximas=80)
    return p.generar(**(args | changes))


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("f6"))


def test_generation_and_splits_are_reproducible(dataset, tmp_path):
    second = generate(tmp_path)
    for path in dataset.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    rows, manifest, _ = p.validar_dataset(dataset, contracts=CONTRACTS)
    assert len(rows) == 1000
    assert [manifest["particiones"][name]["filas"] for name in ("train", "val", "test")] == [700, 150, 150]
    seed = json.loads((dataset / "seed-manifest.json").read_bytes())
    assert seed["filas"] == 1080
    assert seed["sha256"] == p.sha((dataset / "seed.csv").read_bytes())


@pytest.mark.parametrize("changes", [dict(semilla=43), dict(fuente="BD"),
    dict(proximas=-1), dict(proximas=4001), dict(generado_en=datetime(2026, 11, 7)),
    dict(version_dataset="../escape"), dict(version_dataset=".."), dict(version_dataset="a/b")])
def test_rejects_implicit_or_unsafe_parameters(tmp_path, changes):
    with pytest.raises(ValueError):
        generate(tmp_path, **changes)
    assert not list(tmp_path.iterdir())


def test_no_overwrite(dataset):
    before = {f.name: f.read_bytes() for f in dataset.iterdir()}
    with pytest.raises(FileExistsError):
        generate(dataset.parent)
    assert before == {f.name: f.read_bytes() for f in dataset.iterdir()}


def test_registry_write_is_forbidden(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "MODEL_REGISTRY_DIR", tmp_path)
    with pytest.raises(ValueError, match="registry"):
        generate(tmp_path)


@pytest.mark.parametrize("filename", ["raw.jsonl", "train.jsonl", "val.jsonl", "test.jsonl"])
def test_detects_tampering(dataset, tmp_path, filename):
    for f in dataset.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes())
    with (tmp_path / filename).open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError):
        p.validar_dataset(tmp_path, contracts=CONTRACTS)


def test_manifest_counts_are_verified(dataset, tmp_path):
    for f in dataset.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes())
    path = tmp_path / "manifest.json"
    value = json.loads(path.read_bytes())
    value["distribucion"]["no_show"] += 1
    path.write_bytes(p.bytes_json(value))
    with pytest.raises(ValueError, match="Conteos"):
        p.validar_dataset(tmp_path, contracts=CONTRACTS)


def test_duplicate_ids_and_post_cutoff_are_rejected(dataset):
    rows = [json.loads(line) for line in (dataset / "raw.jsonl").read_bytes().splitlines()]
    cutoff = datetime(2026, 10, 30, tzinfo=timezone.utc)
    rows[1] = rows[0]
    with pytest.raises(ValueError, match="duplicado"):
        p.preparar(rows, corte=cutoff, contracts=CONTRACTS)
    with pytest.raises(ValueError, match="corte"):
        p.preparar(rows, corte=datetime(2020, 1, 1, tzinfo=timezone.utc), contracts=CONTRACTS)


def test_extra_features_rejected(dataset):
    rows = [json.loads(line) for line in (dataset / "raw.jsonl").read_bytes().splitlines()]
    rows[0]["features"]["target_no_show"] = 1
    with pytest.raises(ValidationError):
        p.preparar(rows, corte=FECHA, contracts=CONTRACTS)


def test_real_training_candidate_lineage_and_no_activation(dataset, tmp_path):
    before = {f.name: f.read_bytes() for f in dataset.iterdir()}
    target = p.entrenar_candidato(dataset=dataset, version_modelo="qa-model-f6", fecha=FECHA,
                                  directorio=tmp_path, contracts=CONTRACTS)
    manifest = json.loads((target / "manifest.json").read_bytes())
    p.validar_contrato(manifest, "ia/model-manifest.v1.schema.json", CONTRACTS)
    assert manifest["estado"] == "CANDIDATO"
    assert manifest["metricas_test"]["f1_score"] >= 0.82
    assert manifest["artifact"]["sha256"] == p.sha((target / "candidate.joblib").read_bytes())
    assert manifest["dataset_manifest_sha256"] == p.sha((dataset / "manifest.json").read_bytes())
    assert manifest["metrics_sha256"] == p.sha((target / "metrics.json").read_bytes())
    artifact = joblib.load(target / "candidate.joblib")  # solo candidato propio de esta prueba
    assert artifact["version_modelo"] == "qa-model-f6"
    assert before == {f.name: f.read_bytes() for f in dataset.iterdir()}
    with pytest.raises(FileExistsError):
        p.entrenar_candidato(dataset=dataset, version_modelo="qa-model-f6", fecha=FECHA,
                            directorio=tmp_path, contracts=CONTRACTS)


def test_cli_generate_validate_and_failure(tmp_path):
    base = [sys.executable, "-B", "-m", "training.cli", "--contracts-dir", str(CONTRACTS)]
    args = ["generar", "--version-dataset", "cli-qa", "--semilla", "42", "--fecha-corte", "2026-10-29",
        "--generado-en", FECHA.isoformat(), "--fuente", "SINTETICO_GENERADO", "--proximas", "0",
        "--directorio", str(tmp_path)]
    assert subprocess.run(base + args, capture_output=True).returncode == 0
    assert subprocess.run(base + ["validar", "--dataset", str(tmp_path / "cli-qa")], capture_output=True).returncode == 0
    assert subprocess.run(base + args, capture_output=True).returncode == 1
