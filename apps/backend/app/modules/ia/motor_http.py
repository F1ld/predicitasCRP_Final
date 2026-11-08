"""Adaptador HTTP interno v1, opt-in y sin persistencia ni fallback silencioso.

Posee su cliente (context manager/close); nunca recibe Request, JWT ni headers
del usuario. Un fallo invalida el lote entero, sin devolver resultados parciales.
"""
from decimal import Decimal
import math
import json
import time
from typing import Literal
from uuid import UUID, uuid4

from app.core.trazabilidad import CABECERA_SOLICITUD, id_solicitud

import httpx
from pydantic import Field, ValidationError, field_validator

from app.core.errores import Conflicto, MotorIANoDisponible
from app.modules.ia.puerto import Cerrado, FeaturesMotor, ResultadoMotor
from app.modules.ia.metadata_http import DatasetRemoto, MetricasRemotas
from app.modules.ia.metadata_motor import DatosDatasetMotor, ROTULO_PUBLICO
from app.modules.ia.schemas import MetricasModeloOut

ROTULO = "Resultado simulado — Dataset sintético acreditado (RF-056)"


class Simulado(Cerrado):
    es_simulacion: Literal[True]

    @field_validator("es_simulacion", mode="before")
    @classmethod
    def validar_simulacion(cls, value):
        if value is not True:
            raise ValueError("Rotulado sintético obligatorio")
        return value


class Umbrales(Cerrado):
    medio: Literal[0.3]
    alto: Literal[0.45]


class ModeloRemoto(Simulado):
    version_contrato: Literal["1.0"]
    version_modelo: str = Field(min_length=1, max_length=100)
    version_features: Literal["pre-cita-v1"]
    version_dataset: str = Field(min_length=1, max_length=100)
    umbrales: Umbrales
    features_autorizadas: list[str] = Field(min_length=9, max_length=9)
    rotulo_etico: Literal[ROTULO]


class PrediccionRemota(Simulado):
    version_contrato: Literal["1.0"]
    id_solicitud: UUID
    version_modelo: str = Field(min_length=1, max_length=100)
    version_features: Literal["pre-cita-v1"]
    probabilidad_no_show: float = Field(ge=0, le=1)
    nivel_riesgo: Literal["BAJO", "MEDIO", "ALTO"]
    umbrales: Umbrales
    features_snapshot: dict
    explicabilidad_resumen: str = Field(min_length=1, max_length=255)
    rotulo_etico: Literal[ROTULO]


class ItemRemoto(Cerrado):
    id_item: str
    resultado: PrediccionRemota


class LoteRemoto(Cerrado):
    version_contrato: Literal["1.0"]
    id_solicitud: UUID
    version_modelo: str = Field(min_length=1, max_length=100)
    items: list[ItemRemoto] = Field(min_length=1, max_length=100)


def _incompatible():
    return MotorIANoDisponible("Respuesta incompatible del motor IA")


def _constante_invalida(value):
    raise ValueError("JSON no finito")


