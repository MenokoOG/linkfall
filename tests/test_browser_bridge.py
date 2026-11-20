import asyncio
import json
import threading
from typing import Any

import anyio.to_thread
import pytest
from fastapi import FastAPI

from api_support import create_run, make_app, run, wait_for_phase
from asgi import Client
from linkfall.browser import bridge

POST_HEADERS = {"X-Linkfall-Request": "1", "Content-Type": "application/json"}


async def call(app: FastAPI, method: str, path: str, body: object = None) -> dict[str, Any]:
    headers = POST_HEADERS if method == "POST" else {"Accept": "application/json"}
    text = None if body is None else json.dumps(body)
    reply: dict[str, Any] = json.loads(await bridge.request(app, method, path, text, headers))
    return reply


def without_ids(data: Any) -> Any:
    """Run ids are random; everything else must match."""
    if isinstance(data, dict):
        return {k: without_ids(v) for k, v in data.items() if k != "run_id"}
    if isinstance(data, list):
        return [without_ids(v) for v in data]
    return data


class Recorder:
    def __init__(self) -> None:
        self.status: list[int] = []
        self.text = ""
        self.ended = 0
        self.got_chunk = asyncio.Event()
        self.done = asyncio.Event()

    def on_start(self, status: int) -> None:
        self.status.append(status)

    def on_chunk(self, text: str) -> None:
        self.text += text
        self.got_chunk.set()

    def on_end(self) -> None:
        self.ended += 1
        self.done.set()

    def ids(self) -> list[int]:
        return [int(line[4:]) for line in self.text.splitlines() if line.startswith("id: ")]


def open_stream(app: FastAPI, path: str, rec: Recorder, last: str | None = None) -> Any:
    return bridge.open_events(app, path, rec.on_start, rec.on_chunk, rec.on_end, last)


async def bridge_turn(app: FastAPI, run_id: str, link: int) -> dict[str, Any]:
    started = await call(app, "POST", f"/api/runs/{run_id}/turns", {"link": link})
    assert started["status"] == 202, started
    state: dict[str, Any] = {}
    for _ in range(500):
        state = json.loads((await call(app, "GET", f"/api/runs/{run_id}/state"))["body"])
        if state["phase"] == "awaiting_pilot":
            break
        await asyncio.sleep(0.005)
    body = {"turn": state["turn"], "choice": "lodestar", "link": link}
    return await call(app, "POST", f"/api/runs/{run_id}/commit", body)


def test_create_turn_commit_and_404_match_the_test_client() -> None:
    async def go() -> None:
        create = {"seed": 4217, "mode": "story", "scenario": "cinder-ward", "crew": "scripted"}
        client = Client(make_app())
        expected_made = await client.post("/api/runs", create)
        client_id = expected_made.json()["run_id"]
        await client.post(f"/api/runs/{client_id}/turns", {"link": 70})
        state = await wait_for_phase(client, client_id, "awaiting_pilot")
        commit = {"turn": state["turn"], "choice": "lodestar", "link": 70}
        expected_commit = await client.post(f"/api/runs/{client_id}/commit", commit)
        expected_missing = await client.get("/api/runs/nope/state")

        app = bridge.build_app()
        made = await call(app, "POST", "/api/runs", create)
        run_id = json.loads(made["body"])["run_id"]
        committed = await bridge_turn(app, run_id, 70)
        missing = await call(app, "GET", "/api/runs/nope/state")

        for got, want in [
            (made, expected_made),
            (committed, expected_commit),
            (missing, expected_missing),
        ]:
            assert got["status"] == want.status
            assert without_ids(json.loads(got["body"])) == without_ids(want.json())
            assert got["headers"]["content-type"] == want.headers["content-type"]

    run(go)


def test_the_same_origin_check_still_runs() -> None:
    async def go() -> None:
        app = bridge.build_app()
        body = json.dumps({"seed": 1, "mode": "story", "scenario": "cinder-ward"})
        bare = json.loads(await bridge.request(app, "POST", "/api/runs", body, {}))
        assert bare["status"] == 403
        spoofed = {**POST_HEADERS, "Host": "evil.example", "Origin": "http://evil.example"}
        refused = json.loads(await bridge.request(app, "POST", "/api/runs", body, spoofed))
        assert refused["status"] == 403  # Host is the bridge's, so the Origin can't match it

    run(go)


def test_no_model_means_scripted_only() -> None:
    async def go() -> None:
        app = bridge.build_app()
        health = json.loads((await call(app, "GET", "/api/health"))["body"])
        assert "not_configured" in json.dumps(health)
        forced = await call(
            app,
            "POST",
            "/api/runs",
            {"seed": 1, "mode": "story", "scenario": "cinder-ward", "crew": "model"},
        )
        assert forced["status"] == 503

    run(go)


