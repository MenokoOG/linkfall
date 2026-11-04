import asyncio
from pathlib import Path

import pytest

from linkfall.agent_name import AgentName
from linkfall.agents.contract import Agent, NoProposal
from linkfall.agents.systems import SystemsAgent
from linkfall.engine.actions import Action
from linkfall.engine.events import EventKind
from linkfall.eventlog.export import read_export
from linkfall.eventlog.replay import replay
from linkfall.eventlog.store import EventStore
from linkfall.policy.zones import PolicyError
from linkfall.runmode import RunMode
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.choices import LodestarActs, ManualPick, Sign
from linkfall.supervisor.run import SupervisorError
from linkfall.validator.reply import ProposalReply, ProposedAction
from support import Behaviour, make_deps, run_sync, scripted_agents, start

GOLDEN = Path(__file__).parent / "golden"


def as_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return list(value)


def kinds(store: EventStore, run_id: str = "r1") -> list[str]:
    return [r.kind for r in store.read_rows(run_id)]


def test_a_turn_logs_each_answer_as_it_arrives_with_rules_agents_first() -> None:
    llm_tactical = Behaviour(
        AgentName.TACTICAL,
        lambda _v: ProposalReply(agent=AgentName.TACTICAL, action=ProposedAction.FLANK, say="go"),
    )
    store = EventStore()
    agents: list[Agent] = [llm_tactical, SystemsAgent(), *scripted_agents()[2:]]
    run = start(make_deps(store, agents=agents))
    asyncio.run(run.begin_turn(55))
    rows = [r for r in store.read_rows("r1") if r.kind in {"proposal", "no_proposal"}]
    assert [r.payload["agent"] for r in rows] == ["systems", "comms", "vitals", "tactical"]
    assert [r.payload["kind"] for r in rows][-1] == "llm"


def test_begin_turn_checks_the_link_and_the_mission_state() -> None:
    run = start(make_deps())
    with pytest.raises(PolicyError):
        asyncio.run(run.begin_turn(12))
    run_sync(run, [ManualPick(55, Action.HOLD_SHIELD)] * 5)
    assert run.state.over
    with pytest.raises(SupervisorError, match="over"):
        asyncio.run(run.begin_turn(55))


def test_lodestar_acts_and_the_log_replays() -> None:
    store = EventStore()
    run = start(make_deps(store))
    run_sync(run, [LodestarActs(45)])
    assert run.state.turn == 2
    assert kinds(store).count("selector") == 1
    assert kinds(store).count("decision") == 1
    result = replay(store, "r1")
    assert result.ok, result.failure
    assert result.state == run.state


def test_lodestar_is_locked_out_in_the_manual_zone_and_nothing_is_committed() -> None:
    store = EventStore()
    run = start(make_deps(store))

    async def attempt() -> None:
        session = await run.begin_turn(25)
        await run.commit(session, LodestarActs(25))

    with pytest.raises(SupervisorError, match="MANUAL"):
        asyncio.run(attempt())
    assert "command" not in kinds(store)
    assert run.state.turn == 1


def test_a_manual_pick_that_breaks_a_rule_loses_the_turn() -> None:
    run = start(make_deps())
    # audit_comms needs a hostile signature, and the channel is clean on turn 1
    run_sync(run, [ManualPick(55, Action.AUDIT_COMMS)])
    assert run.state.turn == 2
    assert run.state.strain > 10


def test_commit_is_idempotent_per_turn() -> None:
    store = EventStore()
    run = start(make_deps(store))

    async def twice() -> tuple[object, object]:
        session = await run.begin_turn(45)
        first = await run.commit(session, LodestarActs(45))
        before = len(store.read_rows("r1"))
        second = await run.commit(session, ManualPick(45, Action.FLANK))
        assert len(store.read_rows("r1")) == before
        return first, second

    first, second = asyncio.run(twice())
    assert first is second


def test_a_session_from_an_earlier_turn_is_refused() -> None:
    run = start(make_deps())

    async def stale() -> None:
        old = await run.begin_turn(55)
        fresh = await run.begin_turn(55)
        await run.commit(fresh, ManualPick(55, Action.HOLD_SHIELD))
        await run.commit(old, ManualPick(55, Action.HOLD_SHIELD))

    with pytest.raises(SupervisorError, match="no longer open"):
        asyncio.run(stale())


def test_the_commit_link_wins_and_is_logged() -> None:
    store = EventStore()
    run = start(make_deps(store))

    async def go() -> None:
        session = await run.begin_turn(85)
        result = await run.commit(session, LodestarActs(45))
        assert result.decision.zone.value == "ASSISTED"

    asyncio.run(go())
    decision = next(r for r in store.read_rows("r1") if r.kind == "decision")
    assert decision.payload["link"] == 45


