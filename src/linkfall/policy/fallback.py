"""When the selector fails, Lodestar takes the first eligible candidate: Tactical, then Systems."""

from collections.abc import Sequence

from linkfall.agent_name import AgentName
from linkfall.policy.decision import Candidate

FALLBACK_ORDER = (AgentName.TACTICAL, AgentName.SYSTEMS)


def fallback_pick(eligible: Sequence[Candidate]) -> Candidate | None:
    for agent in FALLBACK_ORDER:
        for candidate in eligible:
            if candidate.agent is agent:
                return candidate
    return None
