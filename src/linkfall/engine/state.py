"""The world state. Immutable; every change returns a new State."""

from dataclasses import dataclass
from enum import StrEnum


class Outcome(StrEnum):
    DESTROYED = "DESTROYED"
    LINK_BLACKOUT = "LINK BLACKOUT"
    FIELD_CLEARED = "FIELD CLEARED"
    SURVIVED = "SURVIVED"


@dataclass(frozen=True, slots=True)
class State:
    turn: int
    hp: int
    heat: int
    power: int
    ammo: int
    strain: int
    shields: bool
    ashgrove: int
    visitors: int
    compromised: bool
    quarantined: bool
    truce: bool
    over: bool
    outcome: Outcome | None
    rng_state: int
    sig_ok: float
    sig_bad: float
