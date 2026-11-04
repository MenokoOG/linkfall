"""Move a run in and out of a store as plain JSON. Golden logs use this format."""

import json
from pathlib import Path

from linkfall.eventlog.replay import replay
from linkfall.eventlog.schema import SCHEMA_VERSION
from linkfall.eventlog.store import EventLogError, EventStore
from linkfall.eventlog.types import JsonValue, NewRow, RunHeader
from linkfall.runmode import RunMode


def export_run(store: EventStore, run_id: str) -> dict[str, JsonValue]:
    """Export a run with its replay fingerprint. A log that fails replay is not exported."""
    result = replay(store, run_id)
    if result.failure is not None:
        raise EventLogError(f"run {run_id!r} fails replay: {result.failure.reason}")
    header = store.get_run(run_id)
    rows: list[JsonValue] = [
        {"turn": r.turn, "kind": r.kind, "payload": r.payload} for r in store.read_rows(run_id)
    ]
    run: dict[str, JsonValue] = {
        "run_id": header.run_id,
        "seed": header.seed,
        "mode": header.mode.value,
        "scenario": header.scenario,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "run": run,
        "rows": rows,
        "fingerprint": result.fingerprint,
    }


def import_run(store: EventStore, data: dict[str, JsonValue]) -> str:
    """Load an exported run into a store. Shape errors raise EventLogError."""
    try:
        if data["schema_version"] != SCHEMA_VERSION:
            raise EventLogError(f"unsupported export schema version {data['schema_version']!r}")
        run = data["run"]
        raw_rows = data["rows"]
        if not isinstance(run, dict) or not isinstance(raw_rows, list):
            raise EventLogError("export has the wrong shape")
        seed = run["seed"]
        run_id, scenario = run["run_id"], run["scenario"]
        if (
            not isinstance(seed, int)
            or not isinstance(run_id, str)
            or not isinstance(scenario, str)
        ):
            raise EventLogError("export header has the wrong types")
        header = RunHeader(run_id, seed, RunMode(str(run["mode"])), scenario, SCHEMA_VERSION)
        rows: list[NewRow] = []
        for raw in raw_rows:
            if not isinstance(raw, dict):
                raise EventLogError("export row has the wrong shape")
            turn, kind, payload = raw["turn"], raw["kind"], raw["payload"]
            if (
                not isinstance(turn, int)
                or not isinstance(kind, str)
                or not isinstance(payload, dict)
            ):
                raise EventLogError("export row has the wrong types")
            rows.append(NewRow(turn, kind, payload))
    except (KeyError, ValueError) as exc:
        raise EventLogError(f"export is not valid: {exc!r}") from exc
    store.create_run(header, rows)
    return run_id


def write_export(path: Path, data: dict[str, JsonValue]) -> None:
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def read_export(path: Path) -> dict[str, JsonValue]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise EventLogError(f"{path.name} is not a JSON object")
    return loaded
