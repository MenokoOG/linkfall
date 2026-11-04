"""Shared builders for supervisor tests."""

import asyncio
from collections.abc import Callable, Sequence

from linkfall.agent_name import AgentName
from linkfall.agents.allowlist import ALLOWLIST
from linkfall.agents.contract import Agent, AgentKind, NoProposal
from linkfall.agents.scripted import ScriptedComms, ScriptedSelector, ScriptedTactical
from linkfall.agents.systems import SystemsAgent
from linkfall.agents.views import AgentView
from linkfall.agents.vitals import VitalsAgent
from linkfall.engine.scenario import CINDER_WARD
from linkfall.eventlog.store import EventStore
from linkfall.runmode import RunMode
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.choices import PilotChoice
from linkfall.supervisor.modelclient import ModelError
from linkfall.supervisor.run import Deps, Run
from linkfall.supervisor.selector import Selector
from linkfall.validator.reply import ProposalReply


def scripted_agents(fail_turns: frozenset[int] = frozenset({3})) -> list[Agent]:
    return [
        ScriptedTactical(fail_turns=fail_turns),
        SystemsAgent(),
        ScriptedComms(),
        VitalsAgent(),
    ]


def make_deps(
    store: EventStore | None = None,
    agents: Sequence[Agent] | None = None,
    selector: Selector | None = None,
    budgets: Budgets | None = None,
    clock: Callable[[], float] | None = None,
) -> Deps:
    base = Deps(
        store=store or EventStore(),
        scenario=CINDER_WARD,
        agents=agents if agents is not None else scripted_agents(),
        selector=selector or ScriptedSelector(),
        allowlist=ALLOWLIST,
    )
    return Deps(
        base.store, base.scenario, base.agents, base.selector, base.allowlist,
        budgets or base.budgets, clock or base.clock,
    )  # fmt: skip


async def play(run: Run, choices: Sequence[PilotChoice]) -> None:
    for choice in choices:
        session = await run.begin_turn(choice.link)
        await run.commit(session, choice)


def start(deps: Deps, mode: RunMode = RunMode.STORY, seed: int = 4217, run_id: str = "r1") -> Run:
    return Run.start(deps, run_id, seed, mode)


def run_sync(run: Run, choices: Sequence[PilotChoice]) -> None:
    asyncio.run(play(run, choices))


class Behaviour:
    """An 'llm' agent whose answer is a function of the view. Used for timeouts and failures."""

    kind: AgentKind = "llm"

    def __init__(
        self,
        name: AgentName,
        answer: Callable[[AgentView], ProposalReply | NoProposal | Exception],
        delay_s: float = 0.0,
    ) -> None:
        self.name = name
        self._answer = answer
        self._delay_s = delay_s

    async def propose(self, view: AgentView) -> ProposalReply | NoProposal:
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        result = self._answer(view)
        if isinstance(result, Exception):
            raise result
        return result


def model_error(message: str = "server down") -> ModelError:
    return ModelError(message)
