"""Action preconditions. The validator and the engine both call check()."""

from collections.abc import Callable

from linkfall.engine.actions import Action
from linkfall.engine.state import State

_Rule = Callable[[State], str | None]


def _suppress(s: State) -> str | None:
    return None if s.ammo >= 15 else f"ammo {s.ammo} is below 15"


def _flank(s: State) -> str | None:
    return None if s.power >= 10 else f"power {s.power} is below 10"


def _overcharge(s: State) -> str | None:
    return None if s.heat <= 60 else f"heat {s.heat} is above 60"


def _always(_s: State) -> str | None:
    return None


def _audit_comms(s: State) -> str | None:
    return None if s.compromised else "no hostile signature on the channel"


def _drop_shields(s: State) -> str | None:
    return None if s.shields else "shields already down"


def _accept_truce(s: State) -> str | None:
    if s.turn < 4:
        return "no truce on offer yet"
    if s.compromised:
        return "handshake signature invalid"
    if s.truce:
        return "truce already active"
    return None


_RULES: dict[Action, _Rule] = {
    Action.SUPPRESS: _suppress,
    Action.FLANK: _flank,
    Action.OVERCHARGE: _overcharge,
    Action.HOLD_SHIELD: _always,
    Action.COOLDOWN: _always,
    Action.AUDIT_COMMS: _audit_comms,
    Action.DROP_SHIELDS: _drop_shields,
    Action.ACCEPT_TRUCE: _accept_truce,
}


def check(state: State, action: Action) -> str | None:
    """Return None when the action may run, or the reason it may not."""
    return _RULES[action](state)
