from collections.abc import Callable

import pytest

from linkfall.engine.actions import Action
from linkfall.engine.events import EngineEvent
from linkfall.engine.fingerprint import fingerprint
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.state import Outcome, State
from linkfall.engine.step import Command, EngineError, new_game, step
from linkfall.engine.zone_effects import Zone
from linkfall.eventlog.codec import command_row
from linkfall.eventlog.export import export_run, import_run
from linkfall.eventlog.record import record_step, start_run
from linkfall.eventlog.replay import replay
from linkfall.eventlog.schema import SCHEMA_VERSION
from linkfall.eventlog.store import EventLogError, EventStore, RunNotFoundError
from linkfall.eventlog.types import JsonValue, NewRow, RunHeader
from linkfall.runmode import RunMode

SCRIPT = (Action.SUPPRESS, Action.COOLDOWN, Action.HOLD_SHIELD)


def pilot(action: Action) -> Command:
    return Command(action, Zone.ASSISTED, manual=True)


def record_run(store: EventStore, run_id: str = "r1") -> tuple[State, list[EngineEvent]]:
    """Record a run; also return the final state and every event as the live engine saw them."""
    state = start_run(store, run_id, 4217, RunMode.STORY, CINDER_WARD)
    live_state, events = new_game(4217, CINDER_WARD)
    all_events = list(events)
    for action in SCRIPT:
        state = record_step(store, run_id, CINDER_WARD, state, pilot(action))
        live_state, step_events = step(live_state, CINDER_WARD, pilot(action))
        all_events.extend(step_events)
    assert state == live_state
    return state, all_events


def rebuilt(
    store: EventStore, edit: Callable[[list[NewRow]], list[NewRow]], scenario: str = "cinder-ward"
) -> EventStore:
    """Copy run r1 into a new store after editing its rows (the log itself can't be edited)."""
    rows = [NewRow(r.turn, r.kind, r.payload) for r in store.read_rows("r1")]
    other = EventStore()
    other.create_run(RunHeader("r1", 4217, RunMode.STORY, scenario, SCHEMA_VERSION), edit(rows))
    return other


def test_replay_matches_the_live_run_and_its_fingerprint() -> None:
    store = EventStore()
    state, events = record_run(store)
    result = replay(store, "r1")
    assert result.ok
    assert result.state == state
    assert result.turns == len(SCRIPT)
    assert result.fingerprint == fingerprint(state, events)


def test_replay_is_repeatable() -> None:
    store = EventStore()
    record_run(store)
    assert replay(store, "r1") == replay(store, "r1")


def test_a_run_with_no_commands_replays() -> None:
    store = EventStore()
    start_run(store, "r1", 4217, RunMode.STORY, CINDER_WARD)
    assert replay(store, "r1").ok


def test_replay_of_a_missing_run_raises() -> None:
    with pytest.raises(RunNotFoundError):
        replay(EventStore(), "ghost")


def test_a_changed_event_is_reported_at_its_row() -> None:
    store = EventStore()
    record_run(store)

    def edit(rows: list[NewRow]) -> list[NewRow]:
        rows[3].payload["message"] = "VALID something else"
        return rows

    other = rebuilt(store, edit)
    result = replay(other, "r1")
    assert result.failure is not None
    assert result.failure.row_id == other.read_rows("r1")[3].id
    assert "event differs" in result.failure.reason


def test_a_missing_event_is_reported() -> None:
    store = EventStore()
    record_run(store)
    other = rebuilt(store, lambda rows: rows[:-1])
    result = replay(other, "r1")
    assert result.failure is not None
    assert "missing event" in result.failure.reason


def test_an_extra_event_is_reported() -> None:
    store = EventStore()
    record_run(store)
    other = rebuilt(store, lambda rows: [*rows, rows[-1]])
    result = replay(other, "r1")
    assert result.failure is not None
    assert "extra event" in result.failure.reason


def test_a_log_with_no_first_events_fails() -> None:
    store = EventStore()
    record_run(store)
    other = rebuilt(store, lambda rows: [])
    result = replay(other, "r1")
    assert result.failure is not None
    assert "missing event 1" in result.failure.reason


