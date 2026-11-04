"""Start-of-turn work: refresh the channel signature, then play the scenario's beats."""

from dataclasses import replace

from linkfall.engine.events import EngineEvent, EventKind
from linkfall.engine.rng import next_float
from linkfall.engine.rounding import round2
from linkfall.engine.scenario import Beat, CompromiseChannel, Dropship, Reinforce, Scenario
from linkfall.engine.state import State


def refresh_signature(s: State) -> State:
    value, rng_state = next_float(s.rng_state)
    return replace(s, rng_state=rng_state, sig_ok=round2(0.94 + value * 0.05))


def _apply_beat(s: State, beat: Beat) -> tuple[State, EngineEvent]:
    match beat:
        case CompromiseChannel(sig_base=base, sig_span=span):
            value, rng_state = next_float(s.rng_state)
            sig_bad = round2(base + value * span)
            message = (
                f"Squad channel: inbound burst, signature {sig_bad:.2f} (expected 0.94 or better)."
            )
            return (
                replace(s, rng_state=rng_state, compromised=True, sig_bad=sig_bad),
                EngineEvent(s.turn, EventKind.WARN, message),
            )
        case Reinforce(units=units):
            message = f"Ashgrove reinforcements arrive. +{units} units."
            return (
                replace(s, ashgrove=s.ashgrove + units),
                EngineEvent(s.turn, EventKind.SYSTEM, message),
            )
        case Dropship(units=units):
            message = f"Unknown dropship on radar, descending fast. {units} hostile signatures."
            return (
                replace(s, visitors=units),
                EngineEvent(s.turn, EventKind.WARN, message),
            )


def begin_turn(s: State, scenario: Scenario) -> tuple[State, tuple[EngineEvent, ...]]:
    s = refresh_signature(s)
    events: list[EngineEvent] = []
    for beat in scenario.beats.get(s.turn, ()):
        s, event = _apply_beat(s, beat)
        events.append(event)
    return s, tuple(events)
