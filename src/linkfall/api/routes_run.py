"""Run-level routes: create, read state, stream the log, replay, health."""

import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

import linkfall
from linkfall.api.registry import (
    ActiveRun,
    ModelUnavailableError,
    Phase,
    Registry,
    RegistryFullError,
)
from linkfall.api.schemas import CreateRun, state_json
from linkfall.api.security import require_same_origin
from linkfall.api.sse import stream
from linkfall.engine.scenario import SCENARIOS
from linkfall.eventlog.replay import replay
from linkfall.eventlog.store import EventStore, RunNotFoundError

router = APIRouter(prefix="/api")
_RUN_ID = re.compile(r"[A-Za-z0-9_-]{8,40}")


def registry_of(request: Request) -> Registry:
    registry: Registry = request.app.state.registry
    return registry


def store_of(request: Request) -> EventStore:
    store: EventStore = request.app.state.store
    return store


def run_id_of(run_id: str) -> str:
    if not _RUN_ID.fullmatch(run_id):
        raise HTTPException(status_code=404, detail="no such run")
    return run_id


def known_run(request: Request, run_id: str = Depends(run_id_of)) -> str:
    try:
        store_of(request).get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="no such run") from exc
    return run_id


def active_summary(run_id: str, active: ActiveRun) -> dict[str, object]:
    state = active.run.state
    return {
        "run_id": run_id,
        "mode": active.run.mode.value,
        "seed": active.seed,
        "scenario": active.scenario,
        "max_turns": SCENARIOS[active.scenario].max_turns,
        "phase": active.phase.value,
        "turn": state.turn,
        "over": state.over,
        "outcome": state.outcome.value if state.outcome else None,
        "state": state_json(state),
        "error": active.error,
    }


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    registry = registry_of(request)
    if not registry.model_configured:
        model = "not_configured"
    else:
        model = "up" if await registry.model_up() else "down"
    return {"status": "ok", "version": linkfall.__version__, "model": model}


@router.post("/runs", status_code=201, dependencies=[Depends(require_same_origin)])
async def create_run(body: CreateRun, request: Request) -> dict[str, object]:
    try:
        run_id, active, crew = await registry_of(request).create(
            body.seed, body.mode, body.scenario, body.crew
        )
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RegistryFullError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return {**active_summary(run_id, active), "crew": crew}


@router.get("/runs/{run_id}/state")
async def get_state(request: Request, run_id: str = Depends(known_run)) -> dict[str, object]:
    active = registry_of(request).get(run_id)
    if active is not None:
        return active_summary(run_id, active)
    store = store_of(request)
    header = store.get_run(run_id)
    result = await asyncio.to_thread(replay, store, run_id)
    scenario = SCENARIOS.get(header.scenario)
    closed: dict[str, object] = {
        "run_id": run_id,
        "mode": header.mode.value,
        "seed": header.seed,
        "scenario": header.scenario,
        "max_turns": scenario.max_turns if scenario else None,
        "phase": "closed",
        "replay_ok": result.ok,
    }
    if result.state is not None:
        closed |= {
            "turn": result.state.turn,
            "over": result.state.over,
            "outcome": result.state.outcome.value if result.state.outcome else None,
            "state": state_json(result.state),
        }
    return closed


@router.get("/runs/{run_id}/replay")
async def replay_run(request: Request, run_id: str = Depends(known_run)) -> dict[str, object]:
    result = await asyncio.to_thread(replay, store_of(request), run_id)
    failure = (
        {"row_id": result.failure.row_id, "reason": result.failure.reason}
        if result.failure
        else None
    )
    return {
        "ok": result.ok,
        "fingerprint": result.fingerprint,
        "turns": result.turns,
        "failure": failure,
    }


@router.get("/runs/{run_id}/events")
async def events(
    request: Request,
    run_id: str = Depends(known_run),
    after: int = Query(0, ge=0),
    follow: bool = True,
) -> StreamingResponse:
    resume = request.headers.get("last-event-id")
    if resume is not None:
        if not resume.isdigit():
            raise HTTPException(status_code=400, detail="Last-Event-ID must be a number")
        after = max(after, int(resume))
    config = request.app.state.config
    registry = registry_of(request)

    def finished() -> bool:
        active = registry.get(run_id)
        return active is None or (active.run.state.over and active.phase is Phase.IDLE)

    body = stream(
        store_of(request),
        run_id,
        after,
        follow=follow,
        finished=finished,
        request=request,
        poll_s=config.stream_poll_s,
        heartbeat_s=config.stream_heartbeat_s,
        max_s=config.stream_max_s,
    )
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
