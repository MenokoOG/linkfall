"""The pilot's inputs: open a turn, commit a choice, dismiss a proposal."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from linkfall.api.registry import ActiveRun, Phase
from linkfall.api.routes_run import registry_of, run_id_of
from linkfall.api.schemas import Commit, Dismiss, StartTurn, state_json
from linkfall.api.security import require_same_origin
from linkfall.eventlog.turnrows import decision_payload
from linkfall.supervisor.choices import LodestarActs, ManualPick, PilotChoice, Sign
from linkfall.supervisor.run import SupervisorError
from linkfall.supervisor.session import TurnResult

router = APIRouter(prefix="/api", dependencies=[Depends(require_same_origin)])
log = logging.getLogger("linkfall.api")


def active_run(request: Request, run_id: str = Depends(run_id_of)) -> tuple[str, ActiveRun]:
    active = registry_of(request).get(run_id)
    if active is None:
        raise HTTPException(status_code=409, detail="this run is not active on this server")
    return run_id, active


async def collect(run_id: str, active: ActiveRun, link: int) -> None:
    try:
        active.session = await active.run.begin_turn(link)
        active.phase = Phase.AWAITING_PILOT
    except Exception:
        log.exception("turn collection failed", extra={"run_id": run_id})
        active.phase = Phase.ERROR
        active.error = "collecting proposals failed; see the server log"


def result_json(result: TurnResult, link: int, turn: int) -> dict[str, object]:
    return {
        "turn": turn,
        "command": {
            "action": result.command.action.value,
            "zone": result.command.zone.value,
            "manual": result.command.manual,
        },
        "events": [
            {"turn": e.turn, "kind": e.kind.value, "message": e.message} for e in result.events
        ],
        "decision": decision_payload(link, result.decision),
        "state": state_json(result.state),
    }


@router.post("/runs/{run_id}/turns", status_code=202)
async def start_turn(
    body: StartTurn, found: tuple[str, ActiveRun] = Depends(active_run)
) -> dict[str, object]:
    run_id, active = found
    async with active.lock:
        if active.run.state.over:
            raise HTTPException(status_code=409, detail="the mission is over")
        if active.phase is not Phase.IDLE:
            raise HTTPException(status_code=409, detail=f"the turn is {active.phase.value}")
        active.phase = Phase.COLLECTING
        active.task = asyncio.create_task(collect(run_id, active, body.link))
        return {"turn": active.run.state.turn, "phase": active.phase.value}


def to_choice(body: Commit) -> PilotChoice:
    if body.choice == "lodestar":
        return LodestarActs(body.link)
    if body.choice == "manual" and body.action is not None:
        return ManualPick(body.link, body.action)
    if body.choice == "sign" and body.agent is not None:
        return Sign(body.link, body.agent)
    raise HTTPException(status_code=422, detail="the choice is missing its action or agent")


@router.post("/runs/{run_id}/commit")
async def commit(
    body: Commit, found: tuple[str, ActiveRun] = Depends(active_run)
) -> dict[str, object]:
    _, active = found
    async with active.lock:
        if active.last_result is not None and body.turn == active.last_turn:
            return result_json(active.last_result, body.link, body.turn)  # a retry of a commit
        session = active.session
        if active.phase is not Phase.AWAITING_PILOT or session is None:
            raise HTTPException(status_code=409, detail=f"the turn is {active.phase.value}")
        if body.turn != session.turn:
            raise HTTPException(status_code=409, detail="that turn is no longer open")
        try:
            result = await active.run.commit(session, to_choice(body))
        except SupervisorError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        active.phase, active.session = Phase.IDLE, None
        active.last_result, active.last_turn = result, body.turn
        return result_json(result, body.link, body.turn)


@router.post("/runs/{run_id}/dismiss")
async def dismiss(
    body: Dismiss, found: tuple[str, ActiveRun] = Depends(active_run)
) -> dict[str, object]:
    _, active = found
    async with active.lock:
        if active.phase is not Phase.AWAITING_PILOT or active.session is None:
            raise HTTPException(status_code=409, detail=f"the turn is {active.phase.value}")
        try:
            active.run.dismiss(active.session, body.agent)
        except SupervisorError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"dismissed": body.agent.value, "turn": active.session.turn}
