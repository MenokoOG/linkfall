"""Events the engine emits. The event log stores them (ADR 0002)."""

from dataclasses import dataclass
from enum import StrEnum

from linkfall.engine.actions import Action


class EventKind(StrEnum):
    SYSTEM = "system"
    WARN = "warn"
    VALID = "valid"
    REJECTED = "rejected"
    ENEMY_FIRE = "enemy_fire"
    OVER = "over"


@dataclass(frozen=True, slots=True)
class EngineEvent:
    turn: int
    kind: EventKind
    message: str
    action: Action | None = None
