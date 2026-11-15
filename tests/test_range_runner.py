import asyncio
import logging
from collections.abc import Sequence

import pytest

from linkfall.range.recheck import RecheckStatus, recheck
from linkfall.range.rows import NewRow, RowKind
from linkfall.range.runner import (
    RangeBusyError,
    RangeService,
    RunStatus,
    TargetUnavailableError,
)
from linkfall.range.store import RangeLogError, RangeStore
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.modelclient import ModelRequest, ModelResponse

DECLINE = '{"say":"Declined.","action":"refer_to_pilot"}'


class Model:
    """A model client with a health flag. With a gate, each call waits until it is opened."""

    def __init__(self, up: bool = True, gate: asyncio.Event | None = None) -> None:
        self.up = up
        self.gate = gate
        self.calls = 0
        self.health_checks = 0

    async def healthy(self) -> bool:
        self.health_checks += 1
        await asyncio.sleep(0)  # a real health check yields to other requests
        return self.up

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        return ModelResponse(DECLINE)


class FailingStore(RangeStore):
    """Writes the first probe, then fails like a locked or full disk would."""

    def __init__(self) -> None:
        super().__init__()
        self.appends = 0

    def append(self, run_id: str, rows: Sequence[NewRow]) -> None:
        self.appends += 1
        if self.appends > 1:
            raise RangeLogError("cannot append: database is locked")
        super().append(run_id, rows)


def service(store: RangeStore | None = None, model: Model | None = None) -> RangeService:
    return RangeService(
        store or RangeStore(), model, Budgets(timeout_s=1.0), now=lambda: "2026-11-15T12:00:00"
    )


def ended(store: RangeStore, run_id: str) -> bool:
    return any(row.kind == RowKind.END for row in store.read_rows(run_id))


def test_a_scripted_run_writes_every_probe_and_an_end_row() -> None:
    async def go() -> None:
        store = RangeStore()
        svc = service(store)
        run_id = await svc.start("weak")
        await svc.wait()
        header = store.get_run(run_id)
        assert (header.target, header.kind) == ("weak", "scripted")
        assert header.created_at == "2026-11-15T12:00:00"
        rows = store.read_rows(run_id)
        assert [row.kind for row in rows].count("verdict") == 7
        assert rows[-1].kind == "end"
        assert rows[-1].payload["probes"] == 7
        check = recheck(rows)
        assert check.status is RecheckStatus.OK
        assert rows[-1].payload["fingerprint"] == check.fingerprint
        assert svc.status(run_id, ended(store, run_id)) is RunStatus.DONE
        assert svc.error(run_id) is None
        assert svc.current_probe(run_id) is None
        assert not svc.busy

    asyncio.run(go())


def test_run_ids_are_unguessable_and_differ() -> None:
    async def go() -> None:
        svc = service()
        first = await svc.start("reference")
        await svc.wait()
        second = await svc.start("reference")
        await svc.wait()
        assert first != second
        assert len(first) == 16

    asyncio.run(go())


def test_a_model_run_makes_fourteen_calls() -> None:
    async def go() -> None:
        store, model = RangeStore(), Model()
        svc = service(store, model)
        run_id = await svc.start("model")
        await svc.wait()
        assert model.calls == 14
        assert store.get_run(run_id).kind == "model"
        assert recheck(store.read_rows(run_id)).status is RecheckStatus.OK

    asyncio.run(go())


def test_targets_list_the_scripts_and_the_model_with_its_health() -> None:
    async def go() -> None:
        names = [(t.name, t.kind, t.available) for t in await service().targets()]
        assert names == [
            ("reference", "scripted", True),
            ("weak", "scripted", True),
            ("overreach", "scripted", True),
        ]
        up = await service(model=Model(up=True)).targets()
        assert (up[-1].name, up[-1].kind, up[-1].available) == ("model", "model", True)
        assert up[-1].blurb
        down = await service(model=Model(up=False)).targets()
        assert down[-1].available is False
        assert len(down) == 4

    asyncio.run(go())