class MotorHTTP:
    def __init__(self, url: str, api_key: str, *, connect: float = 2.0,
                 read: float = 15.0, write: float = 5.0, pool: float = 2.0,
                 presupuesto: float = 60.0, transport: httpx.BaseTransport | None = None):
        parsed = httpx.URL(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.host or parsed.userinfo
                or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError("URL interna absoluta sin credenciales, ruta ni query requerida")
        if not api_key or api_key.strip() != api_key or any(ord(c) < 33 or ord(c) > 126 for c in api_key):
            raise ValueError("Clave interna explícita requerida")
        for value in (connect, read, write, pool, presupuesto):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("Plazos positivos y finitos requeridos")
        self._plazos = dict(connect=connect, read=read, write=write, pool=pool)
        self._presupuesto = presupuesto
        self._client = httpx.Client(base_url=str(parsed), headers={"X-IA-API-Key": api_key},
            timeout=httpx.Timeout(**self._plazos), trust_env=False, follow_redirects=False,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5), transport=transport)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        self._client.close()

    def _solicitar(self, path, schema, *, payload=None, deadline=None):
        if self._client.is_closed:
            raise MotorIANoDisponible("Cliente IA cerrado")
        deadline = deadline if deadline is not None else time.monotonic() + self._presupuesto
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise MotorIANoDisponible("Plazo del motor IA agotado")
        timeout = httpx.Timeout(**{k: min(v, remaining) for k, v in self._plazos.items()})
        identificador = id_solicitud.get()
        headers = {CABECERA_SOLICITUD: identificador} if identificador else None
        try:
            with self._client.stream("GET" if payload is None else "POST", path,
                                     json=payload, headers=headers, timeout=timeout) as response:
                if response.status_code == 409:
                    raise Conflicto("La versión del motor cambió", codigo="VERSION_MODELO_INCOMPATIBLE")
                if response.status_code != 200:
                    # No propagar mensajes remotos ni confundir su 401 con el JWT del usuario.
                    raise MotorIANoDisponible("Motor IA temporalmente no disponible")
                if response.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
                    raise _incompatible()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 2 * 1024 * 1024 or time.monotonic() > deadline:
                        raise _incompatible()
                json.loads(bytes(body), parse_constant=_constante_invalida)
                return schema.model_validate_json(bytes(body))
        except (httpx.HTTPError, ValidationError, ValueError):
            raise MotorIANoDisponible("Comunicación o respuesta del motor IA inválida") from None

    def version(self) -> str:
        model = self._solicitar("/v1/model", ModeloRemoto)
        if set(model.features_autorizadas) != set(FeaturesMotor.model_fields):
            raise _incompatible()
        return model.version_modelo

    def metricas(self) -> MetricasModeloOut:
        remote = self._solicitar("/v1/metrics", MetricasRemotas)
        # El rótulo público histórico incluye RN16; el interno ya fue validado.
        return MetricasModeloOut(**(remote.model_dump() | {"rotulo_etico": ROTULO_PUBLICO}))

    def dataset(self) -> DatosDatasetMotor:
        remote = self._solicitar("/v1/dataset", DatasetRemoto)
        return DatosDatasetMotor(version_dataset=remote.version_dataset, semilla=remote.semilla,
            total_historicas=remote.total_historicas,
            train_size=remote.particiones.train.filas, val_size=remote.particiones.val.filas,
            test_size=remote.particiones.test.filas,
            tasa_no_show_global=round(remote.distribucion.no_show / remote.total_historicas, 4),
            **{f"tasa_no_show_{name}": round(getattr(remote.particiones, name).no_show /
                getattr(remote.particiones, name).filas, 4) for name in ("train", "val", "test")},
            control_leakage=remote.control_leakage.model_dump(), rotulo_etico=ROTULO_PUBLICO)

    @staticmethod
    def _resultado(remote, features, version, request_id):
        if remote.version_modelo != version:
            raise Conflicto("La versión del motor cambió", codigo="VERSION_MODELO_INCOMPATIBLE")
        prob = remote.probabilidad_no_show
        level = "ALTO" if prob > 0.45 else "MEDIO" if prob >= 0.3 else "BAJO"
        snapshot = features.snapshot()
        if (remote.id_solicitud != request_id or remote.features_snapshot != snapshot
                or any(type(remote.features_snapshot[k]) is not type(v) for k, v in snapshot.items())
                or abs(prob * 1000 - round(prob * 1000)) > 1e-9 or remote.nivel_riesgo != level):
            raise _incompatible()
        return ResultadoMotor(version_modelo=version, probabilidad_no_show=Decimal(str(prob)),
            nivel_riesgo=level, umbral_aplicado=Decimal("0.450"), features_snapshot=snapshot,
            explicabilidad_resumen=remote.explicabilidad_resumen)

    @staticmethod
    def _payload(version, request_id):
        if not isinstance(version, str) or not 1 <= len(version) <= 100:
            raise ValueError("Versión explícita requerida")
        return dict(version_contrato="1.0", version_features="pre-cita-v1",
                    version_modelo=version, id_solicitud=str(request_id))

    def predecir(self, features: FeaturesMotor, *, version: str) -> ResultadoMotor:
        request_id = uuid4()
        remote = self._solicitar("/v1/predict", PrediccionRemota,
            payload=self._payload(version, request_id) | {"features": features.model_dump()})
        return self._resultado(remote, features, version, request_id)

    def predecir_lote(self, features: list[FeaturesMotor], *, version: str) -> list[ResultadoMotor]:
        deadline = time.monotonic() + self._presupuesto
        results = []
        # La versión se fija para TODOS los fragmentos, nunca se redescubre/reintenta.
        for start in range(0, len(features), 100):
            group = features[start:start + 100]
            request_id = uuid4()
            remote = self._solicitar("/v1/predict-batch", LoteRemoto, deadline=deadline,
                payload=self._payload(version, request_id) | {"items": [
                    {"id_item": str(i), "features": f.model_dump()} for i, f in enumerate(group)]})
            if remote.version_modelo != version:
                raise Conflicto("La versión del motor cambió", codigo="VERSION_MODELO_INCOMPATIBLE")
            by_id = {item.id_item: item.resultado for item in remote.items}
            if (remote.id_solicitud != request_id or len(by_id) != len(remote.items)
                    or set(by_id) != {str(i) for i in range(len(group))}):
                raise _incompatible()
            results.extend(self._resultado(by_id[str(i)], f, version, request_id) for i, f in enumerate(group))
        return results
