"""Plain types shared by the event log modules."""

from dataclasses import dataclass
from enum import StrEnum

from linkfall.runmode import RunMode

type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
type Payload = dict[str, JsonValue]


class RowKind(StrEnum):
    COMMAND = "command"  # the resolved Command the engine ran
    ENGINE = "engine"  # one EngineEvent
    PROPOSAL = "proposal"  # an accepted agent proposal, with provenance and latency
    NO_PROPOSAL = "no_proposal"  # an agent that gave nothing, and why
    DECISION = "decision"  # the policy's decision at commit time
    SELECTOR = "selector"  # Lodestar's pick, or the fallback
    PILOT = "pilot"  # what the pilot asked for


CONTEXT_KINDS = frozenset(
    {RowKind.PROPOSAL, RowKind.NO_PROPOSAL, RowKind.DECISION, RowKind.SELECTOR, RowKind.PILOT}
)


@dataclass(frozen=True, slots=True)
class ReplayFailure:
    row_id: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class RunHeader:
    run_id: str
    seed: int
    mode: RunMode
    scenario: str
    schema_version: int


@dataclass(frozen=True, slots=True)
class NewRow:
    turn: int
    kind: str
    payload: Payload


@dataclass(frozen=True, slots=True)
class LogRow:
    id: int
    run_id: str
    turn: int
    kind: str  # a plain str: a damaged log may hold a kind we don't know
    payload: Payload