@pytest.mark.parametrize(
    ("name", "model", "message"),
    [
        ("nobody", Model(), "no target named 'nobody'"),
        ("model", None, "the model server is not available"),
        ("model", Model(up=False), "the model server is not available"),
    ],
)
def test_a_target_that_cannot_run_is_refused_and_no_run_is_created(
    name: str, model: Model | None, message: str
) -> None:
    async def go() -> None:
        svc = service(model=model)
        with pytest.raises(TargetUnavailableError, match=message):
            await svc.start(name)
        assert not svc.busy

    asyncio.run(go())


def test_a_second_run_is_refused_while_one_is_running() -> None:
    async def go() -> None:
        gate = asyncio.Event()
        store, model = RangeStore(), Model(gate=gate)
        svc = service(store, model)
        run_id = await svc.start("model")
        await asyncio.sleep(0.01)
        assert svc.busy
        assert svc.status(run_id, ended=False) is RunStatus.RUNNING
        assert svc.current_probe(run_id) == "P1"
        assert svc.current_probe("another-run") is None
        for name in ("model", "reference"):
            with pytest.raises(RangeBusyError):
                await svc.start(name)
        gate.set()
        await svc.wait()
        assert svc.status(run_id, ended(store, run_id)) is RunStatus.DONE
        again = await svc.start("reference")
        await svc.wait()
        assert again != run_id

    asyncio.run(go())


def test_two_starts_that_race_through_the_health_check_give_one_run() -> None:
    async def go() -> None:
        gate = asyncio.Event()
        model = Model(gate=gate)
        svc = service(model=model)
        outcomes = await asyncio.gather(
            svc.start("model"), svc.start("model"), return_exceptions=True
        )
        assert model.health_checks == 2  # both passed the first busy check
        assert sum(isinstance(outcome, str) for outcome in outcomes) == 1
        assert sum(isinstance(outcome, RangeBusyError) for outcome in outcomes) == 1
        gate.set()
        await svc.wait()

    asyncio.run(go())


def test_a_log_write_failure_stops_the_run_and_says_why(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def go() -> None:
        store = FailingStore()
        svc = service(store)
        with caplog.at_level(logging.ERROR, logger="linkfall.range"):
            run_id = await svc.start("reference")
            await svc.wait()
        assert svc.status(run_id, ended=False) is RunStatus.ERROR
        assert svc.error(run_id) == "RangeLogError: cannot append: database is locked"
        assert not svc.busy
        assert svc.current_probe(run_id) is None
        rows = store.read_rows(run_id)
        assert {row.probe for row in rows} == {"P1"}  # the first probe stays, whole
        assert recheck(rows).status is RecheckStatus.INCOMPLETE
        assert store.appends == 2  # it stopped at the failure
        assert [record.message for record in caplog.records] == ["range run failed"]

    asyncio.run(go())


def test_a_run_nothing_is_running_reads_as_interrupted() -> None:
    svc = service()
    assert svc.status("from-before-a-restart", ended=False) is RunStatus.INTERRUPTED
    assert svc.status("from-before-a-restart", ended=True) is RunStatus.DONE
    assert svc.current_probe("from-before-a-restart") is None
    asyncio.run(svc.wait())  # nothing to wait for


def test_each_probe_is_logged_with_its_verdict(caplog: pytest.LogCaptureFixture) -> None:
    async def go() -> str:
        svc = service()
        run_id = await svc.start("overreach")
        await svc.wait()
        return run_id

    with caplog.at_level(logging.INFO, logger="linkfall.range"):
        run_id = asyncio.run(go())
    records = [record for record in caplog.records if record.message == "range probe"]
    assert [record.__dict__["probe"] for record in records] == [f"P{n}" for n in range(1, 8)]
    assert records[-1].__dict__["verdict"] == "OVERSTEP"
    assert {record.__dict__["target"] for record in records} == {"overreach"}
    assert {record.__dict__["run_id"] for record in records} == {run_id}
    assert all(isinstance(record.__dict__["latency_ms"], int) for record in records)
