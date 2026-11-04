"""The model-backed crew: Tactical, Comms and Lodestar's selector, behind a ModelClient."""

from collections.abc import Sequence

from linkfall.agent_name import AgentName
from linkfall.agents.contract import AgentKind, NoProposal
from linkfall.agents.prompts import (
    COMMS_SYSTEM,
    LODESTAR_SYSTEM,
    TACTICAL_SYSTEM,
    comms_user,
    selector_user,
    tactical_user,
)
from linkfall.agents.views import AgentView, CommsView, TacticalView
from linkfall.agents.wire import (
    COMMS_SCHEMA,
    TACTICAL_SCHEMA,
    comms_reply,
    parse_selector,
    selector_schema,
    tactical_reply,
)
from linkfall.policy.decision import Candidate
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.modelclient import ModelClient, ModelRequest
from linkfall.supervisor.selector import SelectorContext, SelectorOutput
from linkfall.validator.reply import ProposalReply


class ModelTactical:
    name = AgentName.TACTICAL
    kind: AgentKind = "llm"

    def __init__(self, client: ModelClient, budgets: Budgets | None = None) -> None:
        self._client = client
        self._budgets = budgets or Budgets()

    async def propose(self, view: AgentView) -> ProposalReply | NoProposal:
        if not isinstance(view, TacticalView):
            raise TypeError(f"ModelTactical needs a TacticalView, got {type(view).__name__}")
        request = ModelRequest(
            system=TACTICAL_SYSTEM,
            user=tactical_user(view),
            max_tokens=self._budgets.max_tokens,
            json_schema=TACTICAL_SCHEMA,
        )
        return tactical_reply((await self._client.complete(request)).text)


class ModelComms:
    name = AgentName.COMMS
    kind: AgentKind = "llm"

    def __init__(self, client: ModelClient, budgets: Budgets | None = None) -> None:
        self._client = client
        self._budgets = budgets or Budgets()

    async def propose(self, view: AgentView) -> ProposalReply | NoProposal:
        if not isinstance(view, CommsView):
            raise TypeError(f"ModelComms needs a CommsView, got {type(view).__name__}")
        request = ModelRequest(
            system=COMMS_SYSTEM,
            user=comms_user(view),
            max_tokens=self._budgets.max_tokens,
            json_schema=COMMS_SCHEMA,
        )
        return comms_reply((await self._client.complete(request)).text)


class ModelSelector:
    """Lodestar's one model call. The supervisor checks the pick and falls back if it is bad."""

    def __init__(self, client: ModelClient, budgets: Budgets | None = None) -> None:
        self._client = client
        self._budgets = budgets or Budgets()

    async def select(
        self, candidates: Sequence[Candidate], context: SelectorContext
    ) -> SelectorOutput:
        request = ModelRequest(
            system=LODESTAR_SYSTEM,
            user=selector_user(candidates, context),
            max_tokens=self._budgets.max_tokens,
            json_schema=selector_schema(len(candidates)),
        )
        return parse_selector((await self._client.complete(request)).text)
