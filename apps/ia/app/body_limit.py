"""Recepción ASGI acotada: no acumula el resto de un streaming excesivo."""
import anyio
from starlette.responses import JSONResponse

from app.config import MAX_BODY_SIZE_BYTES


class MaxBodySizeMiddleware:
    def __init__(self, app, receive_timeout=10):
        self.app = app
        self.receive_timeout = receive_timeout

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def reject(status, code, message):
            response = JSONResponse(status_code=status, content={"error": {
                "codigo": code, "mensaje": message, "campos": {}}})
            await response(scope, receive, send)

        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
            if length < 0:
                raise ValueError
        except ValueError:
            return await reject(422, "VALIDACION", "Content-Length inválido")
        if length > MAX_BODY_SIZE_BYTES:
            return await reject(413, "SOLICITUD_DEMASIADO_GRANDE", "El cuerpo supera 256 KiB")
        chunks, size = [], 0
        try:
            with anyio.fail_after(self.receive_timeout):
                while True:
                    event = await receive()
                    if event["type"] == "http.disconnect":
                        return
                    chunk = event.get("body", b"")
                    size += len(chunk)
                    if size > MAX_BODY_SIZE_BYTES:
                        return await reject(413, "SOLICITUD_DEMASIADO_GRANDE", "El cuerpo supera 256 KiB")
                    chunks.append(chunk)
                    if not event.get("more_body", False):
                        break
        except TimeoutError:
            return await reject(422, "VALIDACION", "Tiempo máximo de recepción excedido")

        replayed = False
        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)
