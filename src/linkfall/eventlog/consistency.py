"""Is a turn's logged context consistent with the command the engine ran?

Re-runs the policy over the logged proposals and compares it with the logged decision. A log
with no decision row (an engine-only log, or a turn still open) skips the policy checks.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from linkfall.agent_name import AgentName
from linkfall.engine.actions import Action
from linkfall.engine.step import Command
from linkfall.eventlog.codec import CodecError
from linkfall.eventlog.turnrows import (
    LoggedPilot,
    LoggedSelector,
    decision_payload,
    parse_agent,
    parse_pilot,
    parse_proposal,
    parse_selector,
)
from linkfall.eventlog.types import LogRow, ReplayFailure, RowKind
from linkfall.policy.decide import decide
from linkfall.policy.decision import Candidate, Decision, Verdict
from linkfall.policy.zones import PolicyError
from linkfall.runmode import RunMode


@dataclass
class _Turn:
    proposals: list[Candidate] = field(default_factory=list)
    dismissed: set[AgentName] = field(default_factory=set)
    decisions: list[LogRow] = field(default_factory=list)
    selector: LoggedSelector | None = None
    pilot: list[LoggedPilot] = field(default_factory=list)


def _read(rows: Sequence[LogRow]) -> _Turn | ReplayFailure:
    turn = _Turn()
    for row in rows:
        try:
            match row.kind:
                case RowKind.PROPOSAL.value:
                    turn.proposals.append(parse_proposal(row.payload))
                case RowKind.NO_PROPOSAL.value:
                    parse_agent(row.payload)
                case RowKind.DECISION.value:
                    turn.decisions.append(row)
                case RowKind.SELECTOR.value:
                    turn.selector = parse_selector(row.payload)
                case RowKind.PILOT.value:
                    pilot = parse_pilot(row.payload)
                    turn.pilot.append(pilot)
                    if pilot.op == "dismiss" and pilot.agent is not None:
                        turn.dismissed.add(pilot.agent)
        except CodecError as exc:
            return ReplayFailure(row.id, str(exc))
    return turn


def _recompute(mode: RunMode, turn: _Turn, row: LogRow) -> Decision | ReplayFailure:
    link = row.payload.get("link")
    if isinstance(link, bool) or not isinstance(link, int):
        return ReplayFailure(row.id, "decision has no link")
    live = [c for c in turn.proposals if c.agent not in turn.dismissed]
    try:
        decision = decide(link, mode, live)
    except PolicyError as exc:
        return ReplayFailure(row.id, f"decision link is not valid: {exc}")
    if decision_payload(link, decision) != row.payload:
        return ReplayFailure(row.id, "logged decision differs from what the policy decides")
    return decision


def _check_actor(
    turn: _Turn, decision: Decision, command: Command, row_id: int
) -> ReplayFailure | None:
    if command.zone is not decision.zone:
        return ReplayFailure(row_id, "command zone differs from the decision's zone")
    if command.manual:
        signed = [p for p in turn.pilot if p.op == "sign"]
        for pilot in signed:
            held = [h.candidate for h in decision.held if h.candidate.agent is pilot.agent]
            if not held or held[0].reply.engine_action is not command.action:
                return ReplayFailure(row_id, "signed proposal does not match the command")
        return None
    if decision.verdict is Verdict.MANUAL:
        return ReplayFailure(row_id, "Lodestar acted in the MANUAL zone")
    if turn.selector is None:
        return ReplayFailure(row_id, "Lodestar command has no selector row")
    if turn.selector.chosen is None:
        if command.action is not Action.HOLD_SHIELD:
            return ReplayFailure(row_id, "a fallback command must be hold_shield")
        return None
    pick = [c for c in decision.eligible if c.agent is turn.selector.chosen]
    if not pick:
        return ReplayFailure(row_id, f"selector chose {turn.selector.chosen}, who was not eligible")
    if pick[0].reply.engine_action is not command.action:
        return ReplayFailure(row_id, "command differs from the chosen proposal")
    return None


def check_turn(
    mode: RunMode, rows: Sequence[LogRow], command: Command | None, command_row_id: int | None
) -> ReplayFailure | None:
    turn = _read(rows)
    if isinstance(turn, ReplayFailure):
        return turn
    if not turn.decisions:
        return None
    if len(turn.decisions) > 1 or command is None or command_row_id is None:
        return ReplayFailure(turn.decisions[-1].id, "decision rows do not match one command")
    decision = _recompute(mode, turn, turn.decisions[0])
    if isinstance(decision, ReplayFailure):
        return decision
    return _check_actor(turn, decision, command, command_row_id)
