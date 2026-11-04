"""A tiny ASGI test client. Lets tests drive the app, including streams, with no extra package."""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from starlette.types import ASGIApp, Message, Scope


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")


@dataclass
class Stream:
    """A response that is still open. Read chunks as they arrive; close to disconnect."""

    app: ASGIApp
    scope: Scope
    body: bytes
    status: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    _chunks: asyncio.Queue[bytes | None] = field(default_factory=asyncio.Queue)
    _started: asyncio.Event = field(default_factory=asyncio.Event)
    _disconnect: asyncio.Event = field(default_factory=asyncio.Event)
    _task: asyncio.Task[None] | None = None

    async def open(self) -> "Stream":
        sent = False

        async def receive() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": self.body, "more_body": False}
            await self._disconnect.wait()
            return {"type": "http.disconnect"}

        async def send(message: Message) -> None:
            if message["type"] == "http.response.start":
                self.status = message["status"]
                self.headers = {k.decode().lower(): v.decode() for k, v in message["headers"]}
                self._started.set()
            elif message["type"] == "http.response.body":
                if message.get("body"):
                    await self._chunks.put(message["body"])
                if not message.get("more_body", False):
                    await self._chunks.put(None)

        async def run() -> None:
            await self.app(self.scope, receive, send)

        self._task = asyncio.create_task(run())
        await asyncio.wait_for(self._started.wait(), timeout=5)
        return self

    async def chunk(self, timeout: float = 2.0) -> bytes | None:
        return await asyncio.wait_for(self._chunks.get(), timeout=timeout)

    async def read_all(self, timeout: float = 5.0) -> bytes:
        parts: list[bytes] = []
        while (piece := await self.chunk(timeout)) is not None:
            parts.append(piece)
        await self.finish()
        return b"".join(parts)

    async def finish(self) -> None:
        if self._task is not None:
            await asyncio.wait_for(self._task, timeout=5)

    async def close(self) -> None:
        self._disconnect.set()
        await self.finish()


class Client:
    def __init__(self, app: ASGIApp, host: str = "localhost", csrf: bool = True) -> None:
        self.app = app
        self.host = host
        self.csrf = csrf

    def _scope(self, method: str, path: str, query: str, headers: dict[str, str]) -> Scope:
        merged = {"host": self.host, **headers}
        return {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query.encode(),
            "root_path": "",
            "headers": [(k.lower().encode(), v.encode()) for k, v in merged.items()],
            "server": ("localhost", 80),
            "client": ("127.0.0.1", 50000),
        }

    def _headers(
        self, method: str, body: bytes, headers: dict[str, str] | None, chunked: bool = False
    ) -> dict[str, str]:
        out = dict(headers or {})
        if method == "POST":
            if self.csrf:
                out.setdefault("x-linkfall-request", "1")
            out.setdefault("content-type", "application/json")
        if body and not chunked:
            out.setdefault("content-length", str(len(body)))
        return out

    async def open(
        self,
        method: str,
        path: str,
        *,
        json_body: object = None,
        raw_body: bytes | None = None,
        query: str = "",
        headers: dict[str, str] | None = None,
        chunked: bool = False,
    ) -> Stream:
        body = (
            raw_body
            if raw_body is not None
            else (json.dumps(json_body).encode() if json_body is not None else b"")
        )
        scope = self._scope(method, path, query, self._headers(method, body, headers, chunked))
        return await Stream(self.app, scope, body).open()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: object = None,
        raw_body: bytes | None = None,
        query: str = "",
        headers: dict[str, str] | None = None,
    ) -> Response:
        stream = await self.open(
            method, path, json_body=json_body, raw_body=raw_body, query=query, headers=headers
        )
        body = await stream.read_all()
        return Response(stream.status, stream.headers, body)

    async def get(self, path: str, **kw: Any) -> Response:
        return await self.request("GET", path, **kw)

    async def post(self, path: str, json_body: object = None, **kw: Any) -> Response:
        return await self.request("POST", path, json_body=json_body, **kw)