def test_signing_a_truce_works_once_the_channel_is_clean() -> None:
    store = EventStore()
    run = start(make_deps(store))
    run_sync(
        run,
        [
            ManualPick(55, Action.HOLD_SHIELD),
            ManualPick(55, Action.AUDIT_COMMS),
            ManualPick(55, Action.HOLD_SHIELD),
            Sign(85, AgentName.COMMS),
        ],
    )
    assert run.state.truce
    assert replay(store, "r1").ok


def test_signing_with_nothing_waiting_is_refused() -> None:
    run = start(make_deps())

    async def go() -> None:
        session = await run.begin_turn(55)
        await run.commit(session, Sign(55, AgentName.COMMS))

    with pytest.raises(SupervisorError, match="nothing waiting"):
        asyncio.run(go())


def test_dismissing_a_proposal_removes_it_from_the_decision() -> None:
    store = EventStore()
    run = start(make_deps(store))
    run_sync(run, [ManualPick(85, Action.HOLD_SHIELD)])

    async def go() -> None:
        session = await run.begin_turn(85)  # turn 2: the forged order is on the table
        run.dismiss(session, AgentName.COMMS)
        result = await run.commit(session, LodestarActs(85))
        assert all(h.candidate.agent is not AgentName.COMMS for h in result.decision.held)
        assert all(c.agent is not AgentName.COMMS for c in result.decision.eligible)
        assert result.command.action is not Action.DROP_SHIELDS

    asyncio.run(go())
    assert replay(store, "r1").ok


def test_dismissing_an_agent_with_no_proposal_is_refused() -> None:
    run = start(make_deps(agents=[SystemsAgent()]))

    async def go() -> None:
        session = await run.begin_turn(55)
        run.dismiss(session, AgentName.COMMS)

    with pytest.raises(SupervisorError, match="no proposal"):
        asyncio.run(go())


def test_when_every_model_agent_fails_lodestar_stands_by_and_the_fallback_runs() -> None:
    store = EventStore()
    failing = [
        Behaviour(AgentName.TACTICAL, lambda _v: NoProposal("timeout")),
        Behaviour(AgentName.COMMS, lambda _v: NoProposal("timeout")),
    ]
    run = start(make_deps(store, agents=failing, budgets=Budgets(timeout_s=0.05)))
    run_sync(run, [LodestarActs(85)])
    selector = next(r for r in store.read_rows("r1") if r.kind == "selector")
    assert selector.payload["fallback"] == "nothing eligible"
    assert selector.payload["chosen"] is None
    command = next(r for r in store.read_rows("r1") if r.kind == "command")
    assert command.payload["action"] == "hold_shield"
    assert replay(store, "r1").ok


def test_story_mission_matches_the_engine_only_golden_log() -> None:
    store = EventStore()
    run = start(make_deps(store))
    run_sync(run, [LodestarActs(85)] * 5)
    assert run.state.outcome is not None
    assert run.state.outcome.value == "DESTROYED"
    golden = read_export(GOLDEN / "story-forged-order-link85.json")
    assert replay(store, "r1").fingerprint == golden["fingerprint"]


def test_hardened_mode_never_runs_the_forged_order() -> None:
    store = EventStore()
    run = start(make_deps(store), mode=RunMode.HARDENED)
    run_sync(run, [LodestarActs(85)] * 5)
    commands = [r.payload["action"] for r in store.read_rows("r1") if r.kind == "command"]
    assert "drop_shields" not in commands
    reasons = [
        reason
        for r in store.read_rows("r1")
        if r.kind == "decision"
        for held in as_list(r.payload["held"])
        if isinstance(held, dict) and held["agent"] == "comms"
        for reason in as_list(held["reasons"])
    ]
    assert "EXTERNAL_ORIGIN" in reasons
    assert replay(store, "r1").ok


def test_warning_events_are_part_of_the_state_the_tactical_view_sees() -> None:
    run = start(make_deps())
    run_sync(run, [ManualPick(55, Action.HOLD_SHIELD)])
    session = asyncio.run(run.begin_turn(55))
    assert session.state.turn == 2
    events = [
        e.kind for e in asyncio.run(run.commit(session, ManualPick(55, Action.HOLD_SHIELD))).events
    ]
    assert EventKind.VALID in events


def test_nothing_can_be_dismissed_after_the_mission_ends() -> None:
    run = start(make_deps())
    run_sync(run, [ManualPick(55, Action.HOLD_SHIELD)] * 4)

    async def last() -> None:
        session = await run.begin_turn(55)
        await run.commit(session, ManualPick(55, Action.HOLD_SHIELD))
        run.dismiss(session, AgentName.COMMS)

    with pytest.raises(SupervisorError, match="over"):
        asyncio.run(last())
