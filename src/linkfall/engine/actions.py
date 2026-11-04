"""The concrete actions the engine can run."""

from enum import StrEnum


class Action(StrEnum):
    SUPPRESS = "suppress"
    FLANK = "flank"
    OVERCHARGE = "overcharge"
    HOLD_SHIELD = "hold_shield"
    COOLDOWN = "cooldown"
    AUDIT_COMMS = "audit_comms"
    DROP_SHIELDS = "drop_shields"
    ACCEPT_TRUCE = "accept_truce"
