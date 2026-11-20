"""Calls the API app in-process, the way the page does under Pyodide (ADR 0012).

The page has one thread, so the two thread hand-offs the app uses run inline. Requests and the
event stream go through the full ASGI app: same routes, same checks, same error shapes.
"""

import asyncio
import codecs
import json
from collections.abc import Callable, Mapping
from typing import Any

import anyio.to_thread
from anyio import CapacityLimiter
from fastapi import FastAPI
from starlette.types import Message, Scope

from linkfall.api.app import create_app
from linkfall.api.config import ApiConfig
from linkfall.eventlog.store import EventStore
from linkfall.range.store import RangeStore

HOST = "localhost"


async def _inline_to_thread[**P, T](
    func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs
) -> T:
    return func(*args, **kwargs)


async def _inline_run_sync[*Ts, T](
    func: Callable[[*Ts], T],
    *args: *Ts,
    abandon_on_cancel: bool = False,
    cancellable: bool | None = None,
    limiter: CapacityLimiter | None = None,
) -> T:
    return func(*args)  # the options only matter with threads


def install_thread_patches() -> None:
    """Make asyncio.to_thread and anyio.to_thread.run_sync run their function inline.

    Only the page calls this. Pyodide has no threads, and nothing else needs changing.
    """
    asyncio.to_thread = _inline_to_thread
    anyio.to_thread.run_sync = _inline_run_sync


def build_app() -> FastAPI:
    """The app with both logs in memory and no model, so only the scripted crew is offered."""
    return create_app(ApiConfig(model_url=None), store=EventStore(), range_store=RangeStore())


def _scope(method: str, path: str, headers: Mapping[str, str]) -> Scope:
    path, _, query = path.partition("?")
    # The caller's headers pass through so the same-origin check still runs; Host is ours.
    merged = {k.lower(): v for k, v in headers.items() if k.lower() != "host"}
    merged["host"] = HOST
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
        "headers": [(k.encode(), v.encode()) for k, v in merged.items()],
        "server": (HOST, 80),
        "client": ("127.0.0.1", 1),
    }


def _headers(message: Message) -> dict[str, str]:
    return {k.decode().lower(): v.decode() for k, v in message.get("headers", [])}


async def request(
    app: FastAPI,
    method: str,
    path: str,
    body: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> str:
    """One request. Returns JSON text: {"status", "headers", "body"}, body as text."""
    if not path.startswith("/api/"):
        raise ValueError("API paths must start with /api/")
    raw = (body or "").encode()
    sent_headers = dict(headers or {})
    if raw:
        sent_headers["content-length"] = str(len(raw))
    out: dict[str, Any] = {"status": 0, "headers": {}}
    chunks: list[bytes] = []
    done = asyncio.Event()
    delivered = False

    async def receive() -> Message:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": raw, "more_body": False}
        await done.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        if message["type"] == "http.response.start":
            out["status"] = message["status"]
            out["headers"] = _headers(message)
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                done.set()

    try:
        await app(_scope(method, path, sent_headers), receive, send)
    finally:
        done.set()
    out["body"] = b"".join(chunks).decode("utf-8", errors="replace")
    return json.dumps(out)


class EventStream:
    """One open event stream. Calls on_start(status), then on_chunk(text) per piece, then
    on_end() once. close() disconnects, the way a browser tab closing an EventSource does."""

    def __init__(
        self,
        app: FastAPI,
        path: str,
        on_start: Callable[[int], object],
        on_chunk: Callable[[str], object],
        on_end: Callable[[], object],
        last_event_id: str | None = None,
    ) -> None:
        if not path.startswith("/api/"):
            raise ValueError("API paths must start with /api/")
        headers = {"accept": "text/event-stream"}
        if last_event_id is not None:
            headers["last-event-id"] = last_event_id
        self._scope = _scope("GET", path, headers)
        self._app = app
        self._on_start = on_start
        self._on_chunk = on_chunk
        self._on_end = on_end
        self._disconnect = asyncio.Event()
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._task: asyncio.Task[None] | None = None

    def start(self) -> "EventStream":
        self._task = asyncio.get_running_loop().create_task(self._run())
        return self

    async def _run(self) -> None:
        delivered = False

        async def receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await self._disconnect.wait()
            return {"type": "http.disconnect"}

        async def send(message: Message) -> None:
            if message["type"] == "http.response.start":
                self._on_start(message["status"])
            elif message["type"] == "http.response.body":
                text = self._decoder.decode(message.get("body", b""))
                if text:
                    self._on_chunk(text)

        try:
            await self._app(self._scope, receive, send)
        finally:
            self._on_end()

    async def close(self) -> None:
        self._disconnect.set()
        if self._task is not None:
            await self._task


def open_events(
    app: FastAPI,
    path: str,
    on_start: Callable[[int], object],
    on_chunk: Callable[[str], object],
    on_end: Callable[[], object],
    last_event_id: str | None = None,
) -> EventStream:
    """Start an event stream on the running loop and return it, so the page can close it."""
    return EventStream(app, path, on_start, on_chunk, on_end, last_event_id).start()


class PageBridge:
    """What the page holds: the app and the two calls, in shapes JavaScript can pass in."""

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def request(
        self, method: str, path: str, body: str | None, headers_json: str | None
    ) -> str:
        headers = json.loads(headers_json) if headers_json else {}
        if not isinstance(headers, dict):
            raise TypeError("headers must be a JSON object")
        return await request(
            self.app, method, path, body, {str(k): str(v) for k, v in headers.items()}
        )

    def open_events(
        self,
        path: str,
        last_event_id: str | None,
        on_start: Callable[[int], object],
        on_chunk: Callable[[str], object],
        on_end: Callable[[], object],
    ) -> EventStream:
        return open_events(self.app, path, on_start, on_chunk, on_end, last_event_id)


def start_page() -> PageBridge:
    """The page's one Python call at start-up: patch the thread hand-offs, then build the app."""
    install_thread_patches()
    return PageBridge(build_app())
