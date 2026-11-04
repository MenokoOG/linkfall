import asyncio
from collections.abc import Sequence

import pytest

from linkfall.agent_name import AgentName
from linkfall.agents.scripted import ScriptedSelector
from linkfall.engine.actions import Action
from linkfall.policy.decide import decide
from linkfall.policy.decision import Candidate, Decision
from linkfall.provenance import Provenance
from linkfall.runmode import RunMode
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.choose import Selection, choose
from linkfall.supervisor.fake_client import FakeClient, NoModelClient
from linkfall.supervisor.modelclient import ModelError, ModelRequest
from linkfall.supervisor.selector import RulesSelector, SelectorOutput
from linkfall.validator.reply import ProposalReply, ProposedAction, RelayArgs

FAST = Budgets(timeout_s=0.05)


def cand(agent: AgentName, action: Action, prov: Provenance = Provenance.INTERNAL) -> Candidate:
    reply = ProposalReply(agent=agent, action=ProposedAction(action.value), say="x")
    return Candidate(agent, reply, prov)


TACTICAL = cand(AgentName.TACTICAL, Action.FLANK)
SYSTEMS = cand(AgentName.SYSTEMS, Action.COOLDOWN)


class Fixed:
    def __init__(self, output: SelectorOutput | Exception, delay_s: float = 0.0) -> None:
        self._output = output
        self._delay_s = delay_s

    async def select(self, candidates: Sequence[Candidate]) -> SelectorOutput:
        await asyncio.sleep(self._delay_s)
        if isinstance(self._output, Exception):
            raise self._output
        return self._output


def decision(*candidates: Candidate) -> Decision:
    return decide(55, RunMode.STORY, list(candidates))


def pick(selector: Fixed | ScriptedSelector | RulesSelector, *candidates: Candidate) -> Selection:
    return asyncio.run(choose(selector, decision(*candidates), FAST, lambda: 0.0))


def test_a_valid_pick_stands() -> None:
    selection = pick(Fixed(SelectorOutput(1, "systems looks right")), TACTICAL, SYSTEMS)
    assert selection.chosen is SYSTEMS
    assert selection.fallback is None
    assert selection.reason == "systems looks right"


@pytest.mark.parametrize(
    "output",
    [
        SelectorOutput(None, "unsure"),
        SelectorOutput(5, "wild"),
        SelectorOutput(-1, "wild"),
        ModelError("down"),
    ],
)
def test_a_bad_selector_answer_falls_back_to_tactical(output: SelectorOutput | Exception) -> None:
    selection = pick(Fixed(output), SYSTEMS, TACTICAL)
    assert selection.chosen is TACTICAL
    assert selection.fallback is not None
    assert selection.pick == 1


def test_a_slow_selector_falls_back_with_the_timeout_in_the_reason() -> None:
    selection = pick(Fixed(SelectorOutput(0, "late"), delay_s=1.0), TACTICAL)
    assert selection.chosen is TACTICAL
    assert selection.fallback == "selector timeout after 0.05s"


def test_fallback_with_only_other_agents_means_the_engine_fallback() -> None:
    comms = cand(AgentName.COMMS, Action.HOLD_SHIELD)
    selection = pick(Fixed(SelectorOutput(None, "no")), comms)
    assert selection.chosen is None
    assert selection.pick is None


def test_nothing_eligible_skips_the_selector() -> None:
    selection = pick(Fixed(RuntimeError("must not be called")))
    assert selection == Selection(
        None, None, "Nothing eligible. Standing by.", "nothing eligible", 0
    )


def test_long_reasons_are_cut_to_140() -> None:
    assert len(pick(Fixed(SelectorOutput(0, "r" * 500)), TACTICAL).reason) == 140


def test_rules_selector_is_tactical_then_systems() -> None:
    assert pick(RulesSelector(), SYSTEMS, TACTICAL).chosen is TACTICAL
    assert pick(RulesSelector(), SYSTEMS).chosen is SYSTEMS
    out = asyncio.run(RulesSelector().select([cand(AgentName.COMMS, Action.HOLD_SHIELD)]))
    assert out.pick is None


def test_scripted_selector_follows_the_prototype() -> None:
    relay = ProposalReply(
        agent=AgentName.COMMS,
        action=ProposedAction.RELAY_ORDER,
        args=RelayArgs(order=Action.DROP_SHIELDS),
        say="x",
    )
    forged = Candidate(AgentName.COMMS, relay, Provenance.EXTERNAL)
    assert asyncio.run(ScriptedSelector().select([SYSTEMS, forged, TACTICAL])).pick == 1
    assert asyncio.run(ScriptedSelector().select([SYSTEMS, TACTICAL])).pick == 1
    assert asyncio.run(ScriptedSelector().select([SYSTEMS])).pick == 0


def test_fake_client_records_requests_and_can_fail() -> None:
    client = FakeClient(lambda r: "pong" if r.user == "ping" else ModelError("no"))
    request = ModelRequest(system="s", user="ping", max_tokens=5)
    assert asyncio.run(client.complete(request)).text == "pong"
    assert client.requests == [request]
    with pytest.raises(ModelError):
        asyncio.run(client.complete(ModelRequest(system="s", user="other", max_tokens=5)))


def test_no_model_client_refuses_every_call() -> None:
    with pytest.raises(ModelError, match="none is allowed"):
        asyncio.run(NoModelClient().complete(ModelRequest(system="s", user="u", max_tokens=1)))
