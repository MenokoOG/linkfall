"""Rows the supervisor writes around a turn: proposals, decisions, the selector, the pilot.

Builders write them; parsers read them back for replay. Neither imports agent or supervisor code.
"""

import json
from dataclasses import dataclass

from pydantic import ValidationError

from linkfall.agent_name import AgentName
from linkfall.engine.actions import Action
from linkfall.eventlog.codec import CodecError
from linkfall.eventlog.types import JsonValue, NewRow, Payload, RowKind
from linkfall.policy.decision import Candidate, Decision
from linkfall.provenance import Provenance
from linkfall.validator.reply import ProposalReply


def proposal_row(
    turn: int,
    agent: AgentName,
    kind: str,
    provenance: Provenance,
    latency_ms: int,
    reply: ProposalReply,
) -> NewRow:
    payload: Payload = {
        "agent": agent.value,
        "kind": kind,
        "provenance": provenance.value,
        "latency_ms": latency_ms,
        "reply": json.loads(reply.model_dump_json()),
    }
    return NewRow(turn, RowKind.PROPOSAL.value, payload)


def no_proposal_row(turn: int, agent: AgentName, kind: str, reason: str, latency_ms: int) -> NewRow:
    payload: Payload = {
        "agent": agent.value,
        "kind": kind,
        "reason": reason,
        "latency_ms": latency_ms,
    }
    return NewRow(turn, RowKind.NO_PROPOSAL.value, payload)


def decision_payload(link: int, decision: Decision) -> Payload:
    eligible: list[JsonValue] = [c.agent.value for c in decision.eligible]
    held: list[JsonValue] = [
        {"agent": h.candidate.agent.value, "reasons": [r.name for r in h.reasons]}
        for h in decision.held
    ]
    return {
        "link": link,
        "zone": decision.zone.value,
        "verdict": decision.verdict.value,
        "eligible": eligible,
        "held": held,
    }


def decision_row(turn: int, link: int, decision: Decision) -> NewRow:
    return NewRow(turn, RowKind.DECISION.value, decision_payload(link, decision))


def selector_row(
    turn: int,
    pick: int | None,
    reason: str,
    chosen: AgentName | None,
    fallback: str | None,
    latency_ms: int,
) -> NewRow:
    payload: Payload = {
        "pick": pick,
        "reason": reason,
        "chosen": chosen.value if chosen is not None else None,
        "fallback": fallback,
        "latency_ms": latency_ms,
    }
    return NewRow(turn, RowKind.SELECTOR.value, payload)


def pilot_row(
    turn: int, op: str, link: int | None, action: Action | None, agent: AgentName | None
) -> NewRow:
    payload: Payload = {
        "op": op,
        "link": link,
        "action": action.value if action is not None else None,
        "agent": agent.value if agent is not None else None,
    }
    return NewRow(turn, RowKind.PILOT.value, payload)


@dataclass(frozen=True, slots=True)
class LoggedPilot:
    op: str
    link: int | None
    action: Action | None
    agent: AgentName | None


@dataclass(frozen=True, slots=True)
class LoggedSelector:
    chosen: AgentName | None
    fallback: str | None


def _str(payload: Payload, name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str):
        raise CodecError(f"field {name!r} is missing or not text")
    return value


def _opt_int(payload: Payload, name: str) -> int | None:
    value = payload.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise CodecError(f"field {name!r} is not a number")
    return value


def _opt_agent(payload: Payload, name: str) -> AgentName | None:
    value = payload.get(name)
    if value is None:
        return None
    try:
        return AgentName(_str(payload, name))
    except ValueError as exc:
        raise CodecError(str(exc)) from exc


def parse_proposal(payload: Payload) -> Candidate:
    try:
        agent = AgentName(_str(payload, "agent"))
        provenance = Provenance(_str(payload, "provenance"))
        reply = ProposalReply.model_validate_json(json.dumps(payload.get("reply")), strict=True)
    except (ValueError, ValidationError) as exc:
        raise CodecError(f"unreadable proposal: {exc}") from exc
    if reply.agent is not agent:
        raise CodecError("proposal reply names a different agent")
    return Candidate(agent, reply, provenance)


def parse_pilot(payload: Payload) -> LoggedPilot:
    raw_action = payload.get("action")
    try:
        action = Action(raw_action) if isinstance(raw_action, str) else None
    except ValueError as exc:
        raise CodecError(str(exc)) from exc
    return LoggedPilot(
        _str(payload, "op"), _opt_int(payload, "link"), action, _opt_agent(payload, "agent")
    )


def parse_selector(payload: Payload) -> LoggedSelector:
    fallback = payload.get("fallback")
    if fallback is not None and not isinstance(fallback, str):
        raise CodecError("field 'fallback' is not text")
    return LoggedSelector(_opt_agent(payload, "chosen"), fallback)


def parse_agent(payload: Payload) -> AgentName:
    agent = _opt_agent(payload, "agent")
    if agent is None:
        raise CodecError("field 'agent' is missing")
    return agent
