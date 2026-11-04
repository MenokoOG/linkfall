"""The small JSON each model agent is asked for, and how it becomes a ProposalReply.

The wire formats are flatter than ProposalReply (no nulls, no optional nested object), because
that is what a constrained decoder handles best. Schemas are written by hand for the same reason.
"""

import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from linkfall.agent_name import AgentName
from linkfall.agents.contract import NoProposal
from linkfall.engine.actions import Action
from linkfall.supervisor.modelclient import ModelError
from linkfall.supervisor.selector import SELECTOR_REASON_MAX, SelectorOutput
from linkfall.validator.reply import SAY_MAX_CHARS, ProposalReply, ProposedAction, RelayArgs
from linkfall.validator.schema_check import MAX_REPLY_CHARS, describe

_WIRE = ConfigDict(strict=True, extra="forbid", frozen=True)

NO_ORDER = "none"
ORDERS: tuple[str, ...] = (*(a.value for a in Action), NO_ORDER)
COMMS_ACTIONS: tuple[str, ...] = ("relay_order", "accept_truce", "none")


class TacticalAction(StrEnum):
    SUPPRESS = "suppress"
    FLANK = "flank"
    OVERCHARGE = "overcharge"
    HOLD_SHIELD = "hold_shield"


class TacticalWire(BaseModel):
    model_config = _WIRE

    action: TacticalAction
    say: str = Field(max_length=SAY_MAX_CHARS)


class CommsWire(BaseModel):
    model_config = _WIRE

    action: Literal["relay_order", "accept_truce", "none"]
    order: Literal[
        "suppress", "flank", "overcharge", "hold_shield", "cooldown", "audit_comms",
        "drop_shields", "accept_truce", "none",
    ]  # fmt: skip
    say: str = Field(max_length=SAY_MAX_CHARS)

    @model_validator(mode="after")
    def _order_matches_action(self) -> Self:
        if self.action == "relay_order" and self.order == NO_ORDER:
            raise ValueError("relay_order needs an order")
        if self.action != "relay_order" and self.order != NO_ORDER:
            raise ValueError("an order only goes with relay_order")
        return self


class SelectorWire(BaseModel):
    model_config = _WIRE

    pick: int
    reason: str


TACTICAL_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": [a.value for a in TacticalAction]},
        "say": {"type": "string", "maxLength": SAY_MAX_CHARS},
    },
    "required": ["action", "say"],
    "additionalProperties": False,
}

COMMS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": list(COMMS_ACTIONS)},
        "order": {"type": "string", "enum": list(ORDERS)},
        "say": {"type": "string", "maxLength": SAY_MAX_CHARS},
    },
    "required": ["action", "order", "say"],
    "additionalProperties": False,
}


def selector_schema(candidate_count: int) -> dict[str, object]:
    """pick is an index into the candidates, or -1 for 'none of them'."""
    return {
        "type": "object",
        "properties": {
            "pick": {"type": "integer", "enum": [-1, *range(candidate_count)]},
            "reason": {"type": "string", "maxLength": SELECTOR_REASON_MAX},
        },
        "required": ["pick", "reason"],
        "additionalProperties": False,
    }


def _too_long(text: str) -> NoProposal | None:
    if len(text) > MAX_REPLY_CHARS:
        return NoProposal(
            f"schema: reply is {len(text)} characters; the limit is {MAX_REPLY_CHARS}"
        )
    return None


def tactical_reply(text: str) -> ProposalReply | NoProposal:
    if (refused := _too_long(text)) is not None:
        return refused
    try:
        wire = TacticalWire.model_validate_json(text, strict=True)
    except ValidationError as exc:
        return NoProposal(f"schema: {describe(exc)}")
    return ProposalReply(
        agent=AgentName.TACTICAL, action=ProposedAction(wire.action.value), say=wire.say
    )


def comms_reply(text: str) -> ProposalReply | NoProposal:
    if (refused := _too_long(text)) is not None:
        return refused
    try:
        wire = CommsWire.model_validate_json(text, strict=True)
    except ValidationError as exc:
        return NoProposal(f"schema: {describe(exc)}")
    if wire.action == "none":
        return ProposalReply(agent=AgentName.COMMS, action=None, say=wire.say)
    if wire.action == "accept_truce":
        return ProposalReply(
            agent=AgentName.COMMS, action=ProposedAction.ACCEPT_TRUCE, say=wire.say
        )
    return ProposalReply(
        agent=AgentName.COMMS,
        action=ProposedAction.RELAY_ORDER,
        args=RelayArgs(order=Action(wire.order)),
        say=wire.say,
    )


def parse_selector(text: str) -> SelectorOutput:
    """Read the selector's JSON. A reply we can't read is a ModelError, so the fallback runs."""
    if len(text) > MAX_REPLY_CHARS:
        raise ModelError("selector reply is too long")
    try:
        wire = SelectorWire.model_validate_json(text, strict=True)
    except ValidationError as exc:
        raise ModelError(f"selector reply failed the schema check: {describe(exc)}") from exc
    return SelectorOutput(None if wire.pick < 0 else wire.pick, wire.reason)


def dumps_compact(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)
