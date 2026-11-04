"""Server-sent events: the event log, streamed. A reconnect resumes with Last-Event-ID."""

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator, Callable

from fastapi import Request

from linkfall.eventlog.store import EventStore
from linkfall.eventlog.types import LogRow

_EVENT_NAME = re.compile(r"[a-z_]{1,32}")


def frame(row: LogRow) -> str:
    """One SSE message. The event name comes from the database, so it is checked first."""
    name = row.kind if _EVENT_NAME.fullmatch(row.kind) else "unknown"
    data = json.dumps(
        {"id": row.id, "turn": row.turn, "kind": row.kind, "payload": row.payload},
        separators=(",", ":"),
    )
    return f"id: {row.id}\nevent: {name}\ndata: {data}\n\n"


async def stream(
    store: EventStore,
    run_id: str,
    after_id: int,
    *,
    follow: bool,
    finished: Callable[[], bool],
    request: Request,
    poll_s: float,
    heartbeat_s: float,
    max_s: float,
) -> AsyncIterator[str]:
    """Send every row after `after_id`. Stop when the run is over and drained, the client leaves,
    or `max_s` passes (the browser reconnects and resumes)."""
    last = after_id
    started = last_sent = time.monotonic()
    while True:
        rows = await asyncio.to_thread(store.read_rows, run_id, last)
        for row in rows:
            yield frame(row)
            last = row.id
        if rows:
            last_sent = time.monotonic()
            continue
        if not follow:
            return
        if finished():
            if not await asyncio.to_thread(store.read_rows, run_id, last):
                return
            continue
        now = time.monotonic()
        if now - started > max_s or await request.is_disconnected():
            return
        if now - last_sent > heartbeat_s:
            yield ": keep-alive\n\n"
            last_sent = now
        await asyncio.sleep(poll_s)
