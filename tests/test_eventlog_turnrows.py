import pytest

from linkfall.agent_name import AgentName
from linkfall.engine.actions import Action
from linkfall.eventlog.codec import CodecError
from linkfall.eventlog.turnrows import (
    parse_agent,
    parse_pilot,
    parse_proposal,
    parse_selector,
    pilot_row,
    proposal_row,
    selector_row,
)
from linkfall.eventlog.types import Payload
from linkfall.provenance import Provenance
from linkfall.validator.reply import ProposalReply, ProposedAction


def good_proposal() -> Payload:
    reply = ProposalReply(agent=AgentName.TACTICAL, action=ProposedAction.FLANK, say="go")
    return proposal_row(2, AgentName.TACTICAL, "llm", Provenance.INTERNAL, 120, reply).payload


def test_a_proposal_round_trips() -> None:
    candidate = parse_proposal(good_proposal())
    assert candidate.agent is AgentName.TACTICAL
    assert candidate.reply.action is ProposedAction.FLANK
    assert candidate.provenance is Provenance.INTERNAL


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("agent", "admiral"),
        ("agent", 7),
        ("provenance", "trusted"),
        ("reply", None),
        ("reply", {"agent": "comms", "action": None, "say": "x"}),  # names a different agent
        ("reply", {"agent": "tactical", "action": "flank", "say": "x", "extra": 1}),
    ],
)
def test_bad_proposal_payloads_are_refused(field: str, value: object) -> None:
    payload = good_proposal()
    payload[field] = value  # type: ignore[assignment]
    with pytest.raises(CodecError):
        parse_proposal(payload)


def test_pilot_rows_round_trip_and_reject_bad_fields() -> None:
    pilot = parse_pilot(pilot_row(3, "manual", 55, Action.FLANK, None).payload)
    assert (pilot.op, pilot.link, pilot.action, pilot.agent) == ("manual", 55, Action.FLANK, None)
    dismiss = parse_pilot(pilot_row(3, "dismiss", None, None, AgentName.COMMS).payload)
    assert dismiss.agent is AgentName.COMMS
    for bad in (
        {"op": "manual", "link": 55, "action": "teleport", "agent": None},
        {"op": "manual", "link": "55", "action": None, "agent": None},
        {"op": "manual", "link": True, "action": None, "agent": None},
        {"op": "dismiss", "link": None, "action": None, "agent": "admiral"},
        {"link": 55, "action": None, "agent": None},
    ):
        with pytest.raises(CodecError):
            parse_pilot(bad)  # type: ignore[arg-type]


def test_selector_rows_round_trip_and_reject_bad_fields() -> None:
    picked = parse_selector(selector_row(1, 0, "ok", AgentName.TACTICAL, None, 5).payload)
    assert picked.chosen is AgentName.TACTICAL
    assert picked.fallback is None
    fell_back = parse_selector(selector_row(1, None, "r", None, "selector timeout", 5).payload)
    assert fell_back.chosen is None
    assert fell_back.fallback == "selector timeout"
    with pytest.raises(CodecError):
        parse_selector({"chosen": None, "fallback": 7})


def test_parse_agent_needs_an_agent() -> None:
    assert parse_agent({"agent": "vitals"}) is AgentName.VITALS
    with pytest.raises(CodecError):
        parse_agent({"agent": None})
