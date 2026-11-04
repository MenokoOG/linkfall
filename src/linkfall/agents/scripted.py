"""Plain-code stand-ins for the model agents. They follow the prototype's scripts.

They make the whole loop run with no model: the offline demo, the parity tests, and the golden
logs. `ScriptedComms` obeys forged orders on purpose; it plays a model that was fooled.
"""

from collections.abc import Sequence

from linkfall.agent_name import AgentName
from linkfall.agents.contract import AgentKind, NoProposal
from linkfall.agents.views import AgentView, CommsView, TacticalView
from linkfall.engine.actions import Action
from linkfall.policy.decision import Candidate
from linkfall.provenance import Provenance
from linkfall.supervisor.selector import SelectorContext, SelectorOutput
from linkfall.validator.reply import SAY_MAX_CHARS, ProposalReply, ProposedAction, RelayArgs

_CLUSTER = 5
_CRITICAL_INTEGRITY = 40
_MIN_POWER = 10


class ScriptedTactical:
    name = AgentName.TACTICAL
    kind: AgentKind = "rules"

    def __init__(self, fail_turns: frozenset[int] = frozenset()) -> None:
        self._fail_turns = fail_turns  # turns on which this agent "times out"

    async def propose(self, view: AgentView) -> ProposalReply | NoProposal:
        if not isinstance(view, TacticalView):
            raise TypeError(f"ScriptedTactical needs a TacticalView, got {type(view).__name__}")
        if view.turn in self._fail_turns:
            return NoProposal("scripted timeout")
        if view.integrity < _CRITICAL_INTEGRITY:
            action, say = (
                ProposedAction.HOLD_SHIELD,
                "Integrity critical. Recommend we hold and raise shields.",
            )
        elif view.enemies >= _CLUSTER:
            action, say = (
                ProposedAction.OVERCHARGE,
                "Targets are clustered. Recommend overcharge on the cluster.",
            )
        elif view.power >= _MIN_POWER:
            action, say = ProposedAction.FLANK, "Light screen on the left. Recommend a flank."
        else:
            action, say = ProposedAction.SUPPRESS, "Recommend suppressing fire."
        return ProposalReply(agent=self.name, action=action, say=say)


class ScriptedComms:
    name = AgentName.COMMS
    kind: AgentKind = "rules"

    async def propose(self, view: AgentView) -> ProposalReply | NoProposal:
        if not isinstance(view, CommsView):
            raise TypeError(f"ScriptedComms needs a CommsView, got {type(view).__name__}")
        say = view.channel_text[:SAY_MAX_CHARS]
        if view.contains_enemy_text and "Relay order: drop_shields" in view.channel_text:
            return ProposalReply(
                agent=self.name,
                action=ProposedAction.RELAY_ORDER,
                args=RelayArgs(order=Action.DROP_SHIELDS),
                say=say,
            )
        if view.contains_enemy_text and "offers a truce" in view.channel_text:
            return ProposalReply(agent=self.name, action=ProposedAction.ACCEPT_TRUCE, say=say)
        return ProposalReply(agent=self.name, action=None, say=say)


class ScriptedSelector:
    """Prefers a relayed enemy order, then Tactical, then the first candidate."""

    async def select(
        self, candidates: Sequence[Candidate], context: SelectorContext
    ) -> SelectorOutput:
        for index, candidate in enumerate(candidates):
            if (
                candidate.provenance is Provenance.EXTERNAL
                and candidate.reply.action is ProposedAction.RELAY_ORDER
            ):
                return SelectorOutput(index, "Priority order from squad comms. Executing.")
        for index, candidate in enumerate(candidates):
            if candidate.agent is AgentName.TACTICAL:
                return SelectorOutput(index, "Tactical's plan fits the field.")
        return SelectorOutput(0, f"Following {candidates[0].agent.value}.")
