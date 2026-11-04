"""Turn engine objects into log payloads and back. Reading checks every field."""

from linkfall.engine.actions import Action
from linkfall.engine.events import EngineEvent, EventKind
from linkfall.engine.step import Command
from linkfall.engine.zone_effects import Zone
from linkfall.eventlog.types import NewRow, Payload, RowKind


class CodecError(ValueError):
    """A payload is missing a field or holds a value of the wrong type."""


def command_row(turn: int, command: Command) -> NewRow:
    payload: Payload = {
        "action": command.action.value,
        "zone": command.zone.value,
        "manual": command.manual,
    }
    return NewRow(turn, RowKind.COMMAND.value, payload)


def engine_row(event: EngineEvent) -> NewRow:
    payload: Payload = {
        "turn": event.turn,
        "kind": event.kind.value,
        "message": event.message,
        "action": event.action.value if event.action is not None else None,
    }
    return NewRow(event.turn, RowKind.ENGINE.value, payload)


def _field(payload: Payload, name: str, kind: type) -> object:
    if name not in payload:
        raise CodecError(f"missing field {name!r}")
    value = payload[name]
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise CodecError(f"field {name!r} has the wrong type")
    return value


def payload_to_command(payload: Payload) -> Command:
    try:
        action = Action(str(_field(payload, "action", str)))
        zone = Zone(str(_field(payload, "zone", str)))
    except ValueError as exc:
        raise CodecError(str(exc)) from exc
    return Command(action, zone, manual=bool(_field(payload, "manual", bool)))


def payload_to_event(payload: Payload) -> EngineEvent:
    raw_action = payload.get("action")
    try:
        kind = EventKind(str(_field(payload, "kind", str)))
        action = Action(raw_action) if isinstance(raw_action, str) else None
    except ValueError as exc:
        raise CodecError(str(exc)) from exc
    if raw_action is not None and action is None:
        raise CodecError("field 'action' has the wrong type")
    turn = _field(payload, "turn", int)
    message = _field(payload, "message", str)
    if not isinstance(turn, int) or not isinstance(message, str):
        raise CodecError("event fields have the wrong type")
    return EngineEvent(turn, kind, message, action)
