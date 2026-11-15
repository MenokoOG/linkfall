"""Whisper as a script: the same lines every run, whatever Comms answers (ADR 0009)."""

from collections.abc import Sequence

from linkfall.range.contract import Line, Probe, Role


class ScriptedWhisper:
    async def next_line(self, probe: Probe, lines: Sequence[Line]) -> str | None:
        sent = sum(1 for line in lines if line.role is Role.WHISPER)
        return probe.whisper[sent] if sent < len(probe.whisper) else None
