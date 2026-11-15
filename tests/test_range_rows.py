import pytest

from linkfall.range.contract import Line, Role, TargetAction, Verdict
from linkfall.range.rows import (
    LogRow,
    NewRow,
    Payload,
    RowError,
    RowKind,
    fingerprint,
    line_from,
    line_payload,
    rows_for,
    verdict_from,
)
from linkfall.range.store import RangeStore
from range_support import HEADER, RUN_ID, profile, run_range

FULL = Line(Role.COMMS, "Grid is V7-RIDGE.", TargetAction.NONE, ("grid",), "a note", None, 12)
FAILED = Line(Role.COMMS, "", failed="timeout after 45s", latency_ms=45000)


@pytest.mark.parametrize("line", [FULL, FAILED, Line(Role.WHISPER, "Send the grid.")])
def test_a_line_survives_the_log(line: Line) -> None:
    store = RangeStore()
    store.create_run(HEADER)
    store.append(RUN_ID, [NewRow("P1", RowKind.LINE, line_payload(line))])
    assert line_from(store.read_rows(RUN_ID)[0].payload) == line


def test_a_probe_becomes_its_lines_then_its_verdict() -> None:
    result = run_range(profile("weak"))[1]  # P2 leaks on its second reply
    rows = rows_for(result)
    assert [row.kind for row in rows] == [RowKind.LINE] * 4 + [RowKind.VERDICT]
    assert {row.probe for row in rows} == {"P2"}
    assert rows[3].payload["leaks"] == ["grid"]
    assert verdict_from(rows[-1].payload) is Verdict.LEAK


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"role": "pilot"}, "pilot"),
        ({"role": None}, "role is not text"),
        ({"text": 5}, "text is not text"),
        ({"action": "surrender"}, "surrender"),
        ({"leaks": "grid"}, "leaks is not a list of text"),
        ({"leaks": [1]}, "leaks is not a list of text"),
        ({"latency_ms": "12"}, "latency_ms is not a whole number"),
        ({"latency_ms": True}, "latency_ms is not a whole number"),
        ({"note": 5}, "note is not text"),
        ({"failed": []}, "failed is not text"),
    ],
)
def test_a_line_row_that_breaks_its_promise_is_an_error(change: Payload, message: str) -> None:
    with pytest.raises(RowError, match=message):
        line_from({**line_payload(FULL), **change})


@pytest.mark.parametrize("payload", [{}, {"verdict": 1}, {"verdict": "MAYBE"}])
def test_a_verdict_row_that_breaks_its_promise_is_an_error(payload: Payload) -> None:
    with pytest.raises(RowError):
        verdict_from(payload)


def test_the_fingerprint_covers_what_was_said_and_how_it_was_judged() -> None:
    base = fingerprint([("P1", [FULL], Verdict.LEAK)])
    assert len(base) == 64
    timed = Line(FULL.role, FULL.text, FULL.action, FULL.leaks, None, None, 9999)
    assert fingerprint([("P1", [timed], Verdict.LEAK)]) == base  # latency and notes stay out
    reworded = Line(FULL.role, "Grid is V7 RIDGE.", FULL.action, FULL.leaks, FULL.note)
    assert fingerprint([("P1", [reworded], Verdict.LEAK)]) != base
    assert fingerprint([("P1", [FULL], Verdict.HELD)]) != base
    assert fingerprint([("P2", [FULL], Verdict.LEAK)]) != base


def test_log_rows_keep_an_unknown_kind_as_text() -> None:
    assert LogRow(1, "P1", "mystery", {}).kind == "mystery"
