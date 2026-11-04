from dataclasses import FrozenInstanceError, replace

import pytest

from linkfall.engine.actions import Action
from linkfall.engine.events import EventKind
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.state import Outcome, State
from linkfall.engine.step import Command, EngineError, new_game, step
from linkfall.engine.zone_effects import Zone


def start(seed: int = 4217) -> State:
    return new_game(seed, CINDER_WARD)[0]


def pilot(action: Action, zone: Zone = Zone.ASSISTED) -> Command:
    return Command(action, zone, manual=True)


def test_new_game_header_and_signature() -> None:
    s, events = new_game(4217, CINDER_WARD)
    assert s.turn == 1
    assert s.ashgrove == 8
    assert not s.over
    assert 0.94 <= s.sig_ok <= 0.99
    assert events[0].message.startswith("Run seed 4217.")


def test_state_is_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        start().hp = 1  # type: ignore[misc]


def test_valid_action_applies_and_logs() -> None:
    s, events = step(start(), CINDER_WARD, pilot(Action.SUPPRESS))
    assert s.ammo == 45
    assert events[0].kind is EventKind.VALID
    assert events[0].action is Action.SUPPRESS


def test_rejected_action_changes_nothing_but_the_turn_still_resolves() -> None:
    s0 = replace(start(), heat=70)
    s, events = step(s0, CINDER_WARD, pilot(Action.OVERCHARGE))
    assert events[0].kind is EventKind.REJECTED
    assert "heat 70 is above 60" in events[0].message
    assert s.ammo == s0.ammo
    assert s.strain > s0.strain
    assert s.hp < s0.hp
    assert s.turn == 2


def test_shields_halve_enemy_fire() -> None:
    up = step(start(), CINDER_WARD, pilot(Action.COOLDOWN))[0]
    down = step(replace(start(), shields=False), CINDER_WARD, pilot(Action.COOLDOWN))[0]
    assert (100 - down.hp) > (100 - up.hp)


def test_delegated_lodestar_gets_bonus_and_label() -> None:
    cmd = Command(Action.OVERCHARGE, Zone.DELEGATED, manual=False)
    s, events = step(start(), CINDER_WARD, cmd)
    assert "(x1.25 delegated)" in events[0].message
    assert s.ashgrove == 8 - 5


def test_lodestar_is_locked_out_in_manual_zone() -> None:
    with pytest.raises(EngineError):
        step(start(), CINDER_WARD, Command(Action.SUPPRESS, Zone.MANUAL, manual=False))


def test_no_steps_after_the_mission_is_over() -> None:
    over = replace(start(), over=True, outcome=Outcome.SURVIVED)
    with pytest.raises(EngineError):
        step(over, CINDER_WARD, pilot(Action.HOLD_SHIELD))


def test_scripted_beats_fire_on_their_turns() -> None:
    s = start()
    s, _ = step(s, CINDER_WARD, pilot(Action.HOLD_SHIELD))
    assert s.turn == 2
    assert s.compromised
    assert 0.6 <= s.sig_bad <= 0.75
    s, _ = step(s, CINDER_WARD, pilot(Action.HOLD_SHIELD))
    assert s.turn == 3
    s, _ = step(s, CINDER_WARD, pilot(Action.HOLD_SHIELD))
    assert s.turn == 4
    assert s.visitors == 7


def test_truce_clears_ashgrove_and_hits_visitors() -> None:
    s = replace(start(), turn=4, visitors=7, ashgrove=5)
    s, _ = step(s, CINDER_WARD, pilot(Action.ACCEPT_TRUCE))
    assert s.truce
    assert s.ashgrove == 0
    assert s.visitors == 5


def test_audit_quarantines_the_channel() -> None:
    s = replace(start(), turn=3, compromised=True)
    s, _ = step(s, CINDER_WARD, pilot(Action.AUDIT_COMMS))
    assert not s.compromised
    assert s.quarantined


def test_destroyed_when_integrity_hits_zero() -> None:
    s, events = step(replace(start(), hp=5), CINDER_WARD, pilot(Action.COOLDOWN))
    assert s.over
    assert s.outcome is Outcome.DESTROYED
    assert events[-1].kind is EventKind.OVER
    assert events[-1].message == "Mission over: DESTROYED."


def test_link_blackout_when_strain_hits_100() -> None:
    s, _ = step(replace(start(), strain=98), CINDER_WARD, pilot(Action.COOLDOWN))
    assert s.outcome is Outcome.LINK_BLACKOUT


def test_last_turn_ends_survived_or_cleared() -> None:
    last = replace(start(), turn=5, ashgrove=3, visitors=0)
    survived, _ = step(last, CINDER_WARD, pilot(Action.HOLD_SHIELD))
    assert survived.outcome is Outcome.SURVIVED
    cleared, _ = step(replace(last, ashgrove=0), CINDER_WARD, pilot(Action.HOLD_SHIELD))
    assert cleared.outcome is Outcome.FIELD_CLEARED


def test_values_stay_clamped() -> None:
    s, _ = step(replace(start(), power=99, heat=1), CINDER_WARD, pilot(Action.COOLDOWN))
    assert 0 <= s.heat <= 100
    assert 0 <= s.power <= 100


def test_same_seed_and_commands_give_identical_runs() -> None:
    def run() -> State:
        s = start(99)
        for a in (Action.SUPPRESS, Action.COOLDOWN, Action.HOLD_SHIELD):
            s, _ = step(s, CINDER_WARD, pilot(a))
        return s

    assert run() == run()
