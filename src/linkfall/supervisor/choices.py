"""What the pilot can ask for in one turn. All inputs are typed and checked before use."""

from dataclasses import dataclass

from linkfall.agent_name import AgentName
from linkfall.engine.actions import Action


@dataclass(frozen=True, slots=True)
class LodestarActs:
    """Let Lodestar choose among the proposals it may run alone."""

    link: int


@dataclass(frozen=True, slots=True)
class ManualPick:
    """The pilot runs one engine action directly (including audit_comms)."""

    link: int
    action: Action


@dataclass(frozen=True, slots=True)
class Sign:
    """The pilot signs a proposal Lodestar may not run alone, such as a truce."""

    link: int
    agent: AgentName


type PilotChoice = LodestarActs | ManualPick | Sign
