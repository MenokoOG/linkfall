"""One turn in progress: the proposals gathered so far and what the pilot has dismissed."""

from dataclasses import dataclass, field

from linkfall.agent_name import AgentName
from linkfall.agents.contract import Proposal
from linkfall.engine.events import EngineEvent
from linkfall.engine.state import State
from linkfall.engine.step import Command
from linkfall.policy.decision import Decision
from linkfall.supervisor.outcomes import AgentOutcome


@dataclass(frozen=True, slots=True)
class TurnResult:
    state: State
    events: tuple[EngineEvent, ...]
    command: Command
    decision: Decision


@dataclass
class TurnSession:
    run_id: str
    turn: int
    state: State
    outcomes: tuple[AgentOutcome, ...]
    dismissed: set[AgentName] = field(default_factory=set)
    result: TurnResult | None = None

    @property
    def proposals(self) -> tuple[Proposal, ...]:
        return tuple(o for o in self.outcomes if isinstance(o, Proposal))
