"""Lodestar's selector: picks among candidates the policy already allows (ADR 0006)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from linkfall.engine.state import State
from linkfall.engine.zone_effects import Zone
from linkfall.policy.decision import Candidate
from linkfall.policy.fallback import fallback_pick

SELECTOR_REASON_MAX = 140


@dataclass(frozen=True, slots=True)
class SelectorOutput:
    pick: int | None  # an index into the candidates, or None for "nothing"
    reason: str


@dataclass(frozen=True, slots=True)
class SelectorContext:
    """The battlefield facts Lodestar sees when it chooses. The run mode is not one of them."""

    turn: int
    zone: Zone
    integrity: int
    heat: int
    ammo: int
    power: int
    shields: bool
    enemies: int

    @classmethod
    def from_state(cls, state: State, zone: Zone) -> "SelectorContext":
        return cls(
            turn=state.turn,
            zone=zone,
            integrity=state.hp,
            heat=state.heat,
            ammo=state.ammo,
            power=state.power,
            shields=state.shields,
            enemies=state.ashgrove + state.visitors,
        )


class Selector(Protocol):
    async def select(
        self, candidates: Sequence[Candidate], context: SelectorContext
    ) -> SelectorOutput: ...


class RulesSelector:
    """No model: Tactical first, then Systems. The baseline for evals (ADR 0006)."""

    async def select(
        self, candidates: Sequence[Candidate], context: SelectorContext
    ) -> SelectorOutput:
        chosen = fallback_pick(candidates)
        if chosen is None:
            return SelectorOutput(None, "Nothing eligible from Tactical or Systems.")
        return SelectorOutput(
            list(candidates).index(chosen), "Rules baseline: Tactical, then Systems."
        )
