import json
import logging
import threading
from collections.abc import Iterator
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

import pytest
import uvicorn

from api_support import config, make_app, run
from asgi import Client
from linkfall.api.app import create_app
from linkfall.api.config import ConfigError, load_config
from linkfall.api.logs import JsonFormatter, configure_logging, request_id
from linkfall.eventlog.store import EventStore


def test_config_defaults_and_overrides() -> None:
    default = load_config({})
    assert default.model_url is None
    assert default.allowed_hosts == ("localhost", "127.0.0.1", "[::1]")
    assert default.max_runs == 20
    custom = load_config(
        {
            "LINKFALL_DB": "/data/x.sqlite3",
            "LINKFALL_MODEL_URL": "http://model:8080",
            "LINKFALL_ALLOWED_HOSTS": "localhost, example.test",
            "LINKFALL_MODEL_TIMEOUT_S": "30",
            "LINKFALL_MAX_RUNS": "5",
        }
    )
    assert custom.db_path == Path("/data/x.sqlite3")
    assert custom.model_url == "http://model:8080"
    assert custom.allowed_hosts == ("localhost", "example.test")
    assert custom.budgets.timeout_s == 30.0
    assert custom.max_runs == 5


@pytest.mark.parametrize(
    "env",
    [
        {"LINKFALL_MODEL_TIMEOUT_S": "soon"},
        {"LINKFALL_MODEL_TIMEOUT_S": "0"},
        {"LINKFALL_MAX_RUNS": "-1"},
    ],
)
def test_bad_settings_stop_the_server_from_starting(env: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        load_config(env)


def test_an_unexpected_error_is_a_safe_500_with_a_request_id(caplog: Any) -> None:
    async def go() -> None:
        app = make_app()

        async def boom(*_a: object, **_k: object) -> None:
            raise RuntimeError("secret internals")

        app.state.registry.create = boom
        response = await Client(app).post(
            "/api/runs", {"seed": 1, "mode": "story", "scenario": "cinder-ward"}
        )
        assert response.status == 500
        body = response.json()
        assert body["error"] == "internal error"
        assert body["request_id"] == response.headers["x-request-id"]
        assert "secret" not in response.text
        assert "content-security-policy" in response.headers

    with caplog.at_level(logging.ERROR, logger="linkfall.api"):
        run(go)
    assert any(r.exc_info for r in caplog.records)


def test_each_request_gets_its_own_id_and_one_log_line(caplog: Any) -> None:
    async def go() -> None:
        client = Client(make_app())
        a = await client.get("/api/health")
        b = await client.get("/api/health")
        assert a.headers["x-request-id"] != b.headers["x-request-id"]

    with caplog.at_level(logging.INFO, logger="linkfall.api"):
        run(go)
    lines = [r for r in caplog.records if r.getMessage() == "request"]
    assert len(lines) == 2
    record = lines[0].__dict__
    assert (record["method"], record["path"], record["status"]) == ("GET", "/api/health", 200)
    assert isinstance(record["duration_ms"], int)


def test_json_log_lines_carry_context_and_extras() -> None:
    token = request_id.set("abc123")
    try:
        record = logging.LogRecord(
            "linkfall.x", logging.WARNING, "f.py", 1, "no proposal", (), None
        )
        record.agent = "tactical"
        record.latency_ms = 12
        entry = json.loads(JsonFormatter().format(record))
    finally:
        request_id.reset(token)
    assert entry["message"] == "no proposal"
    assert entry["level"] == "WARNING"
    assert entry["request_id"] == "abc123"
    assert (entry["agent"], entry["latency_ms"]) == ("tactical", 12)
    assert entry["ts"].endswith("Z")


def test_configure_logging_installs_one_json_handler() -> None:
    configure_logging()
    configure_logging()
    handlers = logging.getLogger("linkfall").handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0].formatter, JsonFormatter)


@pytest.fixture
def live_server() -> Iterator[int]:
    app = create_app(config(allowed_hosts=("127.0.0.1", "localhost")), store=EventStore())
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        thread.join(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield int(port)
    server.should_exit = True
    thread.join(5)


def call(
    port: int, method: str, path: str, body: object = None, headers: dict[str, str] | None = None
) -> Any:
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    payload = json.dumps(body) if body is not None else None
    conn.request(
        method, path, body=payload, headers={"Content-Type": "application/json", **(headers or {})}
    )
    response = conn.getresponse()
    data = response.read()
    return response, data


def test_over_a_real_socket_the_headers_the_host_check_and_a_stream(live_server: int) -> None:
    health, data = call(live_server, "GET", "/api/health")
    assert health.status == 200
    assert json.loads(data)["model"] == "not_configured"
    assert health.getheader("Content-Security-Policy")
    assert health.getheader("Content-Type") == "application/json"
    refused, _ = call(live_server, "GET", "/api/health", headers={"Host": "evil.example"})
    assert refused.status == 400
    no_header, _ = call(
        live_server, "POST", "/api/runs", {"seed": 1, "mode": "story", "scenario": "cinder-ward"}
    )
    assert no_header.status == 403
    created, data = call(
        live_server, "POST", "/api/runs",
        {"seed": 1, "mode": "story", "scenario": "cinder-ward"}, {"X-Linkfall-Request": "1"},
    )  # fmt: skip
    assert created.status == 201
    run_id = json.loads(data)["run_id"]
    stream, text = call(live_server, "GET", f"/api/runs/{run_id}/events?follow=false")
    assert stream.status == 200
    assert stream.getheader("Content-Type", "").startswith("text/event-stream")
    assert text.startswith(b"id: 1\nevent: engine\ndata: ")


def test_the_uvicorn_entry_point_builds_an_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    monkeypatch.setenv("LINKFALL_DB", str(tmp_path / "log.sqlite3"))
    monkeypatch.delenv("LINKFALL_MODEL_URL", raising=False)
    module = importlib.import_module("linkfall.api.main")
    module = importlib.reload(module)
    assert module.app.state.config.db_path == tmp_path / "log.sqlite3"
    assert (tmp_path / "log.sqlite3").exists()
    module.app.state.store.close()
