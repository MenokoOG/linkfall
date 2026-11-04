"""Tamper with a recorded mission and check that replay names the first inconsistency."""

import asyncio
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from linkfall.agent_name import AgentName
from linkfall.engine.actions import Action
from linkfall.eventlog.replay import ReplayResult, replay
from linkfall.eventlog.schema import SCHEMA_VERSION
from linkfall.eventlog.store import EventStore
from linkfall.eventlog.turnrows import decision_payload
from linkfall.eventlog.types import NewRow, RunHeader
from linkfall.policy.decide import decide
from linkfall.runmode import RunMode
from linkfall.supervisor.choices import LodestarActs, ManualPick, Sign
from support import make_deps, play, start

Edit = Callable[[list[NewRow]], list[NewRow]]


def record() -> EventStore:
    """Turn 1 Lodestar, turn 2 pilot audits, turn 3 hold, turn 4 pilot signs the truce."""
    store = EventStore()
    run = start(make_deps(store), mode=RunMode.HARDENED)
    asyncio.run(
        play(
            run,
            [
                LodestarActs(85),
                ManualPick(85, Action.AUDIT_COMMS),
                ManualPick(85, Action.HOLD_SHIELD),
                Sign(85, AgentName.COMMS),
            ],
        )
    )
    return store


def tampered(store: EventStore, edit: Edit) -> ReplayResult:
    rows = [NewRow(r.turn, r.kind, r.payload) for r in store.read_rows("r1")]
    other = EventStore()
    header = store.get_run("r1")
    other.create_run(
        RunHeader("r1", header.seed, header.mode, header.scenario, SCHEMA_VERSION), edit(rows)
    )
    return replay(other, "r1")


def first(rows: list[NewRow], kind: str, after: int = 0) -> int:
    return next(i for i, r in enumerate(rows) if i >= after and r.kind == kind)


def reason(result: ReplayResult) -> str:
    assert result.failure is not None
    return result.failure.reason


def test_the_untouched_mission_replays() -> None:
    result = replay(record(), "r1")
    assert result.ok, result.failure
    assert result.turns == 4


def test_a_changed_decision_is_caught() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        rows[first(rows, "decision")].payload["verdict"] = "ASK_PILOT"
        return rows

    assert "differs from what the policy decides" in reason(tampered(record(), edit))


def test_a_removed_proposal_changes_the_policy_result() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        del rows[first(rows, "proposal")]
        return rows

    assert "differs from what the policy decides" in reason(tampered(record(), edit))


def test_an_injected_proposal_is_caught() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        index = first(rows, "proposal")
        rows.insert(index, NewRow(rows[index].turn, "proposal", dict(rows[index].payload)))
        return rows

    assert "differs from what the policy decides" in reason(tampered(record(), edit))


def test_a_lodestar_command_with_no_selector_row_is_caught() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        del rows[first(rows, "selector")]
        return rows

    assert "no selector row" in reason(tampered(record(), edit))


def test_a_selector_that_chose_an_ineligible_agent_is_caught() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        rows[first(rows, "selector")].payload["chosen"] = "vitals"
        return rows

    assert "who was not eligible" in reason(tampered(record(), edit))


def test_a_command_that_differs_from_the_chosen_proposal_is_caught() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        rows[first(rows, "command")].payload["action"] = "cooldown"
        return rows

    assert "differs from the chosen proposal" in reason(tampered(record(), edit))


def test_a_fallback_that_is_not_hold_shield_is_caught() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        rows[first(rows, "selector")].payload["chosen"] = None
        return rows

    assert "must be hold_shield" in reason(tampered(record(), edit))


def test_a_signature_that_does_not_match_the_command_is_caught() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        sign = next(r for r in rows if r.kind == "pilot" and r.payload["op"] == "sign")
        sign.payload["agent"] = "tactical"
        return rows

    assert "does not match the command" in reason(tampered(record(), edit))


def test_a_command_in_the_wrong_zone_is_caught() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        rows[first(rows, "command")].payload["zone"] = "ASSISTED"
        return rows

    assert "zone differs" in reason(tampered(record(), edit))


def test_lodestar_acting_in_the_manual_zone_is_caught() -> None:
    store = record()

    def edit(rows: list[NewRow]) -> list[NewRow]:
        d = first(rows, "decision")
        candidates = []
        for row in rows[:d]:
            if row.kind == "proposal" and row.turn == rows[d].turn:
                from linkfall.eventlog.turnrows import parse_proposal

                candidates.append(parse_proposal(row.payload))
        rows[d] = NewRow(
            rows[d].turn, "decision", decision_payload(25, decide(25, RunMode.HARDENED, candidates))
        )
        rows[first(rows, "command")].payload["zone"] = "MANUAL"
        return rows

    assert "MANUAL zone" in reason(tampered(store, edit))


def test_an_unreadable_proposal_is_caught_at_its_row() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        rows[first(rows, "proposal")].payload["provenance"] = "trusted"
        return rows

    assert "trusted" in reason(tampered(record(), edit))


def test_a_decision_with_a_bad_link_is_caught() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        rows[first(rows, "decision")].payload["link"] = 12
        return rows

    assert "link is not valid" in reason(tampered(record(), edit))


def test_two_decisions_for_one_command_are_caught() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        index = first(rows, "decision")
        rows.insert(index, NewRow(rows[index].turn, "decision", dict(rows[index].payload)))
        return rows

    assert "do not match one command" in reason(tampered(record(), edit))


def test_a_decision_row_with_no_command_after_it_is_caught() -> None:
    def edit(rows: list[NewRow]) -> list[NewRow]:
        decision = rows[first(rows, "decision")]
        end_of_turn_one = first(rows, "proposal", after=first(rows, "command"))
        return [*rows[:end_of_turn_one], NewRow(2, "decision", dict(decision.payload))]

    assert "do not match one command" in reason(tampered(record(), edit))


def test_replay_loads_no_agent_or_supervisor_code() -> None:
    """ADR 0007: replay never touches a model. It can't, because it never imports one."""
    src = Path(__file__).resolve().parent.parent / "src"
    code = (
        f"import sys; sys.path.insert(0, {str(src)!r}); import linkfall.eventlog.replay; "
        "prefixes = ('linkfall.agents', 'linkfall.supervisor'); "
        "bad = [m for m in sys.modules if m.startswith(prefixes)]; "
        "sys.exit(1 if bad else 0)"
    )
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
