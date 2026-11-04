"""Rebuild the golden mission logs (full supervisor runs on scripted agents) in tests/golden/.

Run from the repo root:  PYTHONPATH=src python scripts/refresh_golden_missions.py
Each log holds proposals, decisions, selector picks and pilot choices, not just engine commands.
"""

import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from linkfall.agent_name import AgentName
from linkfall.agents.allowlist import ALLOWLIST
from linkfall.agents.scripted import ScriptedComms, ScriptedSelector, ScriptedTactical
from linkfall.agents.systems import SystemsAgent
from linkfall.agents.vitals import VitalsAgent
from linkfall.engine.actions import Action
from linkfall.engine.scenario import CINDER_WARD
from linkfall.eventlog.export import export_run, write_export
from linkfall.eventlog.store import EventStore
from linkfall.runmode import RunMode
from linkfall.supervisor.choices import LodestarActs, ManualPick, PilotChoice, Sign
from linkfall.supervisor.run import Deps, Run

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden"


@dataclass(frozen=True)
class Mission:
    name: str
    seed: int
    mode: RunMode
    choices: Sequence[PilotChoice]


MISSIONS = (
    Mission(  # Same run as the engine-only golden log, now through the whole supervisor.
        "mission-story-link85",
        4217,
        RunMode.STORY,
        [LodestarActs(85)] * 5,
    ),
    Mission(  # Same run as the engine-only golden log, now through the whole supervisor.
        "mission-hardened-link85",
        4217,
        RunMode.HARDENED,
        [
            LodestarActs(85),
            ManualPick(85, Action.AUDIT_COMMS),
            LodestarActs(85),
            Sign(85, AgentName.COMMS),
            LodestarActs(85),
        ],
    ),
)


def deps(store: EventStore) -> Deps:
    return Deps(
        store=store,
        scenario=CINDER_WARD,
        agents=[
            ScriptedTactical(fail_turns=frozenset({3})),
            SystemsAgent(),
            ScriptedComms(),
            VitalsAgent(),
        ],
        selector=ScriptedSelector(),
        allowlist=ALLOWLIST,
    )


async def play(mission: Mission, store: EventStore) -> str:
    run_id = f"golden-{mission.name}"
    run = Run.start(deps(store), run_id, mission.seed, mission.mode)
    for choice in mission.choices:
        session = await run.begin_turn(choice.link)
        await run.commit(session, choice)
    return run_id


def main() -> int:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for mission in MISSIONS:
        store = EventStore(":memory:")
        run_id = asyncio.run(play(mission, store))
        path = GOLDEN_DIR / f"{mission.name}.json"
        write_export(path, export_run(store, run_id))
        sys.stdout.write(f"wrote {path.relative_to(GOLDEN_DIR.parent.parent)}\n")
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
