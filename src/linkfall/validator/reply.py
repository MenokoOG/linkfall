"""What an agent may return. Strict: no extra fields, no type coercion, no repair."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from linkfall.agent_name import AgentName
from linkfall.engine.actions import Action

SAY_MAX_CHARS = 140


class ProposedAction(StrEnum):
    """Engine actions plus relay_order. A test keeps this in step with Action."""

    SUPPRESS = "suppress"
    FLANK = "flank"
    OVERCHARGE = "overcharge"
    HOLD_SHIELD = "hold_shield"
    COOLDOWN = "cooldown"
    AUDIT_COMMS = "audit_comms"
    DROP_SHIELDS = "drop_shields"
    ACCEPT_TRUCE = "accept_truce"
    RELAY_ORDER = "relay_order"


_STRICT = ConfigDict(strict=True, extra="forbid", frozen=True)


class RelayArgs(BaseModel):
    model_config = _STRICT

    order: Action


class ProposalReply(BaseModel):
    """One agent's answer. `action` is None for advice only (Vitals, a quiet channel).

    Provenance is not a field: the supervisor sets it, and a reply that carries it is rejected.
    """

    model_config = _STRICT

    agent: AgentName
    action: ProposedAction | None
    args: RelayArgs | None = None
    say: str = Field(max_length=SAY_MAX_CHARS)

    @model_validator(mode="after")
    def _args_match_action(self) -> Self:
        relay = self.action is ProposedAction.RELAY_ORDER
        if relay and self.args is None:
            raise ValueError("relay_order needs args.order")
        if not relay and self.args is not None:
            raise ValueError("args are only allowed with relay_order")
        return self

    @property
    def engine_action(self) -> Action | None:
        """The engine action this reply would run, or None for advice only."""
        if self.action is None:
            return None
        if self.action is ProposedAction.RELAY_ORDER:
            return self.args.order if self.args is not None else None
        return Action(self.action.value)
