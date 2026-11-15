import asyncio
from typing import Any

import linkfall
from api_support import FakeModel, create_run, make_app, play_turn, run, wait_for_phase
from asgi import Client
from linkfall.api.registry import Phase
from linkfall.eventlog.replay import replay
from linkfall.eventlog.store import EventStore


def test_health_reports_the_model_state() -> None:
    async def go() -> None:
        none = (await Client(make_app()).get("/api/health")).json()
        assert none == {"status": "ok", "version": linkfall.__version__, "model": "not_configured"}
        up = FakeModel()
        app = make_app(model=up, model_url="http://model.invalid")
        assert (await Client(app).get("/api/health")).json()["model"] == "up"
        up.up = False
        assert (await Client(app).get("/api/health")).json()["model"] == "down"

    run(go)


def test_create_returns_the_new_run() -> None:
    async def go() -> None:
        response = await Client(make_app()).post(
            "/api/runs", {"seed": 4217, "mode": "hardened", "scenario": "cinder-ward"}
        )
        body = response.json()
        assert response.status == 201
        assert body["mode"] == "hardened"
        assert body["crew"] == "scripted"
        assert body["phase"] == "idle"
        assert (body["seed"], body["scenario"], body["max_turns"]) == (4217, "cinder-ward", 5)
        assert body["turn"] == 1
        assert body["state"]["hp"] == 100
        assert "rng_state" not in body["state"]
        assert len(body["run_id"]) >= 12

    run(go)


def test_run_ids_are_unpredictable_and_unknown_ones_are_404() -> None:
    async def go() -> None:
        client = Client(make_app())
        ids = {await create_run(client) for _ in range(5)}
        assert len(ids) == 5
        for path in (
            "/api/runs/does-not-exist-00/state",
            "/api/runs/short/state",
            "/api/runs/a%20b/state",
        ):
            response = await client.get(path)
            assert response.status == 404
            assert response.json() == {"error": "no such run"}

    run(go)


def test_a_model_crew_needs_a_model_that_is_up() -> None:
    async def go() -> None:
        body = {"seed": 1, "mode": "story", "scenario": "cinder-ward", "crew": "model"}
        assert (await Client(make_app()).post("/api/runs", body)).status == 503
        down = FakeModel(up=False)
        configured = make_app(model=down, model_url="http://model.invalid")
        assert (await Client(configured).post("/api/runs", body)).status == 503
        down.up = True
        ok = await Client(configured).post("/api/runs", body)
        assert ok.status == 201
        assert ok.json()["crew"] == "model"
        default = await Client(configured).post(
            "/api/runs", {"seed": 1, "mode": "story", "scenario": "cinder-ward"}
        )
        assert default.json()["crew"] == "model"

    run(go)


def test_a_whole_mission_through_the_api_replays() -> None:
    async def go() -> None:
        store = EventStore()
        client = Client(make_app(store=store))
        run_id = await create_run(client, mode="story")
        for _ in range(5):
            result = await play_turn(client, run_id, 85)
        assert result["state"]["over"] is True
        final = (await client.get(f"/api/runs/{run_id}/state")).json()
        assert final["over"] is True
        assert final["outcome"] is not None
        verdict = (await client.get(f"/api/runs/{run_id}/replay")).json()
        assert verdict["ok"] is True
        assert verdict["turns"] == 5
        assert verdict["fingerprint"] == replay(store, run_id).fingerprint
        again = await client.post(f"/api/runs/{run_id}/turns", {"link": 85})
        assert again.status == 409

    run(go)


def test_hardened_mode_holds_the_forged_order_through_the_api() -> None:
    async def go() -> None:
        store = EventStore()
        client = Client(make_app(store=store))
        run_id = await create_run(client, mode="hardened")
        actions = []
        for _ in range(5):
            result = await play_turn(client, run_id, 85)
            actions.append(result["command"]["action"])
        assert "drop_shields" not in actions

    run(go)


def test_the_turn_is_a_small_state_machine() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        commit = {"turn": 1, "choice": "lodestar", "link": 55}
        assert (
            await client.post(f"/api/runs/{run_id}/commit", commit)
        ).status == 409  # nothing open
        assert (await client.post(f"/api/runs/{run_id}/turns", {"link": 55})).status == 202
        assert (await client.post(f"/api/runs/{run_id}/turns", {"link": 55})).status == 409  # twice
        await wait_for_phase(client, run_id, "awaiting_pilot")
        assert (await client.post(f"/api/runs/{run_id}/turns", {"link": 55})).status == 409
        stale = await client.post(f"/api/runs/{run_id}/commit", {**commit, "turn": 2})
        assert stale.status == 409
        assert "no longer open" in stale.json()["error"]

    run(go)


