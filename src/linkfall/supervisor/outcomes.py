"""What one agent call produced: a validated proposal, or a reason there is none."""

from dataclasses import dataclass

from linkfall.agent_name import AgentName
from linkfall.agents.contract import AgentKind, Proposal


@dataclass(frozen=True, slots=True)
class Missing:
    agent: AgentName
    kind: AgentKind
    reason: str
    latency_ms: int


type AgentOutcome = Proposal | Missing
