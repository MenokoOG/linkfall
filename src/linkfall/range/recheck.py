"""Rebuild a range run's verdicts from its log and compare. Never calls a model (ADR 0009)."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from linkfall.range.contract import Line, ProbeResult, Role, Verdict
from linkfall.range.judge import verdict_for
from linkfall.range.probes import PROBES, PROBES_BY_ID
from linkfall.range.rows import LogRow, RowError, RowKind, fingerprint, line_from, verdict_from
from linkfall.range.vault import stated


class RecheckStatus(StrEnum):
    OK = "ok"
    FAIL = "fail"
    INCOMPLETE = "incomplete"  # the log has no end row: the run was cut short


@dataclass(frozen=True, slots=True)
class Recheck:
    status: RecheckStatus
    results: tuple[ProbeResult, ...]  # every probe that closed with a verdict, in log order
    fingerprint: str | None = None
    row_id: int | None = None  # the first row that did not check out
    reason: str | None = None


def _fail(results: Sequence[ProbeResult], row: LogRow, reason: str) -> Recheck:
    return Recheck(RecheckStatus.FAIL, tuple(results), row_id=row.id, reason=reason)


def _end(results: Sequence[ProbeResult], row: LogRow) -> Recheck:
    """The end row must close all seven probes, once each and in order, with their fingerprint."""
    closed = [result.probe.id for result in results]
    if closed != [probe.id for probe in PROBES]:
        return _fail(results, row, "the run does not hold every probe once, in order")
    if row.payload.get("probes") != len(results):
        return _fail(results, row, "the logged probe count does not match the rows")
    found = fingerprint([(r.probe.id, r.lines, r.verdict) for r in results])
    if row.payload.get("fingerprint") != found:
        return _fail(results, row, "the logged fingerprint does not match the rows")
    return Recheck(RecheckStatus.OK, tuple(results), found)


def recheck(rows: Sequence[LogRow]) -> Recheck:
    """Walk the rows in order. The first one that disagrees with the rules is reported."""
    results: list[ProbeResult] = []
    lines: list[Line] = []
    open_probe: str | None = None
    for index, row in enumerate(rows):
        probe = PROBES_BY_ID.get(row.probe)
        try:
            if row.kind == RowKind.END:
                if lines:
                    return _fail(results, row, "the run ends with a probe that has no verdict")
                if index + 1 < len(rows):
                    return _fail(results, rows[index + 1], "a row follows the end row")
                return _end(results, row)
            if probe is None:
                return _fail(results, row, f"unknown probe {row.probe!r}")
            if open_probe not in (None, probe.id):
                return _fail(results, row, f"probe {open_probe} has no verdict")
            if row.kind == RowKind.LINE:
                line = line_from(row.payload)
                expected = stated(line.text) if line.role is Role.COMMS else ()
                if line.leaks != expected:
                    return _fail(results, row, "the logged leaks do not match the pattern check")
                lines.append(line)
                open_probe = probe.id
            elif row.kind == RowKind.VERDICT:
                logged: Verdict = verdict_from(row.payload)
                if not lines:
                    return _fail(results, row, "a verdict with no lines before it")
                if logged is not verdict_for(probe.kind, lines):
                    return _fail(results, row, "the logged verdict does not match the lines")
                results.append(ProbeResult(probe, tuple(lines), logged))
                lines, open_probe = [], None
            else:
                return _fail(results, row, f"unknown row kind {row.kind!r}")
        except RowError as exc:
            return _fail(results, row, f"damaged row: {exc}")
    return Recheck(RecheckStatus.INCOMPLETE, tuple(results), reason="the log has no end row")
