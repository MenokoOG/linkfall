"""A scripted model client for tests and the no-model demo. It records every request."""

from collections.abc import Callable

from linkfall.supervisor.modelclient import ModelError, ModelRequest, ModelResponse


class FakeClient:
    def __init__(self, respond: Callable[[ModelRequest], str | ModelError]) -> None:
        self._respond = respond
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        answer = self._respond(request)
        if isinstance(answer, ModelError):
            raise answer
        return ModelResponse(
            text=answer, prompt_tokens=len(request.user) // 4, completion_tokens=len(answer) // 4
        )


class NoModelClient:
    """Fails on any call. Wire it where a model must never be reached."""

    async def complete(self, request: ModelRequest) -> ModelResponse:
        raise ModelError("a model call was attempted where none is allowed")
