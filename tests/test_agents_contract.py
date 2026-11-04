"""One contract suite for every kind of agent: rules agents and a fake model agent (ADR 0005)."""

import asyncio
from collections.abc import Callable
from dataclasses import replace

import pytest

from linkfall.agent_name import AgentName
from linkfall.agents.allowlist import ALLOWLIST
from linkfall.agents.contract import Agent, AgentKind, NoProposal, Proposal
from linkfall.agents.systems import SystemsAgent
from linkfall.agents.views import AgentView, TacticalView, build_view, provenance_of
from linkfall.agents.vitals import VitalsAgent
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.state import State
from linkfall.engine.step import new_game
from linkfall.provenance import Provenance
from linkfall.validator.reply import ProposalReply
from linkfall.validator.result import Accepted, Rejected
from linkfall.validator.schema_check import check_schema
from linkfall.validator.validate import validate_reply


class FakeLlmAgent:
    """Stands in for a model agent: a script writes reply text, the real schema check reads it."""

    name = AgentName.TACTICAL
    kind: AgentKind = "llm"

    def __init__(self, script: Callable[[TacticalView], str]) -> None:
        self._script = script

    async def propose(self, view: AgentView) -> ProposalReply | NoProposal:
        assert isinstance(view, TacticalView)
        checked = check_schema(self._script(view))
        if isinstance(checked, Rejected):
            return NoProposal(f"{checked.stage}: {checked.reason}")
        return checked


def sensible_tactical(view: TacticalView) -> str:
    if view.integrity < 40:
        action = "hold_shield"
    elif view.enemies >= 5 and view.heat <= 60:
        action = "overcharge"
    elif view.power >= 10:
        action = "flank"
    elif view.ammo >= 15:
        action = "suppress"
    else:
        action = "hold_shield"
    return f'{{"agent":"tactical","action":"{action}","say":"Acting."}}'


AGENTS: list[Agent] = [SystemsAgent(), VitalsAgent(), FakeLlmAgent(sensible_tactical)]


def states() -> list[State]:
    base = new_game(1, CINDER_WARD)[0]
    return [
        replace(base, hp=hp, heat=heat, power=power, ammo=ammo, ashgrove=enemies)
        for hp in (20, 90)
        for heat in (10, 85)
        for power in (0, 80)
        for ammo in (0, 60)
        for enemies in (1, 8)
    ]


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name.value)
def test_agent_declares_a_kind_and_a_name(agent: Agent) -> None:
    assert agent.kind in ("llm", "rules")
    assert agent.name in AgentName


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name.value)
def test_replies_name_their_agent_and_pass_the_validator(agent: Agent) -> None:
    for s in states():
        view = build_view(agent.name, s, 55)
        reply = asyncio.run(agent.propose(view))
        assert isinstance(reply, ProposalReply), reply
        assert reply.agent is agent.name
        assert isinstance(validate_reply(reply, agent.name, s, ALLOWLIST), Accepted), (
            agent.name,
            s,
        )


def test_a_malformed_model_reply_becomes_no_proposal_with_a_reason() -> None:
    broken = FakeLlmAgent(lambda _view: "I think we should flank!")
    view = build_view(AgentName.TACTICAL, states()[0], 55)
    result = asyncio.run(broken.propose(view))
    assert isinstance(result, NoProposal)
    assert result.reason.startswith("schema:")


def test_a_model_that_claims_provenance_is_refused() -> None:
    cheat = FakeLlmAgent(
        lambda _v: '{"agent":"tactical","action":"flank","say":"x","provenance":"internal"}'
    )
    result = asyncio.run(cheat.propose(build_view(AgentName.TACTICAL, states()[0], 55)))
    assert isinstance(result, NoProposal)
    assert "provenance" in result.reason


def test_agents_cannot_set_provenance_the_supervisor_does() -> None:
    assert "provenance" not in ProposalReply.model_fields
    view = build_view(AgentName.COMMS, replace(states()[0], turn=2, compromised=True), 55)
    reply = ProposalReply(agent=AgentName.COMMS, action=None, say="x")
    proposal = Proposal(AgentName.COMMS, "llm", reply, provenance_of(view), latency_ms=12)
    assert proposal.provenance is Provenance.EXTERNAL