def test_paths_outside_the_api_are_refused() -> None:
    app = bridge.build_app()
    with pytest.raises(ValueError, match="/api/"):
        asyncio.run(bridge.request(app, "GET", "/index.html"))
    with pytest.raises(ValueError, match="/api/"):
        bridge.EventStream(app, "/x", print, print, print)


def test_a_finished_stream_reads_whole_through_request() -> None:
    async def go() -> None:
        app = make_app()
        run_id = await create_run(Client(app))
        reply = await call(app, "GET", f"/api/runs/{run_id}/events?follow=false")
        assert reply["status"] == 200
        assert reply["headers"]["content-type"].startswith("text/event-stream")
        assert reply["body"].startswith("id: ")

    run(go)


def test_the_event_stream_delivers_rows_and_ends_once() -> None:
    async def go() -> None:
        app = make_app()
        run_id = await create_run(Client(app))
        await bridge_turn(app, run_id, 55)
        rec = Recorder()
        open_stream(app, f"/api/runs/{run_id}/events?follow=false", rec)
        await asyncio.wait_for(rec.done.wait(), timeout=5)
        assert rec.status == [200]
        assert rec.ended == 1
        ids = rec.ids()
        assert ids
        assert ids == sorted(ids)
        assert "event: decision" in rec.text

        resumed = Recorder()
        open_stream(app, f"/api/runs/{run_id}/events?follow=false", resumed, str(ids[2]))
        await asyncio.wait_for(resumed.done.wait(), timeout=5)
        assert resumed.ids() == ids[3:]

    run(go)


def test_the_event_stream_stops_on_disconnect() -> None:
    async def go() -> None:
        app = make_app()
        run_id = await create_run(Client(app))
        rec = Recorder()
        stream = open_stream(app, f"/api/runs/{run_id}/events", rec)
        await asyncio.wait_for(rec.got_chunk.wait(), timeout=5)  # the run's opening rows
        assert rec.ended == 0  # a live run keeps the stream open
        await asyncio.wait_for(stream.close(), timeout=5)
        assert rec.ended == 1

    run(go)


def test_an_unknown_run_streams_a_404() -> None:
    async def go() -> None:
        rec = Recorder()
        open_stream(make_app(), "/api/runs/nope/events", rec)
        await asyncio.wait_for(rec.done.wait(), timeout=5)
        assert rec.status == [404]
        assert json.loads(rec.text)["error"] == "no such run"
        assert rec.ended == 1

    run(go)


def test_thread_patches_run_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    # Register the originals with monkeypatch so they come back after the test.
    monkeypatch.setattr(asyncio, "to_thread", asyncio.to_thread)
    monkeypatch.setattr(anyio.to_thread, "run_sync", anyio.to_thread.run_sync)
    bridge.install_thread_patches()
    seen: list[int] = []

    def work(name: str, suffix: str = "") -> str:
        seen.append(threading.get_ident())
        return name + suffix

    async def go() -> None:
        assert await asyncio.to_thread(work, "a", suffix="!") == "a!"
        assert await anyio.to_thread.run_sync(work, "b", abandon_on_cancel=True) == "b"

    run(go)
    assert seen == [threading.get_ident()] * 2  # both ran on this thread


def test_start_page_patches_and_serves_json_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asyncio, "to_thread", asyncio.to_thread)
    monkeypatch.setattr(anyio.to_thread, "run_sync", anyio.to_thread.run_sync)
    page = bridge.start_page()
    assert asyncio.to_thread is bridge._inline_to_thread

    async def go() -> None:
        create = json.dumps({"seed": 4217, "mode": "story", "scenario": "cinder-ward"})
        made = json.loads(await page.request("POST", "/api/runs", create, json.dumps(POST_HEADERS)))
        assert made["status"] == 201
        run_id = json.loads(made["body"])["run_id"]
        health = json.loads(await page.request("GET", "/api/health", None, None))
        assert health["status"] == 200
        with pytest.raises(TypeError, match="JSON object"):
            await page.request("GET", "/api/health", None, "[1]")

        rec = Recorder()
        page.open_events(
            f"/api/runs/{run_id}/events?follow=false", None, rec.on_start, rec.on_chunk, rec.on_end
        )
        await asyncio.wait_for(rec.done.wait(), timeout=5)
        assert rec.status == [200]
        assert rec.ids()

    run(go)
