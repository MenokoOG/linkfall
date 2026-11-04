"""The agent interface. Callers don't care whether an agent is a model or plain code."""

from dataclasses import dataclass
from typing import Literal, Protocol

from linkfall.agent_name import AgentName
from linkfall.agents.views import AgentView
from linkfall.provenance import Provenance
from linkfall.validator.reply import ProposalReply

type AgentKind = Literal["llm", "rules"]


@dataclass(frozen=True, slots=True)
class NoProposal:
    """An agent could not answer: timeout, malformed reply, or nothing to say."""

    reason: str


class Agent(Protocol):
    name: AgentName
    kind: AgentKind

    async def propose(self, view: AgentView) -> ProposalReply | NoProposal: ...


@dataclass(frozen=True, slots=True)
class Proposal:
    """A validated reply with what the supervisor adds. Agents never build this."""

    agent: AgentName
    kind: AgentKind
    reply: ProposalReply
    provenance: Provenance
    latency_ms: int
