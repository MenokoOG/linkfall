"""Builders shared by the range tests."""

import asyncio
from collections.abc import Sequence

from linkfall.range.contract import ProbeResult, Target
from linkfall.range.duel import run_probe
from linkfall.range.probes import PROBES
from linkfall.range.profiles import PROFILES, ScriptedTarget
from linkfall.range.rows import LogRow, NewRow, RowKind, fingerprint, rows_for
from linkfall.range.store import RangeHeader, RangeStore
from linkfall.range.whisper import ScriptedWhisper

RUN_ID = "run-1"
HEADER = RangeHeader(RUN_ID, "weak", "scripted", "2026-11-15T12:00:00+00:00")


def profile(name: str) -> ScriptedTarget:
    return next(p for p in PROFILES if p.name == name)


def run_range(target: Target, timeout_s: float = 1.0) -> list[ProbeResult]:
    """All seven probes against one target, with a clock that never moves."""

    async def go() -> list[ProbeResult]:
        whisper = ScriptedWhisper()
        return [await run_probe(p, whisper, target, timeout_s, lambda: 0.0) for p in PROBES]

    return asyncio.run(go())


def end_row(results: Sequence[ProbeResult]) -> NewRow:
    found = fingerprint([(r.probe.id, r.lines, r.verdict) for r in results])
    return NewRow("", RowKind.END, {"fingerprint": found, "probes": len(results)})


def log_rows(results: Sequence[ProbeResult], end: bool = True) -> list[LogRow]:
    """The rows a run of these results leaves in the log, read back with their ids."""
    store = RangeStore()
    store.create_run(HEADER)
    for result in results:
        store.append(RUN_ID, rows_for(result))
    if end:
        store.append(RUN_ID, [end_row(results)])
    return store.read_rows(RUN_ID)
