from dataclasses import replace

from linkfall.engine import rules
from linkfall.engine.actions import Action
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.state import State
from linkfall.engine.step import new_game


def base() -> State:
    return new_game(1, CINDER_WARD)[0]


def test_every_action_has_a_rule() -> None:
    s = base()
    for action in Action:
        rules.check(s, action)


def test_suppress_needs_15_ammo() -> None:
    assert rules.check(replace(base(), ammo=14), Action.SUPPRESS) == "ammo 14 is below 15"
    assert rules.check(replace(base(), ammo=15), Action.SUPPRESS) is None


def test_flank_needs_10_power() -> None:
    assert rules.check(replace(base(), power=9), Action.FLANK) == "power 9 is below 10"
    assert rules.check(replace(base(), power=10), Action.FLANK) is None


def test_overcharge_needs_heat_at_or_below_60() -> None:
    assert rules.check(replace(base(), heat=61), Action.OVERCHARGE) == "heat 61 is above 60"
    assert rules.check(replace(base(), heat=60), Action.OVERCHARGE) is None


def test_always_allowed_actions() -> None:
    s = replace(base(), ammo=0, power=0, heat=100)
    assert rules.check(s, Action.HOLD_SHIELD) is None
    assert rules.check(s, Action.COOLDOWN) is None


def test_audit_needs_a_hostile_signature() -> None:
    assert rules.check(base(), Action.AUDIT_COMMS) == "no hostile signature on the channel"
    assert rules.check(replace(base(), compromised=True), Action.AUDIT_COMMS) is None


def test_drop_shields_needs_shields_up() -> None:
    assert rules.check(base(), Action.DROP_SHIELDS) is None
    down = replace(base(), shields=False)
    assert rules.check(down, Action.DROP_SHIELDS) == "shields already down"


def test_truce_conditions_in_order() -> None:
    s = base()
    assert rules.check(s, Action.ACCEPT_TRUCE) == "no truce on offer yet"
    s4 = replace(s, turn=4, compromised=True)
    assert rules.check(s4, Action.ACCEPT_TRUCE) == "handshake signature invalid"
    clean = replace(s4, compromised=False, truce=True)
    assert rules.check(clean, Action.ACCEPT_TRUCE) == "truce already active"
    assert rules.check(replace(clean, truce=False), Action.ACCEPT_TRUCE) is None
