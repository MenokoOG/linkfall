"""Lodestar's selector: picks among candidates the policy already allows (ADR 0006)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from linkfall.policy.decision import Candidate
from linkfall.policy.fallback import fallback_pick

SELECTOR_REASON_MAX = 140


@dataclass(frozen=True, slots=True)
class SelectorOutput:
    pick: int | None  # an index into the candidates, or None for "nothing"
    reason: str


class Selector(Protocol):
    async def select(self, candidates: Sequence[Candidate]) -> SelectorOutput: ...


class RulesSelector:
    """No model: Tactical first, then Systems. The baseline for evals (ADR 0006)."""

    async def select(self, candidates: Sequence[Candidate]) -> SelectorOutput:
        chosen = fallback_pick(candidates)
        if chosen is None:
            return SelectorOutput(None, "Nothing eligible from Tactical or Systems.")
        return SelectorOutput(
            list(candidates).index(chosen), "Rules baseline: Tactical, then Systems."
        )
