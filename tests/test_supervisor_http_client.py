"""HttpModelClient against a throwaway local server. No real model."""

import asyncio
import json
import select
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from linkfall.supervisor.http_client import MAX_RESPONSE_BYTES, HttpModelClient
from linkfall.supervisor.modelclient import ModelError, ModelRequest

GOOD = {
    "choices": [{"message": {"content": '{"action":"flank","say":"go"}'}}],
    "usage": {"prompt_tokens": 380, "completion_tokens": 20},
    "timings": {"cache_n": 321},
}


class Stub:
    def __init__(self) -> None:
        self.status = 200
        self.body: bytes = json.dumps(GOOD).encode()
        self.delay_s = 0.0
        self.seen: list[dict[str, Any]] = []
        self.disconnected = threading.Event()


def make_handler(stub: Stub) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"])
            stub.seen.append({"path": self.path, "body": json.loads(self.rfile.read(length))})
            deadline = time.monotonic() + stub.delay_s
            while time.monotonic() < deadline:
                readable, _, _ = select.select([self.connection], [], [], 0.02)
                if readable and not self.connection.recv(1, 2):  # 2 = MSG_PEEK
                    stub.disconnected.set()
                    return
            self.send_response(stub.status)
            self.send_header("Content-Length", str(len(stub.body)))
            self.end_headers()
            self.wfile.write(stub.body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    return Handler


@pytest.fixture
def stub() -> Iterator[tuple[Stub, str]]:
    state = Stub()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    yield state, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


REQUEST = ModelRequest(system="sys", user="usr", max_tokens=40, json_schema={"type": "object"})


def complete(url: str, **kwargs: Any) -> Any:
    return asyncio.run(HttpModelClient(url, request_timeout_s=2.0, **kwargs).complete(REQUEST))


def test_a_good_answer_is_parsed_with_token_counts(stub: tuple[Stub, str]) -> None:
    state, url = stub
    response = complete(url)
    assert response.text == '{"action":"flank","say":"go"}'
    assert (response.prompt_tokens, response.completion_tokens, response.cached_tokens) == (
        380,
        20,
        321,
    )
    sent = state.seen[0]
    assert sent["path"] == "/v1/chat/completions"
    assert sent["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert sent["body"]["max_tokens"] == 40
    assert sent["body"]["temperature"] == 0.0
    assert sent["body"]["cache_prompt"] is True
    assert sent["body"]["response_format"]["json_schema"]["schema"] == {"type": "object"}


def test_options_are_left_out_when_unused(stub: tuple[Stub, str]) -> None:
    state, url = stub
    asyncio.run(
        HttpModelClient(url, cache_prompt=False).complete(ModelRequest("s", "u", max_tokens=5))
    )
    body = state.seen[0]["body"]
    assert "cache_prompt" not in body
    assert "response_format" not in body
    assert "model" not in body


def test_a_model_name_is_sent_when_given(stub: tuple[Stub, str]) -> None:
    state, url = stub
    complete(url, model="qwen")
    assert state.seen[0]["body"]["model"] == "qwen"


def test_a_path_prefix_is_kept(stub: tuple[Stub, str]) -> None:
    state, url = stub
    complete(url + "/base/")
    assert state.seen[0]["path"] == "/base/v1/chat/completions"


def test_an_error_status_becomes_a_model_error(stub: tuple[Stub, str]) -> None:
    state, url = stub
    state.status, state.body = 503, b"overloaded " + b"x" * 500
    with pytest.raises(ModelError, match="503") as info:
        complete(url)
    assert len(str(info.value)) < 200


@pytest.mark.parametrize(
    "body",
    [b"not json", b"{}", b'{"choices":[]}', b'{"choices":[{"message":{"content":5}}]}', b"[1]"],
)
def test_an_unexpected_body_becomes_a_model_error(stub: tuple[Stub, str], body: bytes) -> None:
    state, url = stub
    state.body = body
    with pytest.raises(ModelError):
        complete(url)


def test_an_oversized_body_is_refused(stub: tuple[Stub, str]) -> None:
    state, url = stub
    state.body = b'{"choices":[{"message":{"content":"' + b"x" * MAX_RESPONSE_BYTES + b'"}}]}'
    with pytest.raises(ModelError, match="too large"):
        complete(url)


def test_a_refused_connection_becomes_a_model_error() -> None:
    with pytest.raises(ModelError, match="cannot reach"):
        complete("http://127.0.0.1:9")


def test_a_slow_server_hits_the_socket_timeout(stub: tuple[Stub, str]) -> None:
    state, url = stub
    state.delay_s = 1.0
    client = HttpModelClient(url, request_timeout_s=0.2)
    with pytest.raises(ModelError):
        asyncio.run(client.complete(REQUEST))


def test_cancelling_a_call_closes_the_connection_so_the_server_stops(
    stub: tuple[Stub, str],
) -> None:
    state, url = stub
    state.delay_s = 5.0
    started = time.monotonic()

    async def go() -> None:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(HttpModelClient(url).complete(REQUEST), timeout=0.3)

    asyncio.run(go())
    assert time.monotonic() - started < 2.0
    assert state.disconnected.wait(timeout=2.0)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com",
        "http://user:secret@example.com",
        "http://",
        "example.com:8080",
    ],
)
def test_unsafe_urls_are_refused(url: str) -> None:
    with pytest.raises(ValueError, match="model URL"):
        HttpModelClient(url)
