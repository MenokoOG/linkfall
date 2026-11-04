"""The runs this process is playing. The log is the record; this is only the live handle."""

import asyncio
import logging
import secrets
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from linkfall.agents.allowlist import ALLOWLIST
from linkfall.agents.crew import model_crew, scripted_crew
from linkfall.api.config import ApiConfig
from linkfall.engine.scenario import SCENARIOS
from linkfall.eventlog.store import EventStore
from linkfall.runmode import RunMode
from linkfall.supervisor.http_client import HttpModelClient
from linkfall.supervisor.modelclient import ModelClient
from linkfall.supervisor.run import Deps, Run
from linkfall.supervisor.session import TurnResult, TurnSession

log = logging.getLogger("linkfall.api")


class HealthyModelClient(ModelClient, Protocol):
    async def healthy(self) -> bool: ...


class Phase(StrEnum):
    IDLE = "idle"
    COLLECTING = "collecting"
    AWAITING_PILOT = "awaiting_pilot"
    ERROR = "error"


class RegistryFullError(Exception):
    pass


class ModelUnavailableError(Exception):
    pass


@dataclass
class ActiveRun:
    run: Run
    seed: int
    scenario: str
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    phase: Phase = Phase.IDLE
    session: TurnSession | None = None
    task: asyncio.Task[None] | None = None
    last_result: TurnResult | None = None
    last_turn: int | None = None  # the turn number last_result belongs to
    error: str | None = None


class Registry:
    def __init__(
        self, config: ApiConfig, store: EventStore, client: HealthyModelClient | None = None
    ) -> None:
        self._config = config
        self._store = store
        self._runs: dict[str, ActiveRun] = {}
        self._client: HealthyModelClient | None = client or (
            HttpModelClient(config.model_url) if config.model_url else None
        )

    @property
    def model_configured(self) -> bool:
        return self._client is not None

    def get(self, run_id: str) -> ActiveRun | None:
        return self._runs.get(run_id)

    async def model_up(self) -> bool:
        return self._client is not None and await self._client.healthy()

    async def create(
        self, seed: int, mode: RunMode, scenario: str, crew: str | None
    ) -> tuple[str, ActiveRun, str]:
        use_model = crew == "model" or (crew is None and self._client is not None)
        if use_model:
            if self._client is None or not await self._client.healthy():
                raise ModelUnavailableError("the model server is not available")
            agents, selector = model_crew(self._client, self._config.budgets)
        else:
            agents, selector = scripted_crew()
        self._make_room()
        deps = Deps(
            store=self._store,
            scenario=SCENARIOS[scenario],
            agents=agents,
            selector=selector,
            allowlist=ALLOWLIST,
            budgets=self._config.budgets,
        )
        run_id = secrets.token_urlsafe(12)
        active = ActiveRun(Run.start(deps, run_id, seed, mode), seed, scenario)
        self._runs[run_id] = active
        return run_id, active, "model" if use_model else "scripted"

    def _make_room(self) -> None:
        if len(self._runs) < self._config.max_runs:
            return
        for run_id, active in list(self._runs.items()):
            if active.run.state.over and active.phase is Phase.IDLE:
                del self._runs[run_id]
                return
        raise RegistryFullError("too many runs in progress")
