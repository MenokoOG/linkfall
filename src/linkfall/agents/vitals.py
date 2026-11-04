"""Vitals: plain code over pilot strain and the link value. Advice only, never an action."""

from linkfall.agent_name import AgentName
from linkfall.agents.contract import AgentKind, NoProposal
from linkfall.agents.views import AgentView, VitalsView
from linkfall.validator.reply import ProposalReply

STRAIN_WARNING = 70
LINK_LOAD_FROM = 60


class VitalsAgent:
    name = AgentName.VITALS
    kind: AgentKind = "rules"

    async def propose(self, view: AgentView) -> ProposalReply | NoProposal:
        if not isinstance(view, VitalsView):
            raise TypeError(f"VitalsAgent needs a VitalsView, got {type(view).__name__}")
        if view.strain >= STRAIN_WARNING:
            advice = "Recommend lowering the link."
        elif view.link >= LINK_LOAD_FROM:
            advice = "Link load is climbing."
        else:
            advice = "Within limits."
        say = f"Pilot strain {view.strain}%. {advice}"
        return ProposalReply(agent=self.name, action=None, say=say)
