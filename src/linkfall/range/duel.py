"""One probe: Whisper sends a line, the target answers, the check runs. Stops at a leak."""

import asyncio
from collections.abc import Callable

from linkfall.range.contract import (
    Line,
    Probe,
    ProbeResult,
    Role,
    Target,
    TargetFailure,
    TargetReply,
    Whisper,
)
from linkfall.range.judge import verdict_for
from linkfall.range.vault import stated
from linkfall.supervisor.modelclient import ModelError

_MAX_REASON = 200


def _clip(text: str) -> str:
    return text if len(text) <= _MAX_REASON else text[: _MAX_REASON - 3] + "..."


async def _ask(target: Target, probe: Probe, lines: list[Line], timeout_s: float) -> (
    TargetReply | TargetFailure
):  # fmt: skip
    """A timeout or a model error becomes a failure with its reason. Nothing is repaired."""
    try:
        return await asyncio.wait_for(target.reply(probe, lines), timeout=timeout_s)
    except TimeoutError:
        return TargetFailure(f"timeout after {timeout_s:g}s")
    except ModelError as exc:
        return TargetFailure(_clip(f"model error: {exc}"))


async def run_probe(
    probe: Probe, whisper: Whisper, target: Target, timeout_s: float, clock: Callable[[], float]
) -> ProbeResult:
    lines: list[Line] = []
    while (sent := await whisper.next_line(probe, lines)) is not None:
        lines.append(Line(Role.WHISPER, sent))
        started = clock()
        answer = await _ask(target, probe, lines, timeout_s)
        latency_ms = round((clock() - started) * 1000)
        if isinstance(answer, TargetFailure):
            lines.append(Line(Role.COMMS, "", failed=_clip(answer.reason), latency_ms=latency_ms))
            break
        leaks = stated(answer.say)
        lines.append(
            Line(Role.COMMS, answer.say, answer.action, leaks, answer.note, None, latency_ms)
        )
        if leaks:
            break
    return ProbeResult(probe, tuple(lines), verdict_for(probe.kind, lines))
