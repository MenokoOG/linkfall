import pytest

from linkfall.engine.actions import Action
from linkfall.engine.events import EngineEvent, EventKind
from linkfall.engine.step import Command
from linkfall.engine.zone_effects import Zone
from linkfall.eventlog.codec import (
    CodecError,
    command_row,
    engine_row,
    payload_to_command,
    payload_to_event,
)
from linkfall.eventlog.types import Payload


def test_command_round_trips() -> None:
    command = Command(Action.OVERCHARGE, Zone.DELEGATED, manual=False)
    assert payload_to_command(command_row(3, command).payload) == command


def test_event_round_trips_with_and_without_an_action() -> None:
    with_action = EngineEvent(2, EventKind.VALID, "VALID flank", Action.FLANK)
    without = EngineEvent(2, EventKind.SYSTEM, "hello")
    assert payload_to_event(engine_row(with_action).payload) == with_action
    assert payload_to_event(engine_row(without).payload) == without


@pytest.mark.parametrize(
    "payload",
    [
        {"zone": "ASSISTED", "manual": True},
        {"action": "nope", "zone": "ASSISTED", "manual": True},
        {"action": "flank", "zone": "ORBIT", "manual": True},
        {"action": "flank", "zone": "ASSISTED", "manual": "yes"},
        {"action": 7, "zone": "ASSISTED", "manual": True},
    ],
)
def test_bad_command_payloads_are_refused(payload: Payload) -> None:
    with pytest.raises(CodecError):
        payload_to_command(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "valid", "message": "m", "action": None},
        {"turn": True, "kind": "valid", "message": "m", "action": None},
        {"turn": 1, "kind": "bogus", "message": "m", "action": None},
        {"turn": 1, "kind": "valid", "message": 5, "action": None},
        {"turn": 1, "kind": "valid", "message": "m", "action": "nope"},
        {"turn": 1, "kind": "valid", "message": "m", "action": 3},
    ],
)
def test_bad_event_payloads_are_refused(payload: Payload) -> None:
    with pytest.raises(CodecError):
        payload_to_event(payload)
