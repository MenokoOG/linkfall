import json

import pytest
from pydantic import ValidationError

from linkfall.agent_name import AgentName
from linkfall.engine.actions import Action
from linkfall.validator.reply import SAY_MAX_CHARS, ProposalReply, ProposedAction, RelayArgs


def test_proposed_actions_are_the_engine_actions_plus_relay_order() -> None:
    assert {a.value for a in ProposedAction} == {a.value for a in Action} | {"relay_order"}


def test_engine_action_for_plain_relay_and_advice() -> None:
    plain = ProposalReply(agent=AgentName.TACTICAL, action=ProposedAction.FLANK, say="go")
    relay = ProposalReply(
        agent=AgentName.COMMS,
        action=ProposedAction.RELAY_ORDER,
        args=RelayArgs(order=Action.DROP_SHIELDS),
        say="x",
    )
    advice = ProposalReply(agent=AgentName.VITALS, action=None, say="rest")
    assert plain.engine_action is Action.FLANK
    assert relay.engine_action is Action.DROP_SHIELDS
    assert advice.engine_action is None


def test_json_schema_forbids_extra_fields_and_lists_the_actions() -> None:
    schema = ProposalReply.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"agent", "action", "say"}
    assert schema["properties"]["say"]["maxLength"] == SAY_MAX_CHARS


def test_say_limit_is_exact() -> None:
    ok = {"agent": "tactical", "action": "flank", "say": "x" * SAY_MAX_CHARS}
    ProposalReply.model_validate_json(json.dumps(ok), strict=True)
    with pytest.raises(ValidationError):
        ProposalReply.model_validate_json(
            json.dumps({**ok, "say": "x" * (SAY_MAX_CHARS + 1)}), strict=True
        )


@pytest.mark.parametrize(
    "bad",
    [
        {"agent": "tactical", "action": "relay_order", "say": "x"},
        {"agent": "tactical", "action": "flank", "args": {"order": "flank"}, "say": "x"},
        {"agent": "comms", "action": "relay_order", "args": {"order": "teleport"}, "say": "x"},
        {"agent": "comms", "action": "relay_order", "args": {"order": "flank", "x": 1}, "say": "x"},
    ],
)
def test_args_must_match_the_action(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ProposalReply.model_validate_json(json.dumps(bad), strict=True)
