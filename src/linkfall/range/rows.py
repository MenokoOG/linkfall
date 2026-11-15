"""How a probe's result becomes log rows and back, and the fingerprint of a whole run."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from linkfall.engine.fingerprint import canonical_json
from linkfall.range.contract import Line, ProbeResult, Role, TargetAction, Verdict

type Payload = dict[str, object]


class RowKind(StrEnum):
    LINE = "line"  # one transcript line, as judged
    VERDICT = "verdict"  # the verdict that closes a probe
    END = "end"  # the run finished; holds the fingerprint


@dataclass(frozen=True, slots=True)
class NewRow:
    probe: str
    kind: RowKind
    payload: Payload


@dataclass(frozen=True, slots=True)
class LogRow:
    id: int
    probe: str
    kind: str  # a plain str: a damaged log may hold a kind we don't know
    payload: Payload


class RowError(ValueError):
    """A logged row does not hold what its kind promises."""


def line_payload(line: Line) -> Payload:
    return {
        "role": line.role.value,
        "text": line.text,
        "action": line.action.value if line.action is not None else None,
        "leaks": list(line.leaks),
        "note": line.note,
        "failed": line.failed,
        "latency_ms": line.latency_ms,
    }


def rows_for(result: ProbeResult) -> list[NewRow]:
    probe = result.probe.id
    rows = [NewRow(probe, RowKind.LINE, line_payload(line)) for line in result.lines]
    return [*rows, NewRow(probe, RowKind.VERDICT, {"verdict": result.verdict.value})]


def _text(payload: Payload, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise RowError(f"{key} is not text")
    return value


def _optional_text(payload: Payload, key: str) -> str | None:
    return None if payload.get(key) is None else _text(payload, key)


def line_from(payload: Payload) -> Line:
    try:
        role = Role(_text(payload, "role"))
        action_text = _optional_text(payload, "action")
        action = TargetAction(action_text) if action_text is not None else None
    except ValueError as exc:
        raise RowError(str(exc)) from exc
    leaks = payload.get("leaks")
    if not isinstance(leaks, list) or not all(isinstance(item, str) for item in leaks):
        raise RowError("leaks is not a list of text")
    latency = payload.get("latency_ms")
    if latency is not None and (not isinstance(latency, int) or isinstance(latency, bool)):
        raise RowError("latency_ms is not a whole number")
    return Line(
        role,
        _text(payload, "text"),
        action,
        tuple(leaks),
        _optional_text(payload, "note"),
        _optional_text(payload, "failed"),
        latency,
    )


def verdict_from(payload: Payload) -> Verdict:
    try:
        return Verdict(_text(payload, "verdict"))
    except ValueError as exc:
        raise RowError(str(exc)) from exc


def fingerprint(judged: Sequence[tuple[str, Sequence[Line], Verdict]]) -> str:
    """SHA-256 over what was said and how it was judged. Latency and script notes stay out."""
    payload = [
        {
            "probe": probe,
            "verdict": verdict.value,
            "lines": [
                {
                    "role": line.role.value,
                    "text": line.text,
                    "action": line.action.value if line.action is not None else None,
                    "leaks": list(line.leaks),
                    "failed": line.failed,
                }
                for line in lines
            ],
        }
        for probe, lines, verdict in judged
    ]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
