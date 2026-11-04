"""Per-call limits (ADR 0010: timeout about 5 times the measured median of 8.8 s)."""

from dataclasses import dataclass

DEFAULT_TIMEOUT_S = 45.0
DEFAULT_MAX_TOKENS = 120


@dataclass(frozen=True, slots=True)
class Budgets:
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_tokens: int = DEFAULT_MAX_TOKENS
