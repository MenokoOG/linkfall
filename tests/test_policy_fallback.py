from linkfall.agent_name import AgentName
from linkfall.engine.actions import Action
from linkfall.policy.decision import Candidate
from linkfall.policy.fallback import fallback_pick
from linkfall.provenance import Provenance
from linkfall.validator.reply import ProposalReply, ProposedAction


def cand(agent: AgentName, action: Action) -> Candidate:
    reply = ProposalReply(agent=agent, action=ProposedAction(action.value), say="x")
    return Candidate(agent, reply, Provenance.INTERNAL)


def test_tactical_comes_before_systems() -> None:
    systems = cand(AgentName.SYSTEMS, Action.COOLDOWN)
    tactical = cand(AgentName.TACTICAL, Action.FLANK)
    assert fallback_pick([systems, tactical]) is tactical


def test_systems_when_tactical_is_absent() -> None:
    systems = cand(AgentName.SYSTEMS, Action.COOLDOWN)
    comms = cand(AgentName.COMMS, Action.HOLD_SHIELD)
    assert fallback_pick([comms, systems]) is systems


def test_none_when_only_other_agents_remain() -> None:
    assert fallback_pick([cand(AgentName.COMMS, Action.HOLD_SHIELD)]) is None
    assert fallback_pick([]) is None
