"""The write path: run the engine and log the command and its events in one transaction."""

from linkfall.engine.scenario import Scenario
from linkfall.engine.state import State
from linkfall.engine.step import Command, new_game, step
from linkfall.eventlog.codec import command_row, engine_row
from linkfall.eventlog.schema import SCHEMA_VERSION
from linkfall.eventlog.store import EventStore
from linkfall.eventlog.types import RunHeader
from linkfall.runmode import RunMode


def start_run(
    store: EventStore, run_id: str, seed: int, mode: RunMode, scenario: Scenario
) -> State:
    state, events = new_game(seed, scenario)
    header = RunHeader(run_id, seed, mode, scenario.name, SCHEMA_VERSION)
    store.create_run(header, [engine_row(e) for e in events])
    return state


def record_step(
    store: EventStore, run_id: str, scenario: Scenario, state: State, command: Command
) -> State:
    """Step the engine, then log. If the engine raises, nothing is written."""
    new_state, events = step(state, scenario, command)
    rows = [command_row(state.turn, command), *(engine_row(e) for e in events)]
    store.append_batch(run_id, rows)
    return new_state
