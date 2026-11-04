"""Systems: plain code over heat, power, ammo and shields."""

from linkfall.agent_name import AgentName
from linkfall.agents.contract import AgentKind, NoProposal
from linkfall.agents.views import AgentView, SystemsView
from linkfall.validator.reply import ProposalReply, ProposedAction

HEAT_LIMIT = 60
MIN_AMMO = 15


class SystemsAgent:
    name = AgentName.SYSTEMS
    kind: AgentKind = "rules"

    async def propose(self, view: AgentView) -> ProposalReply | NoProposal:
        if not isinstance(view, SystemsView):
            raise TypeError(f"SystemsAgent needs a SystemsView, got {type(view).__name__}")
        if not view.shields:
            return self._reply(ProposedAction.HOLD_SHIELD, "Shields are down. Raise them first.")
        if view.heat > HEAT_LIMIT:
            say = f"Heat at {view.heat}%. Recommend venting before any overcharge."
            return self._reply(ProposedAction.COOLDOWN, say)
        if view.ammo >= MIN_AMMO:
            return self._reply(
                ProposedAction.SUPPRESS, "Heat and power nominal. Recommend suppressing fire."
            )
        return self._reply(ProposedAction.HOLD_SHIELD, "Ammo low. Recommend raising shields.")

    def _reply(self, action: ProposedAction, say: str) -> ProposalReply:
        return ProposalReply(agent=self.name, action=action, say=say)
