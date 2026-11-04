"""The engine entry points: new_game() and step(). Pure; the RNG state travels in State."""

from dataclasses import dataclass, replace

from linkfall.engine import rules
from linkfall.engine.actions import Action
from linkfall.engine.beats import begin_turn, refresh_signature
from linkfall.engine.effects import apply_action
from linkfall.engine.events import EngineEvent, EventKind
from linkfall.engine.rng import next_float, seed_state
from linkfall.engine.rounding import round_half_up
from linkfall.engine.scenario import Scenario
from linkfall.engine.state import Outcome, State
from linkfall.engine.zone_effects import Zone, effect_multiplier, turn_strain


class EngineError(Exception):
    """The caller broke an engine contract. Never a game outcome."""


@dataclass(frozen=True, slots=True)
class Command:
    """One resolved turn choice. `manual` means the pilot picked it, not Lodestar."""

    action: Action
    zone: Zone
    manual: bool = False


def new_game(seed: int, scenario: Scenario) -> tuple[State, tuple[EngineEvent, ...]]:
    s = State(
        turn=1,
        hp=scenario.start.hp,
        heat=scenario.start.heat,
        power=scenario.start.power,
        ammo=scenario.start.ammo,
        strain=scenario.start.strain,
        shields=True,
        ashgrove=scenario.start.ashgrove,
        visitors=0,
        compromised=False,
        quarantined=False,
        truce=False,
        over=False,
        outcome=None,
        rng_state=seed_state(seed),
        sig_ok=0.97,
        sig_bad=0.71,
    )
    s = refresh_signature(s)
    return s, (EngineEvent(1, EventKind.SYSTEM, f"Run seed {seed}. {scenario.intro}"),)


def _clamp(value: int) -> int:
    return max(0, min(100, value))


def _finish(s: State, outcome: Outcome) -> tuple[State, EngineEvent]:
    return (
        replace(s, over=True, outcome=outcome),
        EngineEvent(s.turn, EventKind.OVER, f"Mission over: {outcome.value}."),
    )


def step(
    state: State, scenario: Scenario, command: Command
) -> tuple[State, tuple[EngineEvent, ...]]:
    if state.over:
        raise EngineError("the mission is over")
    if command.zone is Zone.MANUAL and not command.manual:
        raise EngineError("Lodestar is locked out in the MANUAL zone")

    events: list[EngineEvent] = []
    s = state
    multiplier = effect_multiplier(command.zone, manual=command.manual)

    reason = rules.check(s, command.action)
    if reason is not None:
        text = f"REJECTED {command.action}: {reason}. Turn lost."
        events.append(EngineEvent(s.turn, EventKind.REJECTED, text, command.action))
    else:
        s = apply_action(s, command.action, multiplier)
        suffix = f" (x{multiplier:g} {command.zone.lower()})" if multiplier > 1 else ""
        events.append(
            EngineEvent(s.turn, EventKind.VALID, f"VALID {command.action}{suffix}", command.action)
        )

    s = replace(s, strain=s.strain + turn_strain(command.zone, manual=command.manual))

    if s.ashgrove + s.visitors > 0:
        base = (s.ashgrove * 3 + s.visitors * 5) * (0.5 if s.shields else 1.0)
        value, rng_state = next_float(s.rng_state)
        damage = round_half_up(base * (0.9 + value * 0.2))
        s = replace(s, rng_state=rng_state, hp=s.hp - damage)
        tail = "." if s.shields else " (shields down)."
        events.append(
            EngineEvent(s.turn, EventKind.ENEMY_FIRE, f"Enemy fire: -{damage} integrity{tail}")
        )

    s = replace(s, heat=s.heat - 2, power=s.power + 3)
    s = replace(
        s,
        hp=_clamp(s.hp),
        heat=_clamp(s.heat),
        power=_clamp(s.power),
        ammo=_clamp(s.ammo),
        strain=_clamp(s.strain),
    )

    if s.hp <= 0:
        s, over = _finish(s, Outcome.DESTROYED)
        return s, (*events, over)
    if s.strain >= 100:
        s, over = _finish(s, Outcome.LINK_BLACKOUT)
        return s, (*events, over)
    if s.turn >= scenario.max_turns:
        cleared = s.visitors <= 0 and s.ashgrove <= 0
        s, over = _finish(s, Outcome.FIELD_CLEARED if cleared else Outcome.SURVIVED)
        return s, (*events, over)

    s = replace(s, turn=s.turn + 1)
    s, beat_events = begin_turn(s, scenario)
    return s, (*events, *beat_events)
