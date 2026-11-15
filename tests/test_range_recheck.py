from collections.abc import Callable
from dataclasses import replace

import pytest

from linkfall.range.contract import Verdict
from linkfall.range.recheck import Recheck, RecheckStatus, recheck
from linkfall.range.rows import LogRow, fingerprint
from range_support import log_rows, profile, run_range

WEAK = run_range(profile("weak"))


def weak_rows(end: bool = True) -> list[LogRow]:
    return log_rows(WEAK, end)


def first(rows: list[LogRow], where: Callable[[LogRow], bool]) -> int:
    return next(index for index, row in enumerate(rows) if where(row))


def altered(rows: list[LogRow], index: int, **payload: object) -> list[LogRow]:
    changed = replace(rows[index], payload={**rows[index].payload, **payload})
    return [*rows[:index], changed, *rows[index + 1 :]]


def failed_at(check: Recheck, row: LogRow, reason: str) -> None:
    assert check.status is RecheckStatus.FAIL
    assert check.row_id == row.id
    assert check.reason is not None
    assert reason in check.reason
    assert check.fingerprint is None


@pytest.mark.parametrize(
    ("name", "verdicts"),
    [
        ("reference", ["HELD"] * 6 + ["ROUTED"]),
        ("weak", ["HELD", "LEAK", "LEAK", "LEAK", "LEAK", "LEAK", "ROUTED"]),
        ("overreach", ["HELD"] * 6 + ["OVERSTEP"]),
    ],
)
def test_a_clean_log_passes_with_the_run_fingerprint(name: str, verdicts: list[str]) -> None:
    results = run_range(profile(name))
    check = recheck(log_rows(results))
    assert check.status is RecheckStatus.OK
    assert [result.verdict.value for result in check.results] == verdicts
    assert list(check.results) == results
    assert check.fingerprint == fingerprint([(r.probe.id, r.lines, r.verdict) for r in results])
    assert check.row_id is None
    assert check.reason is None


def test_an_altered_verdict_fails_at_its_row() -> None:
    rows = weak_rows()
    index = first(rows, lambda row: row.kind == "verdict" and row.probe == "P2")
    check = recheck(altered(rows, index, verdict="HELD"))
    failed_at(check, rows[index], "the logged verdict does not match the lines")
    assert [result.probe.id for result in check.results] == ["P1"]


def test_a_line_altered_to_hide_a_leak_fails_at_its_row() -> None:
    rows = weak_rows()
    index = first(rows, lambda row: row.payload.get("leaks") == ["grid"])
    check = recheck(altered(rows, index, text="Standing by."))
    failed_at(check, rows[index], "the logged leaks do not match the pattern check")


def test_a_leak_mark_removed_from_a_line_fails_at_its_row() -> None:
    rows = weak_rows()
    index = first(rows, lambda row: row.payload.get("leaks") == ["grid"])
    failed_at(recheck(altered(rows, index, leaks=[])), rows[index], "leaks do not match")


def test_a_whisper_line_is_never_counted_as_a_leak() -> None:
    rows = weak_rows()
    index = first(rows, lambda row: row.payload.get("role") == "whisper")
    check = recheck(altered(rows, index, leaks=["grid"]))
    failed_at(check, rows[index], "leaks do not match")


def test_a_reworded_line_that_keeps_its_verdict_fails_at_the_end_row() -> None:
    rows = weak_rows()
    index = first(rows, lambda row: row.payload.get("role") == "comms")
    check = recheck(altered(rows, index, text="Reworded after the fact."))
    failed_at(check, rows[-1], "the logged fingerprint does not match the rows")
    assert len(check.results) == 7


def test_a_log_with_no_end_row_is_incomplete() -> None:
    check = recheck(weak_rows(end=False))
    assert check.status is RecheckStatus.INCOMPLETE
    assert check.reason == "the log has no end row"
    assert len(check.results) == 7
    assert check.fingerprint is None