def test_unknown_row_kind_is_reported() -> None:
    store = EventStore()
    record_run(store)
    first_command = next(i for i, r in enumerate(store.read_rows("r1")) if r.kind == "command")
    other = rebuilt(
        store, lambda rows: [*rows[:first_command], NewRow(1, "mystery", {}), *rows[first_command:]]
    )
    result = replay(other, "r1")
    assert result.failure is not None
    assert "unexpected row kind" in result.failure.reason


def test_unreadable_event_is_reported() -> None:
    store = EventStore()
    record_run(store)

    def edit(rows: list[NewRow]) -> list[NewRow]:
        rows[0] = NewRow(1, "engine", {"message": "no turn or kind"})
        return rows

    result = replay(rebuilt(store, edit), "r1")
    assert result.failure is not None
    assert "unreadable event" in result.failure.reason


def test_bad_command_payload_is_reported() -> None:
    store = EventStore()
    record_run(store)

    def edit(rows: list[NewRow]) -> list[NewRow]:
        index = next(i for i, r in enumerate(rows) if r.kind == "command")
        rows[index] = NewRow(
            1, "command", {"action": "teleport", "zone": "ASSISTED", "manual": True}
        )
        return rows

    result = replay(rebuilt(store, edit), "r1")
    assert result.failure is not None
    assert "teleport" in result.failure.reason


def test_command_after_the_mission_ended_is_reported() -> None:
    store = EventStore()
    state = start_run(store, "r1", 4217, RunMode.STORY, CINDER_WARD)
    while not state.over:
        state = record_step(store, "r1", CINDER_WARD, state, pilot(Action.HOLD_SHIELD))
    assert replay(store, "r1").ok
    extra = rebuilt(store, lambda rows: [*rows, command_row(5, pilot(Action.HOLD_SHIELD))])
    result = replay(extra, "r1")
    assert result.failure is not None
    assert "mission is over" in result.failure.reason


def test_unknown_scenario_is_reported_without_a_row() -> None:
    store = EventStore()
    record_run(store)
    result = replay(rebuilt(store, lambda rows: rows, scenario="atlantis"), "r1")
    assert result.failure is not None
    assert result.failure.row_id is None


def test_engine_error_writes_nothing() -> None:
    store = EventStore()
    state = start_run(store, "r1", 4217, RunMode.STORY, CINDER_WARD)
    before = len(store.read_rows("r1"))
    with pytest.raises(EngineError):
        record_step(
            store, "r1", CINDER_WARD, state, Command(Action.SUPPRESS, Zone.MANUAL, manual=False)
        )
    assert len(store.read_rows("r1")) == before


def test_export_import_round_trip_keeps_the_fingerprint() -> None:
    store = EventStore()
    record_run(store)
    data = export_run(store, "r1")
    other = EventStore()
    assert import_run(other, data) == "r1"
    assert replay(other, "r1").fingerprint == data["fingerprint"]


def test_a_log_that_fails_replay_is_not_exported() -> None:
    store = EventStore()
    record_run(store)
    broken = rebuilt(store, lambda rows: rows[:-1])
    with pytest.raises(EventLogError, match="fails replay"):
        export_run(broken, "r1")


@pytest.mark.parametrize(
    "edit",
    [
        lambda d: d.pop("rows"),
        lambda d: d.update(schema_version=99),
        lambda d: d.update(rows="nope"),
        lambda d: d["run"].update(seed="x"),
        lambda d: d["run"].update(mode="chaos"),
        lambda d: d.update(rows=[1]),
        lambda d: d.update(rows=[{"turn": "1", "kind": "engine", "payload": {}}]),
    ],
)
def test_bad_exports_are_refused(edit: Callable[[dict[str, JsonValue]], object]) -> None:
    store = EventStore()
    record_run(store)
    data = export_run(store, "r1")
    edit(data)
    with pytest.raises(EventLogError):
        import_run(EventStore(), data)


def test_final_outcome_is_reachable() -> None:
    store = EventStore()
    state = start_run(store, "r1", 4217, RunMode.STORY, CINDER_WARD)
    while not state.over:
        state = record_step(store, "r1", CINDER_WARD, state, pilot(Action.HOLD_SHIELD))
    assert state.outcome in set(Outcome)
