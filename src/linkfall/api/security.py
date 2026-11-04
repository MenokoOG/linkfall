"""Pure ASGI middleware and the same-origin check (ASVS 5.0.0: 3.2.1, 3.4.2, 3.5.1, 3.5.3)."""

from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSRF_HEADER = "x-linkfall-request"

SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (
        b"content-security-policy",
        b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        b"connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
        b"form-action 'none'; frame-ancestors 'none'",
    ),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"x-frame-options", b"DENY"),
)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        api = scope["path"].startswith("/api")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message["headers"])
                present = {name.lower() for name, _ in headers}
                headers += [(n, v) for n, v in SECURITY_HEADERS if n not in present]
                if api and b"cache-control" not in present:
                    headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodyLimitMiddleware:
    """Refuse request bodies over the limit before the app reads them."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            await _too_large(send)
            return
        seen = 0
        refused = False

        async def counted() -> Message:
            nonlocal seen, refused
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    refused = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        sent_start = False

        async def guarded_send(message: Message) -> None:
            nonlocal sent_start
            if refused and not sent_start:
                sent_start = True
                await _too_large(send)
                return
            if refused:
                return
            sent_start = sent_start or message["type"] == "http.response.start"
            await send(message)

        await self.app(scope, counted, guarded_send)


async def _too_large(send: Send) -> None:
    body = b'{"error":"request body is too large"}'
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def require_same_origin(request: Request) -> None:
    """For every state-changing route: a custom header, and an Origin that matches the Host."""
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail=f"missing {CSRF_HEADER} header")
    origin = request.headers.get("origin")
    if origin is not None and urlsplit(origin).netloc != request.headers.get("host", ""):
        raise HTTPException(status_code=403, detail="cross-origin request refused")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=403, detail="cross-site request refused")
