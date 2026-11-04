import itertools

import pytest

from linkfall.agent_name import AgentName
from linkfall.agents.allowlist import ALLOWLIST
from linkfall.agents.contract import NoProposal
from linkfall.agents.wire import (
    COMMS_ACTIONS,
    COMMS_SCHEMA,
    NO_ORDER,
    ORDERS,
    TACTICAL_SCHEMA,
    TacticalAction,
    comms_reply,
    parse_selector,
    selector_schema,
    tactical_reply,
)
from linkfall.engine.actions import Action
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.step import new_game
from linkfall.supervisor.modelclient import ModelError
from linkfall.validator.reply import SAY_MAX_CHARS, ProposalReply, ProposedAction
from linkfall.validator.result import Accepted, Stage
from linkfall.validator.validate import validate_reply


def test_tactical_schema_lists_exactly_the_tactical_allowlist() -> None:
    properties = TACTICAL_SCHEMA["properties"]
    assert isinstance(properties, dict)
    assert set(properties["action"]["enum"]) == {a.value for a in ALLOWLIST[AgentName.TACTICAL]}
    assert {a.value for a in TacticalAction} == set(properties["action"]["enum"])
    assert properties["say"]["maxLength"] == SAY_MAX_CHARS
    assert TACTICAL_SCHEMA["additionalProperties"] is False


def test_comms_schema_covers_every_engine_action_as_an_order() -> None:
    properties = COMMS_SCHEMA["properties"]
    assert isinstance(properties, dict)
    assert set(properties["order"]["enum"]) == {a.value for a in Action} | {NO_ORDER}
    assert tuple(properties["action"]["enum"]) == COMMS_ACTIONS
    assert set(COMMS_ACTIONS) - {"none"} == {a.value for a in ALLOWLIST[AgentName.COMMS]}
    assert ORDERS[-1] == NO_ORDER


def test_selector_schema_enum_matches_the_candidate_count() -> None:
    properties = selector_schema(3)["properties"]
    assert isinstance(properties, dict)
    assert properties["pick"]["enum"] == [-1, 0, 1, 2]
    assert selector_schema(0)["properties"]["pick"]["enum"] == [-1]  # type: ignore[index]


@pytest.mark.parametrize("action", [a.value for a in TacticalAction])
def test_every_tactical_wire_action_becomes_a_valid_reply(action: str) -> None:
    result = tactical_reply(f'{{"action":"{action}","say":"ok"}}')
    assert isinstance(result, ProposalReply)
    assert result.agent is AgentName.TACTICAL
    state = new_game(1, CINDER_WARD)[0]
    assert isinstance(validate_reply(result, AgentName.TACTICAL, state, ALLOWLIST), Accepted)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "flank",
        '```json\n{"action":"flank","say":"x"}\n```',
        '{"action":"flank"}',
        '{"action":"cooldown","say":"x"}',
        '{"action":"flank","say":"x","agent":"tactical"}',
        '{"action":"flank","say":5}',
        '{"action":"flank","say":"' + "x" * (SAY_MAX_CHARS + 1) + '"}',
        " " * 3000,
    ],
)
def test_bad_tactical_text_becomes_no_proposal_without_echoing_it(text: str) -> None:
    result = tactical_reply(text)
    assert isinstance(result, NoProposal)
    assert result.reason.startswith("schema:")
    assert len(result.reason) <= 260


def test_comms_wire_maps_to_replies() -> None:
    relay = comms_reply('{"action":"relay_order","order":"drop_shields","say":"relaying"}')
    assert isinstance(relay, ProposalReply)
    assert relay.action is ProposedAction.RELAY_ORDER
    assert relay.engine_action is Action.DROP_SHIELDS
    truce = comms_reply('{"action":"accept_truce","order":"none","say":"offer"}')
    assert isinstance(truce, ProposalReply)
    assert truce.action is ProposedAction.ACCEPT_TRUCE
    quiet = comms_reply('{"action":"none","order":"none","say":"quiet"}')
    assert isinstance(quiet, ProposalReply)
    assert quiet.action is None


def test_every_comms_order_passes_the_allowlist_and_only_the_rules_can_refuse_it() -> None:
    state = new_game(1, CINDER_WARD)[0]
    for order in (a.value for a in Action):
        result = comms_reply(f'{{"action":"relay_order","order":"{order}","say":"x"}}')
        assert isinstance(result, ProposalReply)
        assert result.engine_action is Action(order)
        checked = validate_reply(result, AgentName.COMMS, state, ALLOWLIST)
        assert isinstance(checked, Accepted) or checked.stage is Stage.RULES, order


@pytest.mark.parametrize(
    "text",
    [
        '{"action":"relay_order","order":"none","say":"x"}',
        '{"action":"accept_truce","order":"flank","say":"x"}',
        '{"action":"none","order":"flank","say":"x"}',
        '{"action":"relay_order","say":"x"}',
        '{"action":"retreat","order":"none","say":"x"}',
        '{"action":"relay_order","order":"teleport","say":"x"}',
    ],
)
def test_inconsistent_comms_wire_is_refused(text: str) -> None:
    assert isinstance(comms_reply(text), NoProposal)


def test_selector_text_is_read_strictly() -> None:
    assert parse_selector('{"pick":1,"reason":"fits"}').pick == 1
    assert parse_selector('{"pick":-1,"reason":"none fit"}').pick is None
    for bad in (
        '{"pick":"1","reason":"x"}',
        '{"pick":1}',
        "nonsense",
        " " * 3000,
        '{"pick":1,"reason":"x","extra":2}',
    ):
        with pytest.raises(ModelError):
            parse_selector(bad)


def test_all_wire_combinations_are_exercised() -> None:
    combos = list(itertools.product(COMMS_ACTIONS, ORDERS))
    valid = [c for c in combos if (c[0] == "relay_order") == (c[1] != NO_ORDER)]
    for action, order in valid:
        text = f'{{"action":"{action}","order":"{order}","say":"x"}}'
        assert isinstance(comms_reply(text), ProposalReply), text
