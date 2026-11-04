import sqlite3
from pathlib import Path

import pytest

from linkfall.eventlog.schema import SCHEMA_VERSION
from linkfall.eventlog.store import EventLogError, EventStore, RunNotFoundError
from linkfall.eventlog.types import NewRow, RunHeader
from linkfall.runmode import RunMode


def header(run_id: str = "r1") -> RunHeader:
    return RunHeader(run_id, 4217, RunMode.STORY, "cinder-ward", SCHEMA_VERSION)


def row(turn: int = 1, kind: str = "engine", message: str = "hello") -> NewRow:
    return NewRow(turn, kind, {"message": message})


def test_run_header_round_trips() -> None:
    store = EventStore()
    store.create_run(header())
    assert store.get_run("r1") == header()


def test_unknown_run_raises() -> None:
    with pytest.raises(RunNotFoundError):
        EventStore().get_run("nope")


def test_rows_come_back_in_order_and_resume_after_an_id() -> None:
    store = EventStore()
    store.create_run(header(), [row(message="a")])
    ids = store.append_batch("r1", [row(message="b"), row(message="c")])
    assert ids == sorted(ids)
    rows = store.read_rows("r1")
    assert [r.payload["message"] for r in rows] == ["a", "b", "c"]
    resumed = store.read_rows("r1", after_id=rows[0].id)
    assert [r.payload["message"] for r in resumed] == ["b", "c"]


def test_runs_do_not_see_each_others_rows() -> None:
    store = EventStore()
    store.create_run(header("r1"), [row(message="one")])
    store.create_run(header("r2"), [row(message="two")])
    assert [r.payload["message"] for r in store.read_rows("r2")] == ["two"]


def test_update_and_delete_are_refused() -> None:
    store = EventStore()
    store.create_run(header(), [row()])
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store._conn.execute("UPDATE events SET kind = 'x'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store._conn.execute("DELETE FROM events")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store._conn.execute("UPDATE runs SET seed = 1")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store._conn.execute("DELETE FROM runs")


def test_batch_is_all_or_nothing_and_leaves_no_open_transaction() -> None:
    store = EventStore()
    store.create_run(header())
    with pytest.raises(OverflowError):
        store.append_batch("r1", [row(message="kept?"), row(turn=2**70)])
    assert store.read_rows("r1") == []
    store.append_batch("r1", [row(message="after")])
    assert len(store.read_rows("r1")) == 1


def test_append_to_a_missing_run_is_refused() -> None:
    store = EventStore()
    with pytest.raises(EventLogError):
        store.append_batch("ghost", [row()])


def test_duplicate_run_id_is_refused_and_writes_nothing() -> None:
    store = EventStore()
    store.create_run(header(), [row(message="first")])
    with pytest.raises(EventLogError):
        store.create_run(header(), [row(message="second")])
    assert len(store.read_rows("r1")) == 1


def test_hostile_text_is_stored_as_data() -> None:
    store = EventStore()
    nasty = "x'); DROP TABLE events; --"
    store.create_run(header(nasty), [row(message=nasty)])
    assert store.read_rows(nasty)[0].payload["message"] == nasty
    assert store.get_run(nasty).run_id == nasty


def test_file_store_persists_and_checks_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "log.sqlite"
    first = EventStore(path)
    first.create_run(header(), [row()])
    first.close()
    again = EventStore(path)
    assert len(again.read_rows("r1")) == 1
    again.close()
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA user_version = 99")
    raw.commit()
    raw.close()
    with pytest.raises(EventLogError, match="schema version 99"):
        EventStore(path)


def test_damaged_payload_is_reported_not_skipped() -> None:
    store = EventStore()
    store.create_run(header())
    store._conn.execute(
        "INSERT INTO events (run_id, turn, kind, payload) VALUES ('r1', 1, 'engine', 'not json')"
    )
    with pytest.raises(EventLogError, match="invalid JSON"):
        store.read_rows("r1")
    store._conn.execute(
        "INSERT INTO events (run_id, turn, kind, payload) VALUES ('r1', 1, 'engine', '[1]')"
    )
    with pytest.raises(EventLogError):
        store.read_rows("r1")


def test_unknown_mode_in_a_header_is_reported() -> None:
    store = EventStore()
    store._conn.execute(
        "INSERT INTO runs (run_id, seed, mode, scenario, schema_version)"
        " VALUES ('bad', 1, 'chaos', 'cinder-ward', 1)"
    )
    with pytest.raises(EventLogError, match="unknown mode"):
        store.get_run("bad")
