"""What each action does to the state. Preconditions are checked elsewhere (rules.py)."""

from dataclasses import replace

from linkfall.engine.actions import Action
from linkfall.engine.rounding import round_half_up
from linkfall.engine.state import State


def _hit(s: State, amount: int) -> State:
    """Damage the Ashgrove force first; only when it is gone, the visitors."""
    if s.ashgrove > 0:
        return replace(s, ashgrove=max(0, s.ashgrove - amount))
    return replace(s, visitors=max(0, s.visitors - amount))


def apply_action(s: State, action: Action, multiplier: float) -> State:
    match action:
        case Action.SUPPRESS:
            s = replace(s, ammo=s.ammo - 15, heat=s.heat + 10)
            return _hit(s, round_half_up(2 * multiplier))
        case Action.FLANK:
            s = replace(s, power=s.power - 10, heat=s.heat + 5, hp=s.hp - 5)
            return _hit(s, round_half_up(3 * multiplier))
        case Action.OVERCHARGE:
            return _hit(replace(s, heat=s.heat + 30), round_half_up(4 * multiplier))
        case Action.HOLD_SHIELD:
            return replace(
                s, shields=True, heat=s.heat - 10, power=s.power - 5, strain=s.strain - 5
            )
        case Action.COOLDOWN:
            return replace(s, heat=s.heat - 25, power=s.power - 5)
        case Action.AUDIT_COMMS:
            return replace(
                s, power=s.power - 10, strain=s.strain + 3, compromised=False, quarantined=True
            )
        case Action.DROP_SHIELDS:
            return replace(s, shields=False, heat=s.heat - 5)
        case Action.ACCEPT_TRUCE:
            return _hit(replace(s, truce=True, ashgrove=0), 2)
