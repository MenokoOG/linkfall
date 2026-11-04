import asyncio
import json
from typing import Any

from api_support import create_run, make_app, play_turn, run, wait_for_phase
from asgi import Client
from linkfall.api.sse import frame
from linkfall.eventlog.types import LogRow


def parse(text: str) -> list[dict[str, Any]]:
    """Parse SSE text into {id, event, data} records, skipping comments."""
    records = []
    for block in text.split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if not line.startswith(":")
        )
        if fields:
            records.append({**fields, "data": json.loads(fields["data"])})
    return records


def test_frame_format_and_event_name_sanitising() -> None:
    row = LogRow(7, "r1", 2, "proposal", {"say": "line one\nline two"})
    text = frame(row)
    assert text.startswith("id: 7\nevent: proposal\ndata: {")
    assert text.endswith("\n\n")
    assert text.count("\n") == 4  # the newline inside the text is escaped, not sent raw
    hostile = frame(LogRow(8, "r1", 1, "x\nevent: admin", {}))
    assert "event: unknown" in hostile
    assert "admin" not in hostile.split("data:")[0]


def test_a_finished_run_streams_every_row_and_closes() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        for _ in range(5):
            await play_turn(client, run_id, 55, choice="manual", action="hold_shield")
        response = await client.get(f"/api/runs/{run_id}/events")
        assert response.status == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"
        records = parse(response.text)
        ids = [int(r["id"]) for r in records]
        assert ids == sorted(ids)
        kinds = {r["event"] for r in records}
        assert {"engine", "command", "turn", "proposal", "decision", "pilot"} <= kinds
        assert records[-1]["data"]["payload"]["message"].startswith("Mission over:")

    run(go)


def test_resume_with_last_event_id_or_after() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        await play_turn(client, run_id, 55, choice="manual", action="hold_shield")
        everything = parse(
            (await client.get(f"/api/runs/{run_id}/events", query="follow=false")).text
        )
        cut = int(everything[5]["id"])
        by_header = await client.get(
            f"/api/runs/{run_id}/events", query="follow=false", headers={"last-event-id": str(cut)}
        )
        by_query = await client.get(f"/api/runs/{run_id}/events", query=f"follow=false&after={cut}")
        expected = [r["id"] for r in everything if int(r["id"]) > cut]
        assert [r["id"] for r in parse(by_header.text)] == expected
        assert [r["id"] for r in parse(by_query.text)] == expected

    run(go)


def test_bad_resume_values_are_refused() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        bad = await client.get(f"/api/runs/{run_id}/events", headers={"last-event-id": "abc"})
        assert bad.status == 400
        assert (await client.get(f"/api/runs/{run_id}/events", query="after=-1")).status == 422
        assert (await client.get("/api/runs/nope-nope-nope/events")).status == 404

    run(go)


def test_a_live_stream_delivers_cards_as_they_arrive_and_stops_on_disconnect() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        stream = await client.open("GET", f"/api/runs/{run_id}/events")
        seen = ""
        first = await stream.chunk()
        assert first is not None
        seen += first.decode()
        await client.post(f"/api/runs/{run_id}/turns", {"link": 55})
        while (
            "event: turn" not in seen
            or seen.count("event: proposal") + seen.count("event: no_proposal") < 4
        ):
            piece = await stream.chunk(timeout=5)
            assert piece is not None
            seen += piece.decode()
        assert seen.index("event: turn") < seen.index("event: proposal")
        await wait_for_phase(client, run_id, "awaiting_pilot")
        await stream.close()

    run(go)


def test_an_idle_live_stream_sends_heartbeats() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        stream = await client.open("GET", f"/api/runs/{run_id}/events")
        pieces = [await stream.chunk(), await stream.chunk(timeout=3)]
        assert any(p is not None and p.startswith(b": keep-alive") for p in pieces)
        await stream.close()

    run(go)


def test_a_live_stream_closes_itself_when_the_run_is_over() -> None:
    async def go() -> None:
        client = Client(make_app())
        run_id = await create_run(client)
        stream = await client.open("GET", f"/api/runs/{run_id}/events")

        async def play() -> None:
            for _ in range(5):
                await play_turn(client, run_id, 55, choice="manual", action="hold_shield")

        player = asyncio.create_task(play())
        text = (await stream.read_all(timeout=10)).decode()
        await player
        assert "Mission over" in text

    run(go)


def test_a_stream_stops_after_its_maximum_age() -> None:
    async def go() -> None:
        client = Client(make_app(stream_max_s=0.05, stream_heartbeat_s=60))
        run_id = await create_run(client)
        stream = await client.open("GET", f"/api/runs/{run_id}/events")
        await stream.read_all(timeout=3)  # ends by itself; the browser would reconnect

    run(go)
