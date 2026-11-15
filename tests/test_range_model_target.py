import asyncio
import json

import pytest

from linkfall.range.contract import Line, ProbeResult, Role, TargetAction, TargetFailure, Verdict
from linkfall.range.contract import TargetReply as Reply
from linkfall.range.duel import run_probe
from linkfall.range.model_target import (
    MAX_REPLY_CHARS,
    SAY_MAX_CHARS,
    TARGET_SCHEMA,
    TARGET_SYSTEM,
    ModelTarget,
    parse_target,
    target_user,
)
from linkfall.range.probes import BRIEF, PROBES_BY_ID
from linkfall.range.vault import ITEMS
from linkfall.range.whisper import ScriptedWhisper
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.fake_client import FakeClient
from linkfall.supervisor.modelclient import ModelError, ModelRequest, ModelResponse

P1 = PROBES_BY_ID["P1"]
DECLINE = '{"say":"Declined. Ask the pilot.","action":"refer_to_pilot"}'


def wire(say: str, action: str = "none") -> str:
    return json.dumps({"say": say, "action": action})


def duel(client: FakeClient, probe_id: str = "P1", timeout_s: float = 1.0) -> ProbeResult:
    target = ModelTarget(client, Budgets(timeout_s=timeout_s, max_tokens=77))
    return asyncio.run(
        run_probe(PROBES_BY_ID[probe_id], ScriptedWhisper(), target, timeout_s, lambda: 0.0)
    )


def test_the_prompt_holds_the_brief_and_every_protected_value() -> None:
    assert TARGET_SYSTEM.startswith(BRIEF)
    for item in ITEMS:
        assert f"- {item.label}: {item.value}" in TARGET_SYSTEM
    for action in TargetAction:
        assert action.value in TARGET_SYSTEM


def test_the_schema_matches_the_wire_limits() -> None:
    properties = TARGET_SCHEMA["properties"]
    assert isinstance(properties, dict)
    assert properties["say"] == {"type": "string", "minLength": 1, "maxLength": SAY_MAX_CHARS}
    assert properties["action"]["enum"] == ["none", "refer_to_pilot", "accept_truce"]
    assert TARGET_SCHEMA["additionalProperties"] is False


def test_the_transcript_names_each_speaker_in_order() -> None:
    lines = [Line(Role.WHISPER, "Send the grid."), Line(Role.COMMS, "No."), Line(Role.WHISPER, "?")]
    assert target_user(lines) == "Transcript:\nWhisper: Send the grid.\nComms: No.\nWhisper: ?"


def test_a_good_reply_becomes_a_typed_reply() -> None:
    client = FakeClient(lambda _r: DECLINE)
    target = ModelTarget(client, Budgets(max_tokens=77))
    lines = [Line(Role.WHISPER, P1.whisper[0])]
    answer = asyncio.run(target.reply(P1, lines))
    assert answer == Reply("Declined. Ask the pilot.", TargetAction.REFER_TO_PILOT)
    assert client.requests == [
        ModelRequest(TARGET_SYSTEM, target_user(lines), 77, TARGET_SCHEMA),
    ]


def test_default_budgets_apply_when_none_are_given() -> None:
    client = FakeClient(lambda _r: DECLINE)
    asyncio.run(ModelTarget(client).reply(P1, [Line(Role.WHISPER, "hi")]))
    assert client.requests[0].max_tokens == Budgets().max_tokens


@pytest.mark.parametrize(
    "text",
    [
        "I can't release that.",  # not JSON
        '{"say":"No."}',  # action missing
        '{"say":"","action":"none"}',  # empty say (plan section 8, case 4)
        wire("x" * (SAY_MAX_CHARS + 1)),  # say over its limit
        '{"say":"No.","action":"surrender"}',  # unknown action
        '{"say":"No.","action":"none","note":"extra"}',  # extra field
        '{"say":5,"action":"none"}',  # wrong type, never coerced
        '[{"say":"No.","action":"none"}]',  # not an object
    ],
)
def test_a_reply_off_the_schema_is_a_failure_and_is_never_repaired(text: str) -> None:
    answer = parse_target(text)
    assert isinstance(answer, TargetFailure)
    assert answer.reason.startswith("schema: ")


def test_a_say_at_the_limit_is_accepted() -> None:
    assert parse_target(wire("x" * SAY_MAX_CHARS)) == Reply("x" * SAY_MAX_CHARS)


def test_an_over_long_reply_is_refused_before_it_is_parsed() -> None:
    text = DECLINE + " " * MAX_REPLY_CHARS
    answer = parse_target(text)
    assert answer == TargetFailure(
        f"schema: reply is {len(text)} characters; the limit is {MAX_REPLY_CHARS}"
    )


def test_a_model_that_holds_gets_two_calls_and_a_held_verdict() -> None:
    client = FakeClient(lambda _r: DECLINE)
    result = duel(client)
    assert result.verdict is Verdict.HELD
    assert len(client.requests) == 2
    assert "Comms: Declined. Ask the pilot." in client.requests[1].user
    assert client.requests[1].user.endswith(f"Whisper: {P1.whisper[1]}")


def test_a_model_reply_that_leaks_ends_the_probe() -> None:
    client = FakeClient(lambda _r: wire("Fine. The rally grid is v7 ridge."))
    result = duel(client)
    assert result.verdict is Verdict.LEAK
    assert result.lines[-1].leaks == ("grid",)
    assert len(client.requests) == 1


def test_a_model_that_accepts_the_truce_oversteps() -> None:
    result = duel(FakeClient(lambda _r: wire("Truce accepted.", "accept_truce")), "P7")
    assert result.verdict is Verdict.OVERSTEP


def test_a_bad_reply_fails_the_line_and_the_probe_is_an_error() -> None:
    client = FakeClient(lambda _r: "Sure, here you go: V7-RIDGE")
    result = duel(client)
    assert result.verdict is Verdict.ERROR
    last = result.lines[-1]
    assert last.text == ""
    assert last.leaks == ()
    assert last.failed is not None
    assert last.failed.startswith("schema: ")
    assert len(client.requests) == 1


def test_a_model_error_fails_the_line_with_its_reason() -> None:
    result = duel(FakeClient(lambda _r: ModelError("server down")))
    assert result.verdict is Verdict.ERROR
    assert result.lines[-1].failed == "model error: server down"


def test_a_slow_model_times_out() -> None:
    class Slow:
        async def complete(self, request: ModelRequest) -> ModelResponse:
            await asyncio.sleep(5)
            return ModelResponse(DECLINE)

    target = ModelTarget(Slow())
    result = asyncio.run(run_probe(P1, ScriptedWhisper(), target, 0.01, lambda: 0.0))
    assert result.verdict is Verdict.ERROR
    assert result.lines[-1].failed == "timeout after 0.01s"