def test_a_commit_while_proposals_are_still_arriving_is_refused() -> None:
    async def go() -> None:
        app = make_app()
        client = Client(app)
        run_id = await create_run(client)
        app.state.registry.get(run_id).phase = Phase.COLLECTING
        response = await client.post(
            f"/api/runs/{run_id}/commit", {"turn": 1, "choice": "lodestar", "link": 55}
        )
        assert response.status == 409
        assert "collecting" in response.json()["error"]

    run(go)


def test_bad_commit_bodies_are_422() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        good: dict[str, Any] = {"turn": 1, "choice": "lodestar", "link": 55}
        bad = [
            {**good, "link": 12},
            {**good, "link": "55"},
            {**good, "turn": 0},
            {**good, "choice": "yolo"},
            {**good, "action": "flank"},
            {**good, "agent": "comms"},
            {**good, "choice": "manual"},
            {**good, "choice": "manual", "action": "teleport"},
            {**good, "choice": "manual", "action": "flank", "agent": "comms"},
            {**good, "choice": "sign"},
            {**good, "choice": "sign", "agent": "comms", "action": "flank"},
            {"turn": 1, "choice": "lodestar"},
        ]
        for body in bad:
            response = await client.post(f"/api/runs/{run_id}/commit", body)
            assert response.status == 422, body
        for link in (12, 0, 100, "55", 55.5, None):
            assert (await client.post(f"/api/runs/{run_id}/turns", {"link": link})).status == 422

    run(go)


def test_lodestar_is_locked_out_in_the_manual_zone_and_the_turn_stays_open() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        await client.post(f"/api/runs/{run_id}/turns", {"link": 25})
        await wait_for_phase(client, run_id, "awaiting_pilot")
        locked = await client.post(
            f"/api/runs/{run_id}/commit", {"turn": 1, "choice": "lodestar", "link": 25}
        )
        assert locked.status == 409
        assert "MANUAL" in locked.json()["error"]
        manual = await client.post(
            f"/api/runs/{run_id}/commit",
            {"turn": 1, "choice": "manual", "link": 25, "action": "hold_shield"},
        )
        assert manual.status == 200
        assert manual.json()["command"] == {
            "action": "hold_shield",
            "zone": "MANUAL",
            "manual": True,
        }

    run(go)


def test_a_repeated_commit_returns_the_first_answer_and_writes_nothing_new() -> None:
    async def go() -> None:
        store = EventStore()
        client = Client(make_app(store=store))
        run_id = await create_run(client)
        first = await play_turn(client, run_id, 45)
        rows = len(store.read_rows(run_id))
        again = await client.post(
            f"/api/runs/{run_id}/commit", {"turn": 1, "choice": "lodestar", "link": 45}
        )
        assert again.status == 200
        assert again.json() == first
        assert len(store.read_rows(run_id)) == rows

    run(go)


def test_signing_and_dismissing() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        await play_turn(client, run_id, 85, choice="manual", action="hold_shield")
        await client.post(f"/api/runs/{run_id}/turns", {"link": 85})
        await wait_for_phase(client, run_id, "awaiting_pilot")
        assert (await client.post(f"/api/runs/{run_id}/dismiss", {"agent": "vitals"})).status == 200
        assert (await client.post(f"/api/runs/{run_id}/dismiss", {"agent": "nobody"})).status == 422
        nothing = await client.post(
            f"/api/runs/{run_id}/commit",
            {"turn": 2, "choice": "sign", "link": 85, "agent": "tactical"},
        )
        assert nothing.status == 409
        assert "nothing waiting" in nothing.json()["error"]

    run(go)


def test_dismissing_with_no_open_turn_is_refused() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        assert (await client.post(f"/api/runs/{run_id}/dismiss", {"agent": "comms"})).status == 409

    run(go)


def test_the_number_of_live_runs_is_capped_and_finished_runs_make_room() -> None:
    async def go() -> None:
        client = Client(make_app(max_runs=2))
        first = await create_run(client)
        await create_run(client)
        body = {"seed": 1, "mode": "story", "scenario": "cinder-ward"}
        assert (await client.post("/api/runs", body)).status == 429
        for _ in range(5):
            await play_turn(client, first, 55, choice="manual", action="hold_shield")
        assert (await client.post("/api/runs", body)).status == 201

    run(go)


