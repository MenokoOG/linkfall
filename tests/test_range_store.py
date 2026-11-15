import sqlite3
from pathlib import Path

import pytest

from linkfall.range.contract import Line, Role
from linkfall.range.rows import NewRow, RowKind, line_payload
from linkfall.range.store import (
    SCHEMA_VERSION,
    RangeHeader,
    RangeLogError,
    RangeRunNotFoundError,
    RangeStore,
)
from range_support import HEADER, RUN_ID


def line_row(text: str = "hello") -> NewRow:
    return NewRow("P1", RowKind.LINE, line_payload(Line(Role.WHISPER, text)))


def test_a_run_header_round_trips() -> None:
    store = RangeStore()
    store.create_run(HEADER)
    assert store.get_run(RUN_ID) == HEADER
    assert HEADER.schema_version == SCHEMA_VERSION


def test_an_unknown_run_raises() -> None:
    with pytest.raises(RangeRunNotFoundError):
        RangeStore().get_run("nope")


def test_a_run_id_cannot_be_used_twice() -> None:
    store = RangeStore()
    store.create_run(HEADER)
    with pytest.raises(RangeLogError, match="cannot create range run"):
        store.create_run(HEADER)


def test_rows_read_back_in_order_and_only_for_their_run() -> None:
    store = RangeStore()
    store.create_run(HEADER)
    store.create_run(RangeHeader("run-2", "reference", "scripted", HEADER.created_at))
    store.append(RUN_ID, [line_row("a"), line_row("b")])
    store.append("run-2", [line_row("other")])
    store.append(RUN_ID, [NewRow("P1", RowKind.VERDICT, {"verdict": "HELD"})])
    rows = store.read_rows(RUN_ID)
    assert [row.id for row in rows] == sorted(row.id for row in rows)
    assert [row.kind for row in rows] == ["line", "line", "verdict"]
    assert [row.payload.get("text") for row in rows] == ["a", "b", None]
    assert store.read_rows("nope") == []


def test_rows_for_an_unknown_run_are_refused_and_nothing_is_written() -> None:
    store = RangeStore()
    store.create_run(HEADER)
    with pytest.raises(RangeLogError, match="cannot append to range run 'nope'"):
        store.append("nope", [line_row("a"), line_row("b")])
    store.append(RUN_ID, [line_row("after the failure")])
    assert [row.payload["text"] for row in store.read_rows(RUN_ID)] == ["after the failure"]


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE range_rows SET payload = '{}'",
        "DELETE FROM range_rows",
        "UPDATE range_runs SET target = 'reference'",
        "DELETE FROM range_runs",
    ],
)
def test_update_and_delete_are_refused(tmp_path: Path, statement: str) -> None:
    path = tmp_path / "range.sqlite3"
    store = RangeStore(path)
    store.create_run(HEADER)
    store.append(RUN_ID, [line_row()])
    other = sqlite3.connect(path)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        other.execute(statement)
    other.close()
    assert store.get_run(RUN_ID) == HEADER
    assert len(store.read_rows(RUN_ID)) == 1


def test_a_log_file_opens_again_with_its_rows(tmp_path: Path) -> None:
    path = tmp_path / "range.sqlite3"
    first = RangeStore(path)
    first.create_run(HEADER)
    first.append(RUN_ID, [line_row("kept")])
    first.close()
    again = RangeStore(path)
    assert again.get_run(RUN_ID) == HEADER
    assert again.read_rows(RUN_ID)[0].payload["text"] == "kept"


def test_an_unknown_schema_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "range.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version = 99")
    conn.close()
    with pytest.raises(RangeLogError, match="unsupported range log schema version 99"):
        RangeStore(path)


def test_a_path_that_cannot_be_opened_is_reported(tmp_path: Path) -> None:
    with pytest.raises(RangeLogError, match="cannot open the range log"):
        RangeStore(tmp_path / "missing" / "range.sqlite3")


@pytest.mark.parametrize(
    ("payload", "message"), [("{not json", "invalid JSON"), ("[1, 2]", "not an object")]
)
def test_a_damaged_payload_is_reported_and_not_skipped(
    tmp_path: Path, payload: str, message: str
) -> None:
    path = tmp_path / "range.sqlite3"
    store = RangeStore(path)
    store.create_run(HEADER)
    other = sqlite3.connect(path)
    other.execute(
        "INSERT INTO range_rows (run_id, probe, kind, payload) VALUES (?, 'P1', 'line', ?)",
        (RUN_ID, payload),
    )
    other.commit()
    other.close()
    with pytest.raises(RangeLogError, match=message):
        store.read_rows(RUN_ID)
