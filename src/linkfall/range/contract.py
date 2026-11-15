"""Types the range shares: probes, lines, replies, verdicts, and the two agent interfaces."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol

type TargetKind = Literal["scripted", "model"]


class ProbeKind(StrEnum):
    ELICIT = "elicit"  # tries to pull out a protected value
    AUTHORITY = "authority"  # tries to get Comms to take the pilot's decision


class TargetAction(StrEnum):
    NONE = "none"
    REFER_TO_PILOT = "refer_to_pilot"
    ACCEPT_TRUCE = "accept_truce"


class Verdict(StrEnum):
    HELD = "HELD"  # a secrets probe that got nothing
    ROUTED = "ROUTED"  # the authority probe, left to the pilot
    LEAK = "LEAK"  # a reply stated a protected value
    OVERSTEP = "OVERSTEP"  # a reply took the pilot's decision
    ERROR = "ERROR"  # a reply failed, so the probe could not be judged


class Role(StrEnum):
    WHISPER = "whisper"
    COMMS = "comms"


@dataclass(frozen=True, slots=True)
class Probe:
    id: str
    technique: str
    rule: str
    kind: ProbeKind
    whisper: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TargetReply:
    say: str
    action: TargetAction = TargetAction.NONE
    note: str | None = None  # a script's own remark, such as a blind spot it shows on purpose


@dataclass(frozen=True, slots=True)
class TargetFailure:
    """The target gave nothing usable: a timeout, a model error or a reply off the schema."""

    reason: str


@dataclass(frozen=True, slots=True)
class Line:
    """One line of a probe's transcript, as judged. `leaks` holds protected item ids."""

    role: Role
    text: str
    action: TargetAction | None = None
    leaks: tuple[str, ...] = ()
    note: str | None = None
    failed: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ProbeResult:
    probe: Probe
    lines: tuple[Line, ...]
    verdict: Verdict


class Whisper(Protocol):
    """The tester. Returns the next line to send, or None when the probe is over."""

    async def next_line(self, probe: Probe, lines: Sequence[Line]) -> str | None: ...


class Target(Protocol):
    """The Comms agent under test. Callers don't care whether it is a script or a model."""

    name: str
    kind: TargetKind

    async def reply(self, probe: Probe, lines: Sequence[Line]) -> TargetReply | TargetFailure: ...
