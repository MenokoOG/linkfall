"""Settings from the environment. Nothing here is a secret."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from linkfall.supervisor.budgets import DEFAULT_MAX_TOKENS, DEFAULT_TIMEOUT_S, Budgets

DEFAULT_HOSTS = ("localhost", "127.0.0.1", "[::1]")


class ConfigError(ValueError):
    """An environment value is unusable. The server refuses to start."""


@dataclass(frozen=True)
class ApiConfig:
    db_path: Path = Path("data/linkfall.sqlite3")
    range_db: Path | None = None  # None means beside the event log
    model_url: str | None = None  # None means no model: only the scripted crew is offered
    allowed_hosts: tuple[str, ...] = DEFAULT_HOSTS
    max_runs: int = 20
    max_body_bytes: int = 4096
    budgets: Budgets = field(default_factory=Budgets)
    stream_poll_s: float = 0.25
    stream_heartbeat_s: float = 15.0
    stream_max_s: float = 3600.0

    @property
    def range_db_path(self) -> Path:
        return self.range_db or self.db_path.with_name("linkfall-range.sqlite3")


def _number(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be positive")
    return value


def load_config(env: Mapping[str, str] | None = None) -> ApiConfig:
    env = os.environ if env is None else env
    hosts = env.get("LINKFALL_ALLOWED_HOSTS")
    allowed = tuple(h.strip() for h in hosts.split(",") if h.strip()) if hosts else DEFAULT_HOSTS
    budgets = Budgets(
        timeout_s=_number(env, "LINKFALL_MODEL_TIMEOUT_S", DEFAULT_TIMEOUT_S),
        max_tokens=int(_number(env, "LINKFALL_MODEL_MAX_TOKENS", DEFAULT_MAX_TOKENS)),
    )
    range_db = env.get("LINKFALL_RANGE_DB")
    return ApiConfig(
        db_path=Path(env.get("LINKFALL_DB", "data/linkfall.sqlite3")),
        range_db=Path(range_db) if range_db else None,
        model_url=env.get("LINKFALL_MODEL_URL") or None,
        allowed_hosts=allowed,
        max_runs=int(_number(env, "LINKFALL_MAX_RUNS", 20)),
        budgets=budgets,
    )
