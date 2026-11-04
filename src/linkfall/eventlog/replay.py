"""Replay a logged run with no model. Reports the first difference, never repairs (ADR 0007)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from linkfall.engine.events import EngineEvent
from linkfall.engine.fingerprint import fingerprint
from linkfall.engine.scenario import SCENARIOS, Scenario
from linkfall.engine.state import State
from linkfall.engine.step import EngineError, new_game, step
from linkfall.eventlog.codec import CodecError, payload_to_command, payload_to_event
from linkfall.eventlog.store import EventStore
from linkfall.eventlog.types import LogRow, RowKind


@dataclass(frozen=True, slots=True)
class ReplayFailure:
    row_id: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class ReplayResult:
    failure: ReplayFailure | None
    state: State | None
    fingerprint: str | None
    turns: int

    @property
    def ok(self) -> bool:
        return self.failure is None


def _failed(row_id: int | None, reason: str, turns: int) -> ReplayResult:
    return ReplayResult(ReplayFailure(row_id, reason), None, None, turns)


def _compare(
    expected: Sequence[EngineEvent], logged: Sequence[LogRow], anchor: int | None
) -> ReplayFailure | None:
    """Compare regenerated events with logged rows. `anchor` is blamed if rows are missing."""
    for index in range(max(len(expected), len(logged))):
        if index >= len(logged):
            return ReplayFailure(
                anchor, f"log is missing event {index + 1}: {expected[index].message!r}"
            )
        row = logged[index]
        if index >= len(expected):
            return ReplayFailure(row.id, f"log has an extra event: {row.payload.get('message')!r}")
        try:
            event = payload_to_event(row.payload)
        except CodecError as exc:
            return ReplayFailure(row.id, f"unreadable event: {exc}")
        if event != expected[index]:
            return ReplayFailure(
                row.id,
                f"event differs: logged {event.message!r}, replay {expected[index].message!r}",
            )
    return None


def _engine_rows_after(rows: Sequence[LogRow], start: int) -> list[LogRow]:
    group: list[LogRow] = []
    for row in rows[start:]:
        if row.kind != RowKind.ENGINE.value:
            break
        group.append(row)
    return group


def replay(
    store: EventStore, run_id: str, scenarios: Mapping[str, Scenario] = SCENARIOS
) -> ReplayResult:
    header = store.get_run(run_id)
    scenario = scenarios.get(header.scenario)
    if scenario is None:
        return _failed(None, f"unknown scenario {header.scenario!r}", 0)
    rows = store.read_rows(run_id)

    state, first_events = new_game(header.seed, scenario)
    all_events: list[EngineEvent] = list(first_events)
    group = _engine_rows_after(rows, 0)
    if (failure := _compare(first_events, group, None)) is not None:
        return ReplayResult(failure, None, None, 0)

    index = len(group)
    turns = 0
    while index < len(rows):
        row = rows[index]
        if row.kind != RowKind.COMMAND.value:
            return _failed(row.id, f"unexpected row kind {row.kind!r}", turns)
        try:
            command = payload_to_command(row.payload)
            state, events = step(state, scenario, command)
        except (CodecError, EngineError) as exc:
            return _failed(row.id, str(exc), turns)
        group = _engine_rows_after(rows, index + 1)
        if (failure := _compare(events, group, row.id)) is not None:
            return ReplayResult(failure, None, None, turns)
        all_events.extend(events)
        turns += 1
        index += 1 + len(group)

    return ReplayResult(None, state, fingerprint(state, all_events), turns)