def test_a_run_from_an_earlier_process_can_be_read_but_not_played() -> None:
    async def go() -> None:
        store = EventStore()
        client = Client(make_app(store=store))
        run_id = await create_run(client)
        await play_turn(client, run_id, 55, choice="manual", action="hold_shield")
        restarted = Client(make_app(store=store))
        state = (await restarted.get(f"/api/runs/{run_id}/state")).json()
        assert state["phase"] == "closed"
        assert state["replay_ok"] is True
        assert (state["seed"], state["scenario"], state["max_turns"]) == (4217, "cinder-ward", 5)
        assert state["turn"] == 2
        assert (await restarted.post(f"/api/runs/{run_id}/turns", {"link": 55})).status == 409
        assert (await restarted.get(f"/api/runs/{run_id}/replay")).json()["ok"] is True

    run(go)


def test_a_collection_crash_is_reported_without_details(caplog: Any) -> None:
    async def go() -> None:
        app = make_app()
        client = Client(app)
        run_id = await create_run(client)
        active = app.state.registry.get(run_id)

        async def boom(_link: int) -> None:
            raise RuntimeError("secret internals")

        active.run.begin_turn = boom
        await client.post(f"/api/runs/{run_id}/turns", {"link": 55})
        state = await wait_for_phase(client, run_id, "error")
        assert "secret internals" not in str(state)
        assert (await client.post(f"/api/runs/{run_id}/turns", {"link": 55})).status == 409
        await asyncio.sleep(0)

    import logging

    with caplog.at_level(logging.ERROR, logger="linkfall.api"):
        run(go)
    assert any("turn collection failed" in r.getMessage() for r in caplog.records)


def test_the_run_summary_carries_the_squad_channel() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        quiet = (await client.get(f"/api/runs/{run_id}/state")).json()["channel"]
        assert quiet == {
            "text": "Squad channel quiet.",
            "signature": quiet["signature"],
            "enemy_text": False,
        }
        await play_turn(client, run_id, 55, choice="manual", action="hold_shield")
        forged = (await client.get(f"/api/runs/{run_id}/state")).json()["channel"]
        assert forged["enemy_text"] is True
        assert "ASHGROVE" in forged["text"]
        assert forged["signature"] < 0.94

    run(go)


def test_the_decision_preview_shows_what_the_policy_would_do_and_changes_nothing() -> None:
    async def go() -> None:
        store = EventStore()
        client = Client(make_app(store=store))
        run_id = await create_run(client)
        await play_turn(client, run_id, 55, choice="manual", action="hold_shield")
        await client.post(f"/api/runs/{run_id}/turns", {"link": 85})
        await wait_for_phase(client, run_id, "awaiting_pilot")
        rows = len(store.read_rows(run_id))
        story = (await client.get(f"/api/runs/{run_id}/decision", query="link=85")).json()
        assert story["zone"] == "DELEGATED"
        assert story["verdict"] == "EXECUTE"
        assert "comms" in story["eligible"]  # the forged order is eligible in story mode
        assisted = (await client.get(f"/api/runs/{run_id}/decision", query="link=45")).json()
        assert assisted["zone"] == "ASSISTED"
        assert "comms" not in assisted["eligible"]
        assert any(h["agent"] == "comms" for h in assisted["held"])
        manual = (await client.get(f"/api/runs/{run_id}/decision", query="link=25")).json()
        assert manual["verdict"] == "MANUAL"
        assert len(store.read_rows(run_id)) == rows

    run(go)


def test_the_decision_preview_refuses_bad_links_and_wrong_moments() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        assert (await client.get(f"/api/runs/{run_id}/decision", query="link=55")).status == 409
        await client.post(f"/api/runs/{run_id}/turns", {"link": 55})
        await wait_for_phase(client, run_id, "awaiting_pilot")
        for bad in ("link=12", "link=abc", ""):
            assert (await client.get(f"/api/runs/{run_id}/decision", query=bad)).status == 422
        assert (
            await client.get("/api/runs/nope-nope-nope/decision", query="link=55")
        ).status == 404

    run(go)


def test_the_preview_leaves_out_dismissed_proposals() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        await play_turn(client, run_id, 55, choice="manual", action="hold_shield")
        await client.post(f"/api/runs/{run_id}/turns", {"link": 85})
        await wait_for_phase(client, run_id, "awaiting_pilot")
        await client.post(f"/api/runs/{run_id}/dismiss", {"agent": "comms"})
        after = (await client.get(f"/api/runs/{run_id}/decision", query="link=85")).json()
        assert "comms" not in after["eligible"]
        assert all(h["agent"] != "comms" for h in after["held"])

    run(go)