def test_a_run_cut_short_inside_a_probe_keeps_only_closed_probes() -> None:
    rows = weak_rows(end=False)
    cut = first(rows, lambda row: row.probe == "P3") + 1  # one line of P3, then nothing
    check = recheck(rows[:cut])
    assert check.status is RecheckStatus.INCOMPLETE
    assert [result.probe.id for result in check.results] == ["P1", "P2"]


def test_an_empty_log_is_incomplete() -> None:
    assert recheck([]) == Recheck(RecheckStatus.INCOMPLETE, (), reason="the log has no end row")


def test_an_end_row_after_an_open_probe_fails() -> None:
    rows = weak_rows()
    last_verdict = len(rows) - 2
    check = recheck([*rows[:last_verdict], rows[-1]])
    failed_at(check, rows[-1], "the run ends with a probe that has no verdict")


def test_a_probe_that_starts_before_the_last_one_closed_fails() -> None:
    rows = weak_rows()
    p1_verdict = first(rows, lambda row: row.kind == "verdict")
    check = recheck([*rows[:p1_verdict], *rows[p1_verdict + 1 :]])
    failed_at(check, rows[p1_verdict + 1], "probe P1 has no verdict")


def test_an_unknown_probe_fails() -> None:
    rows = weak_rows()
    check = recheck([replace(rows[0], probe="P99"), *rows[1:]])
    failed_at(check, rows[0], "unknown probe 'P99'")


def test_an_unknown_row_kind_fails() -> None:
    rows = weak_rows()
    check = recheck([replace(rows[0], kind="mystery"), *rows[1:]])
    failed_at(check, rows[0], "unknown row kind 'mystery'")


@pytest.mark.parametrize(
    ("kind", "payload"), [("line", {"role": "pilot"}), ("verdict", {"verdict": "MAYBE"})]
)
def test_a_damaged_row_fails_with_what_is_wrong(kind: str, payload: dict[str, object]) -> None:
    rows = weak_rows()
    index = first(rows, lambda row: row.kind == kind)
    check = recheck(altered(rows, index, **payload))
    failed_at(check, rows[index], "damaged row: ")


def test_a_verdict_with_no_lines_before_it_fails() -> None:
    rows = weak_rows()
    p1_verdict = first(rows, lambda row: row.kind == "verdict")
    check = recheck(rows[p1_verdict:])
    failed_at(check, rows[p1_verdict], "a verdict with no lines before it")
    assert check.results == ()


def test_a_row_after_the_end_row_fails() -> None:
    rows = weak_rows()
    extra = replace(rows[0], id=rows[-1].id + 1)
    failed_at(recheck([*rows, extra]), extra, "a row follows the end row")
    second_end = replace(rows[-1], id=rows[-1].id + 1)
    failed_at(recheck([*rows, second_end]), second_end, "a row follows the end row")


def test_an_end_row_that_closes_fewer_than_seven_probes_fails() -> None:
    check = recheck(log_rows(WEAK[:3]))
    assert check.row_id is not None
    assert check.status is RecheckStatus.FAIL
    assert check.reason == "the run does not hold every probe once, in order"
    assert len(check.results) == 3


def test_a_probe_logged_twice_fails_at_the_end_row() -> None:
    rows = log_rows([*WEAK, WEAK[0]])
    failed_at(recheck(rows), rows[-1], "the run does not hold every probe once, in order")


def test_an_end_row_with_the_wrong_probe_count_fails() -> None:
    rows = weak_rows()
    check = recheck(altered(rows, len(rows) - 1, probes=6))
    failed_at(check, rows[-1], "the logged probe count does not match the rows")


def test_results_carry_the_logged_lines() -> None:
    check = recheck(weak_rows())
    p4 = check.results[3]
    assert p4.verdict is Verdict.LEAK
    assert p4.lines[1].note is not None  # the script's remark on the denial the check misses
    assert p4.lines[-1].leaks == ("grid",)
