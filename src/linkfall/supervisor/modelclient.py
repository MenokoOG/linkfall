"""The one seam to a language model. Any OpenAI-compatible server fits behind it (ADR 0003)."""

from dataclasses import dataclass
from typing import Protocol


class ModelError(Exception):
    """The model server failed or answered with something unusable. Never swallowed."""


@dataclass(frozen=True, slots=True)
class ModelRequest:
    system: str
    user: str
    max_tokens: int
    json_schema: dict[str, object] | None = None  # for schema-constrained output when supported
    temperature: float = 0.0


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None


class ModelClient(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...
