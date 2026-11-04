"""ModelClient for an OpenAI-compatible server such as llama.cpp's (ADR 0003, ADR 0010).

Standard library only. A call that the supervisor cancels (its timeout) also closes the socket,
so the server stops generating and its single slot frees up.
"""

import asyncio
import contextlib
import http.client
import json
import socket
import threading
from urllib.parse import urlsplit

from linkfall.supervisor.modelclient import ModelError, ModelRequest, ModelResponse

MAX_RESPONSE_BYTES = 256 * 1024
_MAX_ERROR_TEXT = 120
_OK = 200


class _Call:
    """One in-flight request, abortable from another thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conn: http.client.HTTPConnection | None = None
        self._aborted = False

    def attach(self, conn: http.client.HTTPConnection) -> None:
        with self._lock:
            self._conn = conn
            if self._aborted:
                conn.close()

    def abort(self) -> None:
        with self._lock:
            self._aborted = True
            conn = self._conn
            if conn is not None:
                if conn.sock is not None:
                    with contextlib.suppress(
                        OSError
                    ):  # already closed is fine; we only wake the reader
                        conn.sock.shutdown(socket.SHUT_RDWR)
                conn.close()


class HttpModelClient:
    def __init__(
        self,
        base_url: str,
        *,
        request_timeout_s: float = 60.0,
        model: str | None = None,
        cache_prompt: bool = True,
    ) -> None:
        parts = urlsplit(base_url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("model URL must be http or https with a host")
        if parts.username or parts.password:
            raise ValueError("model URL must not carry credentials")
        self._https = parts.scheme == "https"
        self._host = parts.hostname
        self._port = parts.port
        self._prefix = parts.path.rstrip("/")
        self._timeout = request_timeout_s
        self._model = model
        self._cache_prompt = cache_prompt

    async def complete(self, request: ModelRequest) -> ModelResponse:
        call = _Call()
        try:
            return await asyncio.to_thread(self._post, request, call)
        except asyncio.CancelledError:
            call.abort()
            raise

    async def healthy(self, timeout_s: float = 3.0) -> bool:
        """True when the server answers its /health route with 200. Never raises."""
        return await asyncio.to_thread(self._probe, timeout_s)

    def _probe(self, timeout_s: float) -> bool:
        factory = http.client.HTTPSConnection if self._https else http.client.HTTPConnection
        conn = factory(self._host, self._port, timeout=timeout_s)
        try:
            conn.request("GET", f"{self._prefix}/health")
            return conn.getresponse().status == _OK
        except (OSError, http.client.HTTPException):
            return False
        finally:
            conn.close()

    def _body(self, request: ModelRequest) -> bytes:
        body: dict[str, object] = {
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }
        if self._model:
            body["model"] = self._model
        if self._cache_prompt:
            body["cache_prompt"] = True
        if request.json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "reply", "schema": request.json_schema},
            }
        return json.dumps(body).encode("utf-8")

    def _post(self, request: ModelRequest, call: _Call) -> ModelResponse:
        factory = http.client.HTTPSConnection if self._https else http.client.HTTPConnection
        conn = factory(self._host, self._port, timeout=self._timeout)
        call.attach(conn)
        try:
            conn.request(
                "POST",
                f"{self._prefix}/v1/chat/completions",
                body=self._body(request),
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status = response.status
        except (OSError, http.client.HTTPException) as exc:
            raise ModelError(f"cannot reach the model server: {type(exc).__name__}") from exc
        finally:
            conn.close()
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ModelError("model response is too large")
        if status != _OK:
            text = raw[:_MAX_ERROR_TEXT].decode("utf-8", errors="replace")
            raise ModelError(f"model server answered {status}: {text}")
        return _parse(raw)


def _parse(raw: bytes) -> ModelResponse:
    try:
        data = json.loads(raw)
        text = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ModelError("model response has an unexpected shape") from exc
    if not isinstance(text, str):
        raise ModelError("model response has no text")
    usage = data.get("usage") if isinstance(data, dict) else None
    timings = data.get("timings") if isinstance(data, dict) else None
    return ModelResponse(
        text=text,
        prompt_tokens=_int(usage, "prompt_tokens"),
        completion_tokens=_int(usage, "completion_tokens"),
        cached_tokens=_int(timings, "cache_n"),
    )


def _int(section: object, key: str) -> int | None:
    if not isinstance(section, dict):
        return None
    value = section.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None
