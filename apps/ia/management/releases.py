"""Registry local administrado por un único escritor; activación por reinicio.

Los hashes no son firmas: el operador debe aprobar un hash obtenido de su
pipeline interno confiable. Nunca aceptar modelos de usuarios/no confiables.
"""
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import platform
import re
from importlib.metadata import version
import uuid

import joblib

from app.core.inference import ejecutar_inferencia_individual
from app.core.model_registry import Approval, ModelRegistry
from app.schemas import FeaturesPreCita
from training.pipeline import bytes_json, sha, validar_contrato, validar_version

LIBRARIES = ("joblib", "lightgbm", "numpy", "scikit-learn", "scipy")
LEGACY_APPROVAL = Path(__file__).resolve().parents[1] / "manifests/legacy-approved.json"


def checked_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Archivo regular sin enlace requerido")
    return path.read_bytes()


def root_path(root):
    root = Path(root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("Registry absoluto existente sin enlace requerido")
    root = root.resolve()
    code = Path(__file__).resolve().parents[1]
    if root.is_relative_to(code):
        raise ValueError("Registry no permitido dentro del código")
    return root


@contextmanager
def writer(root):
    lock = root / ".writer.lock"
    with lock.open("x") as stream:
        stream.write(str(os.getpid()))
    try:
        yield
    finally:
        lock.unlink()  # Solo nuestro lock; un lock previo se rechaza, no se borra.


def read_state(root):
    path = root / "state.json"
    if path.is_symlink():
        raise ValueError("Estado enlazado no permitido")
    if not path.exists():
        return {"active": None, "previous": None}
    state = json.loads(checked_file(path))
    if set(state) != {"active", "previous"}:
        raise ValueError("Estado inválido")
    for item in state.values():
        if item is not None:
            if set(item) != {"release", "approval_sha256"}:
                raise ValueError("Referencia inválida")
            validar_version(item["release"])
            if len(item["approval_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in item["approval_sha256"]):
                raise ValueError("Hash de aprobación inválido")
    return state


def expected_state(root, expected):
    state = read_state(root)
    actual = state["active"]["release"] if state["active"] else "VACIO"
    if actual != expected:
        raise ValueError("El activo cambió; operación cancelada")
    return state


def replace_state(root, state):
    temp = root / (".state-" + uuid.uuid4().hex + ".json")
    try:
        with temp.open("xb") as stream:
            stream.write(bytes_json(state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, root / "state.json")
    finally:
        if temp.exists():
            temp.unlink()


def validate_release(root, ref):
    if not isinstance(ref["approval_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", ref["approval_sha256"]):
        raise ValueError("Hash de aprobación obligatorio")
    directory = root / "releases" / validar_version(ref["release"])
    if directory.is_symlink() or (root / "releases").is_symlink():
        raise ValueError("Release enlazada no permitida")
    approval = directory / "approval.json"
    checked_file(approval)
    checked_file(directory / "model.joblib")
    model = ModelRegistry()
    if not model.load_model(directory / "model.joblib", manifest_path=approval,
                            approval_sha256=ref["approval_sha256"]):
        raise ValueError("Release incompatible, corrupta o no aprobada")
    return model


def candidate_files(candidate, approved_hash, contracts, approved_version):
    candidate = Path(candidate)
    if candidate.is_symlink():
        raise ValueError("Candidato enlazado no permitido")
    files = {name: checked_file(candidate / name) for name in
             ("manifest.json", "candidate.joblib", "dataset-manifest.json", "metrics.json")}
    if sha(files["manifest.json"]) != approved_hash:
        raise ValueError("Hash del manifiesto no aprobado")
    manifest = json.loads(files["manifest.json"])
    validar_contrato(manifest, "ia/model-manifest.v1.schema.json", contracts)
    if manifest["estado"] != "CANDIDATO" or manifest["proposito"] != "TRAINING_RUN":
        raise ValueError("Se requiere candidato con linaje completo")
    identity = validar_version(manifest["version_modelo"])
    if identity != approved_version:
        raise ValueError("Versión no aprobada explícitamente")
    if manifest["artifact"]["relative_path"] != identity + "/candidate.joblib":
        raise ValueError("Ruta de artefacto inconsistente")
    for key, name in (("dataset_manifest_sha256", "dataset-manifest.json"), ("metrics_sha256", "metrics.json")):
        if manifest[key] != sha(files[name]):
            raise ValueError("Hash de metadata incorrecto")
    if manifest["artifact"]["sha256"] != sha(files["candidate.joblib"]):
        raise ValueError("Hash de modelo incorrecto")
    deps = manifest["dependencias"]
    if deps.get("python") != platform.python_version() or any(deps.get(k) != version(k) for k in LIBRARIES):
        raise ValueError("Dependencias incompatibles o incompletas")
    dataset = json.loads(files["dataset-manifest.json"])
    validar_contrato(dataset, "data/dataset-manifest.v1.schema.json", contracts)
    if dataset["proposito"] != "TRAINING_RUN" or dataset["version_dataset"] != manifest["version_dataset"]:
        raise ValueError("Dataset incompatible")
    metrics = json.loads(files["metrics.json"])
    if (manifest["metricas_test"]["f1_score"] < 0.82 or
            any(metrics["metricas_test"][k] != v for k, v in manifest["metricas_test"].items())):
        raise ValueError("Métricas no aprobadas")
    # Solo ahora se deserializan los mismos bytes cuyo hash aprobó el operador.
    artifact = joblib.load(io.BytesIO(files["candidate.joblib"]))
    if (artifact["version_modelo"] != identity or artifact["fecha_entrenamiento"] != manifest["entrenado_en"]
            or artifact["umbral_medio"] != manifest["umbrales"]["medio"]
            or artifact["umbral_alto"] != manifest["umbrales"]["alto"]):
        raise ValueError("Identidad/umbrales incompatibles")
    if any(artifact[k] != v for k, v in metrics.items()):
        raise ValueError("Métricas del artefacto inconsistentes")
    features = json.loads(LEGACY_APPROVAL.read_bytes())["smoke"]["features"]
    prob, level, _, explanation = ejecutar_inferencia_individual(artifact["pipeline"], FeaturesPreCita(**features))
    approval = {"sha256": sha(files["candidate.joblib"]), "version_modelo": identity,
        "version_features": manifest["version_features"], "python_major_minor": ".".join(platform.python_version_tuple()[:2]),
        "libraries": {k: deps[k] for k in LIBRARIES},
        "provenance": "Pipeline interno aprobado por hash de manifiesto " + approved_hash,
        "dataset": dataset, "smoke": {"features": features, "probabilidad_no_show": prob,
            "nivel_riesgo": level, "explicabilidad_resumen": explanation}}
    Approval.model_validate(approval)
    approved_manifest = manifest | {"estado": "APROBADO", "artifact":
        manifest["artifact"] | {"relative_path": identity + "/model.joblib"}}
    validar_contrato(approved_manifest, "ia/model-manifest.v1.schema.json", contracts)
    return identity, {"model.joblib": files["candidate.joblib"], "approval.json": bytes_json(approval),
        "manifest.json": bytes_json(approved_manifest), "candidate-manifest.json": files["manifest.json"],
        "dataset-manifest.json": files["dataset-manifest.json"], "metrics.json": files["metrics.json"]}


def install(root, identity, files, expected):
    if identity == "VACIO":
        raise ValueError("Identificador reservado para estado vacío")
    with writer(root):
        state = expected_state(root, expected)
        if state["active"]:
            validate_release(root, state["active"])
        releases = root / "releases"
        if releases.is_symlink():
            raise ValueError("Directorio releases enlazado")
        releases.mkdir(exist_ok=True)
        target = releases / identity
        if target.exists() or target.is_symlink():
            raise FileExistsError("Versión ya instalada; no se sobrescribe")
        # Un fallo conserva staging propio para diagnóstico; nunca cambia active.
        staging = releases / ("pending-" + uuid.uuid4().hex)
        staging.mkdir()
        for name, content in files.items():
            with (staging / name).open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        ref = {"release": staging.name, "approval_sha256": sha(files["approval.json"])}
        validate_release(root, ref)
        staging.rename(target)
        ref["release"] = identity
        replace_state(root, {"active": ref, "previous": state["active"]})
        return ref


def promote(*, registry, candidate, manifest_sha256, approved_version, expected, contracts):
    identity, files = candidate_files(candidate, manifest_sha256, contracts, approved_version)
    return install(root_path(registry), identity, files, expected)


def import_legacy(*, registry, model, expected):
    content = checked_file(model)
    approval = LEGACY_APPROVAL.read_bytes()  # Solo aprobación incluida en software.
    if sha(content) != json.loads(approval)["sha256"]:
        raise ValueError("Modelo no coincide con legacy confiable")
    return install(root_path(registry), "legacy-v1", {"model.joblib": content, "approval.json": approval}, expected)


def rollback(*, registry, expected, target_release=None, approval_sha256=None):
    root = root_path(registry)
    with writer(root):
        state = expected_state(root, expected)
        if (target_release is None) != (approval_sha256 is None):
            raise ValueError("Destino y hash deben proporcionarse juntos")
        target = state["previous"]
        if target_release is not None:
            target = {"release": validar_version(target_release), "approval_sha256": approval_sha256}
        if target is None:
            raise ValueError("No hay versión anterior")
        if target == state["active"]:
            raise ValueError("La versión destino ya está activa")
        validate_release(root, target)
        replace_state(root, {"active": target, "previous": state["active"]})
        return target
