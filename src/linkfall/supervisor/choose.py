"""Lodestar's pick: ask the selector, check the answer, fall back when it fails (ADR 0006)."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from linkfall.policy.decision import Candidate, Decision
from linkfall.policy.fallback import fallback_pick
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.modelclient import ModelError
from linkfall.supervisor.selector import (
    SELECTOR_REASON_MAX,
    Selector,
    SelectorContext,
    SelectorOutput,
)

_NOTHING = "Nothing eligible. Standing by."


@dataclass(frozen=True, slots=True)
class Selection:
    chosen: Candidate | None  # None means the engine fallback action
    pick: int | None  # index into decision.eligible
    reason: str
    fallback: str | None  # why the fallback ran, or None when the selector's pick stood
    latency_ms: int


def _usable(output: SelectorOutput, count: int) -> str | None:
    """Return why a selector answer can't be used, or None."""
    pick = output.pick
    if pick is None:
        return "selector chose nothing"
    if isinstance(pick, bool) or not 0 <= pick < count:
        return f"selector pick {pick} is out of range"
    return None


async def choose(
    selector: Selector,
    decision: Decision,
    context: SelectorContext,
    budgets: Budgets,
    clock: Callable[[], float],
) -> Selection:
    candidates = decision.eligible
    started = clock()
    if not candidates:
        return Selection(None, None, _NOTHING, "nothing eligible", 0)
    why: str | None = None
    output: SelectorOutput | None = None
    try:
        output = await asyncio.wait_for(
            selector.select(candidates, context), timeout=budgets.timeout_s
        )
    except TimeoutError:
        why = f"selector timeout after {budgets.timeout_s:g}s"
    except ModelError as exc:
        why = f"selector error: {exc}"[:200]
    latency_ms = round((clock() - started) * 1000)
    if output is not None:
        why = _usable(output, len(candidates))
        if why is None and output.pick is not None:
            return Selection(
                candidates[output.pick],
                output.pick,
                output.reason[:SELECTOR_REASON_MAX],
                None,
                latency_ms,
            )
    fallback = fallback_pick(candidates)
    reason = f"fallback: {why}"[:SELECTOR_REASON_MAX]
    pick = candidates.index(fallback) if fallback is not None else None
    return Selection(fallback, pick, reason, why, latency_ms)
