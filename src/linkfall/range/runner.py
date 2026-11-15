"""Runs the seven probes against one target, one run at a time, and writes each to the log."""

import asyncio
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from linkfall.range.contract import Target, Whisper
from linkfall.range.duel import run_probe
from linkfall.range.model_target import MODEL_TARGET_NAME, ModelTarget
from linkfall.range.probes import PROBES
from linkfall.range.profiles import PROFILES
from linkfall.range.rows import NewRow, RowKind, fingerprint, rows_for
from linkfall.range.store import RangeHeader, RangeStore
from linkfall.range.whisper import ScriptedWhisper
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.modelclient import ModelClient

log = logging.getLogger("linkfall.range")


class HealthyModelClient(ModelClient, Protocol):
    async def healthy(self) -> bool: ...


class RangeBusyError(Exception):
    pass


class TargetUnavailableError(Exception):
    pass


class RunStatus(StrEnum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    INTERRUPTED = "interrupted"  # the log has no end row and nothing is running it


@dataclass(frozen=True, slots=True)
class TargetInfo:
    name: str
    kind: str
    blurb: str
    available: bool


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class RangeService:
    def __init__(
        self,
        store: RangeStore,
        client: HealthyModelClient | None,
        budgets: Budgets,
        *,
        whisper: Whisper | None = None,
        clock: Callable[[], float] | None = None,
        now: Callable[[], str] = _now,
    ) -> None:
        self._store = store
        self._client = client
        self._budgets = budgets
        self._whisper = whisper or ScriptedWhisper()
        self._clock = clock
        self._now = now
        self._task: asyncio.Task[None] | None = None
        self._running: str | None = None
        self._current: str | None = None
        self._errors: dict[str, str] = {}

    @property
    def busy(self) -> bool:
        return self._task is not None and not self._task.done()

    async def targets(self) -> list[TargetInfo]:
        scripted = [TargetInfo(p.name, p.kind, p.blurb, True) for p in PROFILES]
        if self._client is None:
            return scripted
        up = await self._client.healthy()
        return [*scripted, TargetInfo(MODEL_TARGET_NAME, "model", ModelTarget.blurb, up)]

    async def _target(self, name: str) -> Target:
        for profile in PROFILES:
            if profile.name == name:
                return profile
        if name != MODEL_TARGET_NAME:
            raise TargetUnavailableError(f"no target named {name!r}")
        if self._client is None or not await self._client.healthy():
            raise TargetUnavailableError("the model server is not available")
        return ModelTarget(self._client, self._budgets)

    async def start(self, target_name: str) -> str:
        """Create the run and start it in the background. One run at a time."""
        if self.busy:
            raise RangeBusyError("a range run is already in progress")
        target = await self._target(target_name)
        if self.busy:  # another request got in while the health check ran
            raise RangeBusyError("a range run is already in progress")
        run_id = secrets.token_urlsafe(12)
        self._store.create_run(RangeHeader(run_id, target.name, target.kind, self._now()))
        self._running, self._current = run_id, PROBES[0].id
        self._task = asyncio.create_task(self._run(run_id, target))
        return run_id

    async def _run(self, run_id: str, target: Target) -> None:
        clock = self._clock or asyncio.get_running_loop().time
        judged = []
        try:
            for probe in PROBES:
                self._current = probe.id
                result = await run_probe(
                    probe, self._whisper, target, self._budgets.timeout_s, clock
                )
                self._store.append(run_id, rows_for(result))
                judged.append((probe.id, result.lines, result.verdict))
                log.info(
                    "range probe",
                    extra={
                        "run_id": run_id,
                        "target": target.name,
                        "probe": probe.id,
                        "verdict": result.verdict.value,
                        "latency_ms": sum(line.latency_ms or 0 for line in result.lines),
                    },
                )
            end = {"fingerprint": fingerprint(judged), "probes": len(judged)}
            self._store.append(run_id, [NewRow("", RowKind.END, end)])
        except Exception as exc:  # the run stops and says why; the rows written so far stay
            self._errors[run_id] = f"{type(exc).__name__}: {exc}"[:200]
            log.exception("range run failed", extra={"run_id": run_id})
        finally:
            self._current = None

    def status(self, run_id: str, ended: bool) -> RunStatus:
        if run_id in self._errors:
            return RunStatus.ERROR
        if ended:
            return RunStatus.DONE
        return RunStatus.RUNNING if self.busy and run_id == self._running else RunStatus.INTERRUPTED

    def current_probe(self, run_id: str) -> str | None:
        return self._current if self.busy and run_id == self._running else None

    def error(self, run_id: str) -> str | None:
        return self._errors.get(run_id)

    async def wait(self) -> None:
        """For tests and shutdown: let the run in progress finish."""
        if self._task is not None:
            await self._task
