"""Golden logs: recorded runs that CI replays. A rule change that alters one fails here."""

from pathlib import Path

import pytest

from linkfall.eventlog.export import import_run, read_export
from linkfall.eventlog.replay import replay
from linkfall.eventlog.store import EventStore

GOLDEN = sorted((Path(__file__).parent / "golden").glob("*.json"))
EXPECTED_OUTCOME = {
    "story-forged-order-link85": "DESTROYED",
    "pilot-audit-and-truce-link55": "SURVIVED",
}


def test_golden_logs_exist() -> None:
    assert {p.stem for p in GOLDEN} == set(EXPECTED_OUTCOME)


@pytest.mark.parametrize("path", GOLDEN, ids=lambda p: p.stem)
def test_golden_log_replays_to_its_recorded_fingerprint(path: Path) -> None:
    data = read_export(path)
    store = EventStore()
    run_id = import_run(store, data)
    result = replay(store, run_id)
    assert result.failure is None, result.failure
    assert result.fingerprint == data["fingerprint"]
    assert result.state is not None
    assert result.state.outcome is not None
    assert result.state.outcome.value == EXPECTED_OUTCOME[path.stem]
