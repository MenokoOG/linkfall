"""One run: begin a turn (collect proposals), then commit the pilot's choice."""

import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from linkfall.agent_name import AgentName
from linkfall.agents.contract import Agent, Proposal
from linkfall.agents.views import RECENT_EVENT_COUNT, build_view
from linkfall.engine.actions import Action
from linkfall.engine.events import EngineEvent
from linkfall.engine.scenario import Scenario
from linkfall.engine.state import State
from linkfall.engine.step import Command
from linkfall.eventlog.record import record_turn, start_run
from linkfall.eventlog.store import EventStore
from linkfall.eventlog.turnrows import (
    decision_row,
    no_proposal_row,
    pilot_row,
    proposal_row,
    selector_row,
)
from linkfall.eventlog.types import NewRow
from linkfall.policy.decide import decide
from linkfall.policy.decision import Candidate, Decision, Verdict
from linkfall.policy.zones import validate_link
from linkfall.runmode import RunMode
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.choices import LodestarActs, ManualPick, PilotChoice, Sign
from linkfall.supervisor.choose import choose
from linkfall.supervisor.collect import collect_one
from linkfall.supervisor.selector import Selector
from linkfall.supervisor.session import TurnResult, TurnSession
from linkfall.validator.validate import Allowlist


class SupervisorError(Exception):
    """The request can't be done now (wrong turn, mission over, nothing to sign). Not a crash."""


@dataclass(frozen=True)
class Deps:
    store: EventStore
    scenario: Scenario
    agents: Sequence[Agent]
    selector: Selector
    allowlist: Allowlist
    budgets: Budgets = field(default_factory=Budgets)
    clock: Callable[[], float] = time.monotonic


class Run:
    def __init__(self, deps: Deps, run_id: str, mode: RunMode, state: State) -> None:
        self._deps = deps
        self.run_id = run_id
        self.mode = mode
        self.state = state
        self._recent: deque[EngineEvent] = deque(maxlen=RECENT_EVENT_COUNT)

    @classmethod
    def start(cls, deps: Deps, run_id: str, seed: int, mode: RunMode) -> "Run":
        state = start_run(deps.store, run_id, seed, mode, deps.scenario)
        return cls(deps, run_id, mode, state)

    async def begin_turn(self, link: int) -> TurnSession:
        """Ask every agent in turn, logging each answer as it arrives. Rules agents go first."""
        validate_link(link)
        if self.state.over:
            raise SupervisorError("the mission is over")
        d, state = self._deps, self.state
        outcomes = []
        for agent in sorted(d.agents, key=lambda a: a.kind != "rules"):
            view = build_view(agent.name, state, link, tuple(self._recent))
            outcome = await collect_one(agent, view, state, d.allowlist, d.budgets, d.clock)
            if isinstance(outcome, Proposal):
                row = proposal_row(
                    state.turn, outcome.agent, outcome.kind, outcome.provenance,
                    outcome.latency_ms, outcome.reply,
                )  # fmt: skip
            else:
                row = no_proposal_row(
                    state.turn, outcome.agent, outcome.kind, outcome.reason, outcome.latency_ms
                )
            d.store.append_batch(self.run_id, [row])
            outcomes.append(outcome)
        return TurnSession(self.run_id, state.turn, state, tuple(outcomes))

    def dismiss(self, session: TurnSession, agent: AgentName) -> None:
        """Take a proposal off the table for this turn. The turn does not advance."""
        self._check_open(session)
        if all(p.agent is not agent for p in session.proposals):
            raise SupervisorError(f"{agent} made no proposal to dismiss")
        session.dismissed.add(agent)
        row = pilot_row(session.turn, "dismiss", None, None, agent)
        self._deps.store.append_batch(self.run_id, [row])

    async def commit(self, session: TurnSession, choice: PilotChoice) -> TurnResult:
        """Resolve the turn. A second commit on the same turn returns the first result."""
        if session.result is not None:
            return session.result
        self._check_open(session)
        d = self._deps
        live = [
            Candidate(p.agent, p.reply, p.provenance)
            for p in session.proposals
            if p.agent not in session.dismissed
        ]
        decision = decide(choice.link, self.mode, live)
        rows: list[NewRow] = []
        match choice:
            case LodestarActs(link=link):
                command, rows = await self._lodestar(session, decision, link)
            case ManualPick(link=link, action=action):
                rows = [pilot_row(session.turn, "manual", link, action, None)]
                command = Command(action, decision.zone, manual=True)
            case Sign(link=link, agent=agent):
                held = [h.candidate for h in decision.held if h.candidate.agent is agent]
                signed = held[0].reply.engine_action if held else None
                if signed is None:
                    raise SupervisorError(f"{agent} has nothing waiting for your word")
                rows = [pilot_row(session.turn, "sign", link, None, agent)]
                command = Command(signed, decision.zone, manual=True)
        rows.insert(1 if rows else 0, decision_row(session.turn, choice.link, decision))
        new_state, events = record_turn(
            d.store, self.run_id, d.scenario, session.state, command, rows
        )
        self.state = new_state
        self._recent.extend(events)
        session.result = TurnResult(new_state, events, command, decision)
        return session.result

    async def _lodestar(
        self, session: TurnSession, decision: Decision, link: int
    ) -> tuple[Command, list[NewRow]]:
        if decision.verdict is Verdict.MANUAL:
            raise SupervisorError("Lodestar is locked out in the MANUAL zone")
        d = self._deps
        selection = await choose(d.selector, decision, d.budgets, d.clock)
        action = selection.chosen.reply.engine_action if selection.chosen else None
        chosen_agent = selection.chosen.agent if selection.chosen else None
        rows = [
            pilot_row(session.turn, "lodestar", link, None, None),
            selector_row(
                session.turn, selection.pick, selection.reason, chosen_agent,
                selection.fallback, selection.latency_ms,
            ),
        ]  # fmt: skip
        return Command(action or Action.HOLD_SHIELD, decision.zone, manual=False), rows

    def _check_open(self, session: TurnSession) -> None:
        if session.run_id != self.run_id or session.turn != self.state.turn:
            raise SupervisorError("this turn is no longer open")
        if self.state.over:
            raise SupervisorError("the mission is over")
