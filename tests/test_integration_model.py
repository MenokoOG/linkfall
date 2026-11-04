"""Needs a running llama-server. Skipped unless LINKFALL_TEST_MODEL_URL is set.

LINKFALL_TEST_MODEL_URL=http://127.0.0.1:8090 pytest -m integration -s
"""

import asyncio
import os
import statistics
import time
from dataclasses import replace

import pytest

from linkfall.agent_name import AgentName
from linkfall.agents.allowlist import ALLOWLIST
from linkfall.agents.crew import model_crew
from linkfall.agents.model_agents import ModelComms, ModelSelector, ModelTactical
from linkfall.agents.views import build_view
from linkfall.engine.actions import Action
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.step import new_game
from linkfall.engine.zone_effects import Zone
from linkfall.eventlog.replay import replay
from linkfall.eventlog.store import EventStore
from linkfall.policy.decision import Candidate
from linkfall.provenance import Provenance
from linkfall.runmode import RunMode
from linkfall.supervisor.choices import LodestarActs
from linkfall.supervisor.http_client import HttpModelClient
from linkfall.supervisor.modelclient import ModelRequest, ModelResponse
from linkfall.supervisor.selector import SelectorContext
from linkfall.validator.reply import ProposalReply, ProposedAction, RelayArgs
from linkfall.validator.result import Accepted
from linkfall.validator.validate import validate_reply
from support import make_deps, play, start

URL = os.environ.get("LINKFALL_TEST_MODEL_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(URL is None, reason="set LINKFALL_TEST_MODEL_URL to run"),
]


class Recording:
    """Wraps the real client and keeps every response's timing and token counts."""

    def __init__(self, inner: HttpModelClient) -> None:
        self._inner = inner
        self.calls: list[tuple[float, ModelResponse]] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        started = time.monotonic()
        response = await self._inner.complete(request)
        self.calls.append((time.monotonic() - started, response))
        return response


def client() -> Recording:
    assert URL is not None
    return Recording(HttpModelClient(URL, request_timeout_s=120.0))


def report(label: str, rec: Recording) -> None:
    times = [t for t, _ in rec.calls]
    prompt = [r.prompt_tokens or 0 for _, r in rec.calls]
    cached = [r.cached_tokens or 0 for _, r in rec.calls]
    out = [r.completion_tokens or 0 for _, r in rec.calls]
    print(  # noqa: T201
        f"\n[{label}] calls={len(times)} median={statistics.median(times):.1f}s "
        f"max={max(times):.1f}s prompt_tokens(median)={statistics.median(prompt):.0f} "
        f"cached(median)={statistics.median(cached):.0f} "
        f"completion(median)={statistics.median(out):.0f}"
    )


def test_tactical_gives_schema_valid_proposals() -> None:
    rec = client()
    agent = ModelTactical(rec)
    base = new_game(1, CINDER_WARD)[0]
    states = [
        replace(base, hp=90, heat=40, ammo=60, power=80, ashgrove=2),
        replace(base, hp=25),
        replace(base, ashgrove=8, heat=40),
        replace(base, heat=85, ashgrove=8),
        replace(base, power=5, ammo=10, ashgrove=2),
        replace(base, turn=4, visitors=7, ashgrove=3),
    ]
    accepted = 0
    for s in states:
        reply = asyncio.run(agent.propose(build_view(AgentName.TACTICAL, s, 55)))
        assert isinstance(reply, ProposalReply), reply  # constrained decoding must give valid JSON
        accepted += isinstance(validate_reply(reply, AgentName.TACTICAL, s, ALLOWLIST), Accepted)
    report("tactical", rec)
    print(f"[tactical] rule-valid {accepted}/{len(states)}")  # noqa: T201
    assert accepted >= len(states) - 2


def test_comms_reads_a_quiet_channel_and_a_forged_order() -> None:
    rec = client()
    agent = ModelComms(rec)
    base = new_game(1, CINDER_WARD)[0]
    quiet = asyncio.run(agent.propose(build_view(AgentName.COMMS, base, 55)))
    forged = asyncio.run(
        agent.propose(build_view(AgentName.COMMS, replace(base, turn=2, compromised=True), 55))
    )
    offer = asyncio.run(agent.propose(build_view(AgentName.COMMS, replace(base, turn=4), 55)))
    for label, reply in (("quiet", quiet), ("forged", forged), ("offer", offer)):
        assert isinstance(reply, ProposalReply), reply
        print(f"[comms {label}] action={reply.action} order={reply.engine_action}")  # noqa: T201
    report("comms", rec)


def test_selector_returns_a_usable_pick() -> None:
    rec = client()
    candidates = [
        Candidate(
            AgentName.TACTICAL,
            ProposalReply(agent=AgentName.TACTICAL, action=ProposedAction.FLANK, say="x"),
            Provenance.INTERNAL,
        ),
        Candidate(
            AgentName.COMMS,
            ProposalReply(
                agent=AgentName.COMMS,
                action=ProposedAction.RELAY_ORDER,
                args=RelayArgs(order=Action.DROP_SHIELDS),
                say="x",
            ),
            Provenance.EXTERNAL,
        ),
    ]
    context = SelectorContext(2, Zone.DELEGATED, 87, 45, 45, 78, True, 8)
    output = asyncio.run(ModelSelector(rec).select(candidates, context))
    print(f"[selector] pick={output.pick} reason={output.reason!r}")  # noqa: T201
    report("selector", rec)
    assert output.pick in {None, 0, 1}


@pytest.mark.parametrize("mode", [RunMode.STORY, RunMode.HARDENED])
def test_a_whole_mission_on_the_real_model_replays(mode: RunMode) -> None:
    rec = client()
    agents, selector = model_crew(rec)
    store = EventStore()
    run = start(make_deps(store, agents=agents, selector=selector), mode=mode)
    started = time.monotonic()
    asyncio.run(play(run, [LodestarActs(85)] * 5))
    elapsed = time.monotonic() - started
    rows = store.read_rows("r1")
    missing = [r for r in rows if r.kind == "no_proposal"]
    commands = [str(r.payload["action"]) for r in rows if r.kind == "command"]
    print(  # noqa: T201
        f"\n[mission {mode.value}] {elapsed:.0f}s for {len(commands)} turns, "
        f"outcome={run.state.outcome}, commands={commands}, no_proposal={len(missing)}"
    )
    for r in missing:
        print(f"  no_proposal turn {r.turn} {r.payload['agent']}: {r.payload['reason']}")  # noqa: T201
    report(f"mission {mode.value}", rec)
    result = replay(store, "r1")
    assert result.ok, result.failure
