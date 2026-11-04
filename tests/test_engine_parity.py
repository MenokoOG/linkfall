"""The Python engine must reproduce the prototype's numbers turn by turn."""

import json
from pathlib import Path
from typing import Any

import pytest

from linkfall.engine.actions import Action
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.state import State
from linkfall.engine.step import Command, new_game, step
from linkfall.engine.zone_effects import Zone

DATA = Path(__file__).parent / "engine" / "data" / "prototype_traces.json"
TRACES: list[dict[str, Any]] = json.loads(DATA.read_text(encoding="utf-8"))["traces"]


def zone_for(link: int) -> Zone:
    if link < 30:
        return Zone.MANUAL
    return Zone.ASSISTED if link < 60 else Zone.DELEGATED


def view(s: State) -> dict[str, Any]:
    return {
        "turn": s.turn, "hp": s.hp, "heat": s.heat, "power": s.power, "ammo": s.ammo,
        "strain": s.strain, "shields": s.shields, "A": s.ashgrove, "X": s.visitors,
        "compromised": s.compromised, "quarantined": s.quarantined, "truce": s.truce,
        "over": s.over, "outcome": s.outcome.value if s.outcome else None,
        "sigOk": s.sig_ok, "sigBad": s.sig_bad,
    }  # fmt: skip


@pytest.mark.parametrize("trace", TRACES, ids=lambda t: f"{t['mode']}-{t['seed']}-{t['link']}")
def test_trace_matches_prototype(trace: dict[str, Any]) -> None:
    state, _ = new_game(trace["seed"], CINDER_WARD)
    assert view(state) == trace["init"]
    manual = trace["mode"] == "manual"
    zone = zone_for(trace["link"])
    for index, entry in enumerate(trace["steps"]):
        state, _ = step(state, CINDER_WARD, Command(Action(entry["action"]), zone, manual=manual))
        assert view(state) == entry["after"], f"step {index + 1} ({entry['action']})"
