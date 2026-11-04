"""Rebuild the golden logs in tests/golden/ from the command lists below.

Run from the repo root:  PYTHONPATH=src python scripts/refresh_golden.py
A rule change that alters a golden log shows up as a diff in the pull request.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from linkfall.engine.actions import Action
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.step import Command
from linkfall.engine.zone_effects import Zone
from linkfall.eventlog.export import export_run, write_export
from linkfall.eventlog.record import record_step, start_run
from linkfall.eventlog.store import EventStore
from linkfall.runmode import RunMode

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden"


@dataclass(frozen=True)
class GoldenRun:
    name: str
    seed: int
    mode: RunMode
    commands: tuple[Command, ...]


def _lodestar(zone: Zone, *actions: Action) -> tuple[Command, ...]:
    return tuple(Command(a, zone, manual=False) for a in actions)


def _pilot(zone: Zone, *actions: Action) -> tuple[Command, ...]:
    return tuple(Command(a, zone, manual=True) for a in actions)


RUNS = (
    GoldenRun(
        # Story mode at link 85: Lodestar runs the forged drop_shields order and the armor is lost.
        name="story-forged-order-link85",
        seed=4217,
        mode=RunMode.STORY,
        commands=_lodestar(
            Zone.DELEGATED,
            Action.OVERCHARGE,
            Action.DROP_SHIELDS,
            Action.HOLD_SHIELD,
            Action.DROP_SHIELDS,
            Action.HOLD_SHIELD,
        ),
    ),
    GoldenRun(
        # The pilot audits the channel, then signs the truce.
        name="pilot-audit-and-truce-link55",
        seed=4217,
        mode=RunMode.STORY,
        commands=_pilot(
            Zone.ASSISTED,
            Action.SUPPRESS,
            Action.AUDIT_COMMS,
            Action.FLANK,
            Action.ACCEPT_TRUCE,
            Action.HOLD_SHIELD,
        ),
    ),
)


def build(run: GoldenRun) -> Path:
    store = EventStore(":memory:")
    run_id = f"golden-{run.name}"
    state = start_run(store, run_id, run.seed, run.mode, CINDER_WARD)
    for command in run.commands:
        state = record_step(store, run_id, CINDER_WARD, state, command)
    path = GOLDEN_DIR / f"{run.name}.json"
    write_export(path, export_run(store, run_id))
    store.close()
    return path


def main() -> int:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for run in RUNS:
        sys.stdout.write(f"wrote {build(run).relative_to(GOLDEN_DIR.parent.parent)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
