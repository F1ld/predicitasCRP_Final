"""Ejecución aislada y acotada de inferencia, sin hilos nativos compartidos.

Un único proceso worker persistente carga el modelo una vez y atiende de a una
solicitud. El plazo cubre escritura, cómputo y respuesta completos. Si vence, se
mata y recoge el proceso antes de liberar el cupo; la siguiente solicitud arranca
un worker nuevo. Nunca se publica una respuesta parcial ni se reintenta sola.

No hay procesos hijos al importar este módulo.
"""
from __future__ import annotations

import json
import math
import os
import queue
import subprocess
import sys
import threading

MAX_REQUEST_BYTES = 512 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_ALLOWED_ENV = {
    "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "LANG", "LC_ALL",
    "PYTHONPATH", "MODEL_REGISTRY_DIR", "MODEL_FILENAME",
}


class CapacityUnavailable(RuntimeError):
    """Ya hay una inferencia en curso; no se encola ni se duplica el cupo."""


class ComputationExpired(RuntimeError):
    """El presupuesto total de la inferencia se agotó y el worker fue terminado."""


class WorkerFailed(RuntimeError):
    """El worker no arrancó, murió o devolvió una respuesta interna inválida."""


class IsolatedExecutor:
    def __init__(self, timeout: float = 10.0, command: list[str] | None = None):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("Timeout numérico requerido")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout positivo y finito requerido")
        self.timeout = float(timeout)
        self.command = command or [sys.executable, "-m", "app.inference_worker"]
        self._slot = threading.Lock()
        self._worker_lock = threading.Lock()
        self._worker: subprocess.Popen | None = None
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def _environment(self) -> dict[str, str]:
        # No se transmite IA_API_KEY, DSN ni secretos del proceso HTTP.
        env = {k: v for k, v in os.environ.items() if k in _ALLOWED_ENV}
        env.update(
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            NUMEXPR_NUM_THREADS="1",
            PYTHONDONTWRITEBYTECODE="1",
        )
        return env

    def _terminate(self, child: subprocess.Popen) -> None:
        try:
            if child.poll() is None:
                child.kill()
        except OSError:
            pass
        for stream in (child.stdin, child.stdout):
            if stream is not None:
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass

    def _discard(self, child: subprocess.Popen) -> None:
        with self._worker_lock:
            if self._worker is child:
                self._worker = None
            self._terminate(child)

    def _spawn(self) -> subprocess.Popen:
        with self._worker_lock:
            if self._closed:
                raise CapacityUnavailable("Ejecutor cerrado")
            child = self._worker
            if child is not None and child.poll() is None:
                return child
            if child is not None:
                self._terminate(child)
                self._worker = None
            try:
                child = subprocess.Popen(
                    self.command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    env=self._environment(),
                )
            except (OSError, ValueError):
                raise WorkerFailed("No se pudo iniciar el proceso de inferencia") from None
            self._worker = child
            return child

    def _exchange(self, child: subprocess.Popen, data: bytes) -> dict:
        """Envía un mensaje y espera una línea completa con plazo total."""
        result: queue.Queue = queue.Queue(maxsize=1)

        def transfer() -> None:
            try:
                child.stdin.write(data)
                child.stdin.flush()
                result.put(("ok", child.stdout.readline(MAX_RESPONSE_BYTES + 1)))
            except BaseException as exc:  # se reporta sin propagar al hilo principal
                result.put(("error", exc))

        thread = threading.Thread(target=transfer, name="ia-transfer", daemon=True)
        thread.start()
        try:
            kind, value = result.get(timeout=self.timeout)
        except queue.Empty:
            self._discard(child)
            thread.join(timeout=2)
            raise ComputationExpired("Presupuesto total de inferencia excedido") from None
        thread.join(timeout=2)

        if kind == "error":
            self._discard(child)
            raise WorkerFailed("Fallo de comunicación con el proceso de inferencia") from None
        line = value
        if not isinstance(line, bytes) or not line or not line.endswith(b"\n"):
            self._discard(child)
            raise WorkerFailed("Proceso de inferencia sin respuesta completa")
        if len(line) > MAX_RESPONSE_BYTES:
            self._discard(child)
            raise WorkerFailed("Respuesta interna excesiva")
        try:
            payload = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            self._discard(child)
            raise WorkerFailed("Respuesta interna inválida") from None
        if child.poll() is not None:
            # La respuesta completa es válida aunque el worker haya terminado.
            self._discard(child)
        return payload

    def warm(self) -> None:
        """Arranca y valida el worker antes de aceptar tráfico."""
        if not self._slot.acquire(blocking=False):
            return
        try:
            child = self._spawn()
            payload = self._exchange(child, b'{"action":"ping"}\n')
            if not isinstance(payload, dict) or payload.get("status") != "ok":
                self._discard(child)
                raise WorkerFailed("Worker de inferencia no quedó listo")
        finally:
            self._slot.release()

    def run(self, payload: dict) -> dict:
        if not self._slot.acquire(blocking=False):
            raise CapacityUnavailable("Capacidad de inferencia ocupada")
        try:
            if self._closed:
                raise CapacityUnavailable("Ejecutor cerrado")
            try:
                data = (json.dumps(payload, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
            except (TypeError, ValueError):
                raise WorkerFailed("Solicitud interna no serializable") from None
            if len(data) > MAX_REQUEST_BYTES:
                raise WorkerFailed("Solicitud interna excesiva")
            child = self._spawn()
            result = self._exchange(child, data)
            expected = payload.get("version_modelo")
            items = result.get("items") if isinstance(result, dict) else None
            if (not isinstance(result, dict) or result.get("status") != "ok"
                    or result.get("version_modelo") != expected
                    or not isinstance(items, list)
                    or len(items) != len(payload.get("features", []))):
                self._discard(child)
                raise WorkerFailed("Respuesta del proceso de inferencia incompatible")
            return result
        finally:
            self._slot.release()

    def close(self) -> None:
        self._closed = True
        with self._worker_lock:
            child, self._worker = self._worker, None
        if child is not None:
            self._terminate(child)
        # Espera a que termine una transferencia en curso antes del apagado.
        with self._slot:
            pass
