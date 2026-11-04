"""Builders shared by the API tests."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import FastAPI

from asgi import Client
from linkfall.api.app import create_app
from linkfall.api.config import DEFAULT_HOSTS, ApiConfig
from linkfall.eventlog.store import EventStore
from linkfall.supervisor.fake_client import FakeClient
from linkfall.supervisor.modelclient import ModelRequest, ModelResponse


class FakeModel:
    """A model client that looks like HttpModelClient to the registry, with no network."""

    def __init__(self, up: bool = True) -> None:
        self.up = up
        self._inner = FakeClient(lambda _r: '{"action":"hold_shield","say":"Holding."}')

    async def healthy(self) -> bool:
        return self.up

    async def complete(self, request: ModelRequest) -> ModelResponse:
        return await self._inner.complete(request)


def config(**overrides: Any) -> ApiConfig:
    base: dict[str, Any] = {
        "allowed_hosts": (*DEFAULT_HOSTS, "testserver"),
        "stream_poll_s": 0.01,
        "stream_heartbeat_s": 0.05,
    }
    return ApiConfig(**{**base, **overrides})


def make_app(
    store: EventStore | None = None, model: FakeModel | None = None, **overrides: Any
) -> FastAPI:
    return create_app(config(**overrides), store=store or EventStore(), model_client=model)


def run(test: Callable[[], Coroutine[Any, Any, None]]) -> None:
    asyncio.run(test())


async def wait_for_phase(
    client: Client, run_id: str, phase: str, timeout: float = 5.0
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        state: dict[str, Any] = (await client.get(f"/api/runs/{run_id}/state")).json()
        if state["phase"] == phase:
            return state
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"never reached {phase}; last state {state}")
        await asyncio.sleep(0.01)


async def create_run(client: Client, **body: Any) -> str:
    payload = {"seed": 4217, "mode": "story", "scenario": "cinder-ward", **body}
    response = await client.post("/api/runs", payload)
    assert response.status == 201, response.text
    run_id: str = response.json()["run_id"]
    return run_id


async def play_turn(client: Client, run_id: str, link: int, **commit: Any) -> dict[str, Any]:
    started = await client.post(f"/api/runs/{run_id}/turns", {"link": link})
    assert started.status == 202, started.text
    state = await wait_for_phase(client, run_id, "awaiting_pilot")
    body = {"turn": state["turn"], "choice": "lodestar", "link": link, **commit}
    response = await client.post(f"/api/runs/{run_id}/commit", body)
    assert response.status == 200, response.text
    result: dict[str, Any] = response.json()
    return result
