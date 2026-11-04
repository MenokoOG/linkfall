import asyncio
from dataclasses import replace

import pytest

from linkfall.agent_name import AgentName
from linkfall.agents.allowlist import ALLOWLIST
from linkfall.agents.systems import SystemsAgent
from linkfall.agents.views import SystemsView, VitalsView, build_view
from linkfall.agents.vitals import VitalsAgent
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.step import new_game
from linkfall.validator.reply import SAY_MAX_CHARS, ProposalReply, ProposedAction
from linkfall.validator.result import Accepted
from linkfall.validator.validate import validate_reply


def systems(**fields: int | bool) -> ProposalReply:
    view = SystemsView(**{"heat": 40, "power": 80, "ammo": 60, "shields": True, **fields})  # type: ignore[arg-type]
    result = asyncio.run(SystemsAgent().propose(view))
    assert isinstance(result, ProposalReply)
    return result


def vitals(strain: int, link: int) -> ProposalReply:
    result = asyncio.run(VitalsAgent().propose(VitalsView(strain=strain, link=link)))
    assert isinstance(result, ProposalReply)
    return result


def test_systems_priorities_match_the_prototype() -> None:
    assert systems(shields=False).action is ProposedAction.HOLD_SHIELD
    assert systems(shields=False, heat=90).action is ProposedAction.HOLD_SHIELD
    hot = systems(heat=61)
    assert hot.action is ProposedAction.COOLDOWN
    assert hot.say == "Heat at 61%. Recommend venting before any overcharge."
    assert systems(heat=60).action is ProposedAction.SUPPRESS
    assert systems(ammo=15).action is ProposedAction.SUPPRESS
    low = systems(ammo=14)
    assert low.action is ProposedAction.HOLD_SHIELD
    assert low.say == "Ammo low. Recommend raising shields."


def test_systems_always_proposes_something_the_validator_accepts() -> None:
    base = new_game(1, CINDER_WARD)[0]
    for heat in (0, 60, 61, 100):
        for ammo in (0, 14, 15, 100):
            for shields in (False, True):
                s = replace(base, heat=heat, ammo=ammo, shields=shields)
                view = build_view(AgentName.SYSTEMS, s, 55)
                reply = asyncio.run(SystemsAgent().propose(view))
                assert isinstance(reply, ProposalReply)
                result = validate_reply(reply, AgentName.SYSTEMS, s, ALLOWLIST)
                assert isinstance(result, Accepted), (heat, ammo, shields)


def test_vitals_advice_thresholds() -> None:
    assert vitals(10, 55).say == "Pilot strain 10%. Within limits."
    assert vitals(10, 60).say == "Pilot strain 10%. Link load is climbing."
    assert vitals(69, 55).say == "Pilot strain 69%. Within limits."
    assert vitals(70, 55).say == "Pilot strain 70%. Recommend lowering the link."
    assert vitals(70, 85).say == "Pilot strain 70%. Recommend lowering the link."


def test_vitals_never_proposes_an_action() -> None:
    assert vitals(99, 90).action is None


def test_texts_fit_the_say_limit() -> None:
    assert len(systems(heat=100).say) <= SAY_MAX_CHARS
    assert len(vitals(100, 90).say) <= SAY_MAX_CHARS


@pytest.mark.parametrize("agent", [SystemsAgent(), VitalsAgent()])
def test_a_rules_agent_refuses_someone_elses_view(agent: SystemsAgent | VitalsAgent) -> None:
    wrong = build_view(AgentName.COMMS, new_game(1, CINDER_WARD)[0], 55)
    with pytest.raises(TypeError):
        asyncio.run(agent.propose(wrong))
