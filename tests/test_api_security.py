import json

import pytest

from api_support import create_run, make_app, run
from asgi import Client

SECURITY = (
    "content-security-policy",
    "x-content-type-options",
    "referrer-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
    "x-frame-options",
)


def test_every_kind_of_response_carries_the_security_headers() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        responses = [
            await client.get("/api/health"),
            await client.get("/api/nothing-here"),
            await client.get("/api/runs/short"),
            await client.post("/api/runs", {"seed": -1}),
            await client.get(f"/api/runs/{run_id}/events", query="follow=false"),
            await client.post("/api/runs", raw_body=b"x" * 5000),
            await Client(make_app(), host="evil.example").get("/api/health"),
        ]
        for response in responses:
            for name in SECURITY:
                assert name in response.headers, (response.status, name)
        csp = responses[0].headers["content-security-policy"]
        assert "script-src 'self'" in csp
        assert "'unsafe-inline'" not in csp
        assert "frame-ancestors 'none'" in csp
        assert responses[0].headers["x-content-type-options"] == "nosniff"
        assert responses[0].headers["cache-control"] == "no-store"

    run(go)


def test_posts_need_the_custom_header() -> None:
    async def go() -> None:
        app = make_app()
        body = {"seed": 1, "mode": "story", "scenario": "cinder-ward"}
        refused = await Client(app, csrf=False).post("/api/runs", body)
        assert refused.status == 403
        assert "x-linkfall-request" in refused.json()["error"]
        assert (await Client(app).post("/api/runs", body)).status == 201

    run(go)


def test_a_cross_origin_post_is_refused_and_a_same_origin_one_is_not() -> None:
    async def go() -> None:
        client = Client(make_app())
        body = {"seed": 1, "mode": "story", "scenario": "cinder-ward"}
        evil = await client.post("/api/runs", body, headers={"origin": "http://evil.example"})
        assert evil.status == 403
        site = await client.post("/api/runs", body, headers={"sec-fetch-site": "cross-site"})
        assert site.status == 403
        same = await client.post("/api/runs", body, headers={"origin": "http://localhost"})
        assert same.status == 201

    run(go)


def test_a_foreign_host_header_is_refused() -> None:
    async def go() -> None:
        response = await Client(make_app(), host="evil.example").get("/api/health")
        assert response.status == 400

    run(go)


def test_get_routes_cannot_change_anything() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        for path in (f"/api/runs/{run_id}/turns", f"/api/runs/{run_id}/commit", "/api/runs"):
            # 405 from the router, or 404 once the static files answer for the path
            assert (await client.get(path)).status in {404, 405}

    run(go)


def test_oversized_bodies_are_refused_with_or_without_a_length_header() -> None:
    async def go() -> None:
        app = make_app()
        client = Client(app)
        assert (await client.post("/api/runs", raw_body=b"{" + b" " * 5000 + b"}")).status == 413
        bad_length = await client.post(
            "/api/runs", raw_body=b"{}", headers={"content-length": "abc"}
        )
        assert bad_length.status == 413
        chunked = await client.open("POST", "/api/runs", raw_body=b"x" * 5000, chunked=True)
        assert (await chunked.read_all()) == b'{"error":"request body is too large"}'
        assert chunked.status == 413
        assert not app.state.registry._runs  # nothing was created

    run(go)


def test_interactive_docs_are_off() -> None:
    async def go() -> None:
        client = Client(make_app())
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert (await client.get(path)).status == 404

    run(go)


@pytest.mark.parametrize(
    "body",
    [
        {"seed": -1, "mode": "story", "scenario": "cinder-ward"},
        {"seed": 2**32, "mode": "story", "scenario": "cinder-ward"},
        {"seed": "1", "mode": "story", "scenario": "cinder-ward"},
        {"seed": 1.5, "mode": "story", "scenario": "cinder-ward"},
        {"seed": 1, "mode": "chaos", "scenario": "cinder-ward"},
        {"seed": 1, "mode": "story", "scenario": "atlantis"},
        {"seed": 1, "mode": "story", "scenario": "cinder-ward", "crew": "gpt"},
        {"seed": 1, "mode": "story", "scenario": "cinder-ward", "admin": True},
        {"mode": "story", "scenario": "cinder-ward"},
        [],
    ],
)
def test_bad_create_bodies_get_a_422_that_does_not_echo_input(body: object) -> None:
    async def go() -> None:
        response = await Client(make_app()).post("/api/runs", body)
        assert response.status == 422
        payload = response.json()
        assert payload["error"] == "invalid request"
        assert all(set(f) == {"field", "problem"} for f in payload["fields"])
        for echoed in ("chaos", "atlantis", "gpt"):
            assert echoed not in response.text.replace("cinder-ward", "")

    run(go)


def test_non_json_bodies_are_refused() -> None:
    async def go() -> None:
        client = Client(make_app())
        assert (await client.post("/api/runs", raw_body=b"seed=1")).status == 422
        assert (await client.post("/api/runs", raw_body=b"")).status == 422
        assert (await client.post("/api/runs", raw_body=json.dumps("text").encode())).status == 422

    run(go)


def test_field_names_in_a_422_are_cut_to_40_characters() -> None:
    async def go() -> None:
        body = {"seed": 1, "mode": "story", "scenario": "cinder-ward", "z" * 300: 1}
        response = await Client(make_app()).post("/api/runs", body)
        assert response.status == 422
        assert all(len(f["field"]) <= 40 for f in response.json()["fields"])
        assert "z" * 41 not in response.text

    run(go)
