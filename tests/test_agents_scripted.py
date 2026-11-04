import asyncio
from dataclasses import replace

import pytest

from linkfall.agent_name import AgentName
from linkfall.agents.contract import NoProposal
from linkfall.agents.scripted import ScriptedComms, ScriptedTactical
from linkfall.agents.views import build_view
from linkfall.engine.actions import Action
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.state import State
from linkfall.engine.step import new_game
from linkfall.validator.reply import ProposalReply, ProposedAction


def base() -> State:
    return new_game(1, CINDER_WARD)[0]


def tactical(state: State, agent: ScriptedTactical | None = None) -> ProposalReply | NoProposal:
    view = build_view(AgentName.TACTICAL, state, 55)
    return asyncio.run((agent or ScriptedTactical()).propose(view))


def comms(state: State) -> ProposalReply:
    result = asyncio.run(ScriptedComms().propose(build_view(AgentName.COMMS, state, 55)))
    assert isinstance(result, ProposalReply)
    return result


def action_of(result: ProposalReply | NoProposal) -> ProposedAction | None:
    assert isinstance(result, ProposalReply)
    return result.action


def test_tactical_priorities_follow_the_prototype() -> None:
    assert action_of(tactical(replace(base(), hp=39))) is ProposedAction.HOLD_SHIELD
    assert action_of(tactical(base())) is ProposedAction.OVERCHARGE  # 8 enemies
    few = replace(base(), ashgrove=2)
    assert action_of(tactical(few)) is ProposedAction.FLANK
    assert action_of(tactical(replace(few, power=9))) is ProposedAction.SUPPRESS


def test_tactical_can_be_scripted_to_time_out() -> None:
    result = tactical(replace(base(), turn=3), ScriptedTactical(fail_turns=frozenset({3})))
    assert isinstance(result, NoProposal)
    assert isinstance(tactical(base(), ScriptedTactical(fail_turns=frozenset({3}))), ProposalReply)


def test_comms_obeys_a_forged_relay_order() -> None:
    reply = comms(replace(base(), turn=2, compromised=True))
    assert reply.action is ProposedAction.RELAY_ORDER
    assert reply.engine_action is Action.DROP_SHIELDS
    assert reply.say.startswith("[PRIORITY / ASHGROVE-CMD]")


def test_comms_passes_on_a_genuine_truce_offer() -> None:
    assert comms(replace(base(), turn=4)).action is ProposedAction.ACCEPT_TRUCE


def test_comms_has_only_advice_on_a_quiet_channel() -> None:
    assert comms(base()).action is None


@pytest.mark.parametrize("agent", [ScriptedTactical(), ScriptedComms()])
def test_wrong_view_is_refused(agent: ScriptedTactical | ScriptedComms) -> None:
    with pytest.raises(TypeError):
        asyncio.run(agent.propose(build_view(AgentName.VITALS, base(), 55)))
